"""台本(Script) → voice/{シーン}_{セリフ}.wav ＋ durations.json ＋ kana.txt（読み確認用）

エンジンは実行環境で決める（台本には書かない。同じ台本を Linux のチャットでも Windows でも使うため）。
  core : VOICEVOX CORE（setup.sh で vv/ に入れる。チャット環境の Linux 用）
  http : VOICEVOX アプリ／エンジンの HTTP API（Windows。アプリか vv-engine\\run.exe を起動しておく）
環境変数 MOVIE_MAKER_VOICE_ENGINE で明示できる。未指定なら vv/ に CORE 一式があれば core、なければ http。
"""
import json, os, sys, urllib.error, urllib.parse, urllib.request, wave
from pathlib import Path

HERE = Path(__file__).parent
VV = HERE / "vv"
ORT_LIB = VV / "voicevox_onnxruntime-linux-x64-1.17.3/lib/libvoicevox_onnxruntime.so.1.17.3"
DIC = VV / "open_jtalk_dic_utf_8-1.11"
VVM = VV / "0.vvm"   # ずんだもん（ノーマル=3 など）入り

ENGINE_ENV = "MOVIE_MAKER_VOICE_ENGINE"
URL_ENV = "VOICEVOX_URL"
# localhost だと Windows では先に ::1 を試して待たされることがあるので IPv4 を直接指定する
DEFAULT_URL = "http://127.0.0.1:50021"
SAMPLE_RATE = 24000     # build.SR と同じ。CORE の既定値に合わせ、HTTP でも明示する
HTTP_TIMEOUT = 60       # 秒。長いセリフの合成でも収まる余裕を取る


def engine_name():
    name = os.environ.get(ENGINE_ENV, "").strip().lower()
    if name:
        if name not in ("core", "http"):
            sys.exit(f"{ENGINE_ENV}={name!r} は使えません（core か http）")
        return name
    return "core" if ORT_LIB.exists() and VVM.exists() else "http"


def open_synth():
    from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
    ort = Onnxruntime.load_once(filename=str(ORT_LIB))
    syn = Synthesizer(ort, OpenJtalk(str(DIC)))
    with VoiceModelFile.open(str(VVM)) as m:
        syn.load_voice_model(m)
    return syn


class CoreEngine:
    def __init__(self):
        import voicevox_core
        self.syn = open_synth()
        self.label = f"core（voicevox_core {voicevox_core.__version__}）"

    def speak(self, text, style_id, speed):
        """→ (wav のバイト列, 読みのカナ)"""
        q = self.syn.create_audio_query(text, style_id)
        q.speed_scale = speed
        kana = "".join(m.text for ap in q.accent_phrases for m in ap.moras)
        return self.syn.synthesis(q, style_id), kana


class HttpEngine:
    def __init__(self):
        self.url = os.environ.get(URL_ENV, DEFAULT_URL).rstrip("/")
        try:
            version = self._request("/version", method="GET").decode("utf-8").strip('"')
        except (urllib.error.URLError, OSError) as e:
            if os.name != "nt":
                sys.exit(f"VOICEVOX に接続できません（{self.url}：{e}）。"
                         "チャット環境なら先に `bash setup.sh` で CORE を vv/ に入れてください。")
            sys.exit(f"VOICEVOX に接続できません（{self.url}：{e}）。\n"
                     "VOICEVOX アプリを起動するか、エンジンだけを起動してください（PowerShell）：\n"
                     '  Start-Process "C:\\Program Files\\VOICEVOX\\vv-engine\\run.exe" -WindowStyle Hidden')
        self.label = f"http（{self.url}、エンジン {version}）"

    def _request(self, path, params=None, body=None, method="POST"):
        url = self.url + path + ("?" + urllib.parse.urlencode(params) if params else "")
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            sys.exit(f"VOICEVOX の {path} が失敗（HTTP {e.code}）：{detail}")

    def speak(self, text, style_id, speed):
        q = json.loads(self._request("/audio_query", {"text": text, "speaker": style_id}))
        q["speedScale"] = speed
        q["outputSamplingRate"] = SAMPLE_RATE
        q["outputStereo"] = False
        kana = "".join(m["text"] for ap in q["accent_phrases"] for m in ap["moras"])
        return self._request("/synthesis", {"speaker": style_id}, body=q), kana


def open_engine():
    return CoreEngine() if engine_name() == "core" else HttpEngine()


def synth(script, out="voice"):
    os.makedirs(out, exist_ok=True)
    eng = open_engine()
    v = script.meta.voice
    # 環境によってエンジンが違うので、どれで作った音声かを読み確認の先頭に残す
    durs, kana_log = [], [f"# 音声エンジン：{eng.label}"]
    for s, sc in enumerate(script.scenes):
        row = []
        for i, ln in enumerate(sc.lines):
            wav, kana = eng.speak(ln.speak, v.style_id, v.speed)
            fn = f"{out}/{s}_{i}.wav"
            Path(fn).write_bytes(wav)
            with wave.open(fn) as w:
                if (w.getframerate(), w.getnchannels()) != (SAMPLE_RATE, 1):
                    sys.exit(f"{fn}: {w.getframerate()}Hz / {w.getnchannels()}ch（期待 {SAMPLE_RATE}Hz / モノラル）")
                row.append(w.getnframes() / w.getframerate())
            kana_log.append(f"{s}-{i} {row[-1]:5.2f}s  {kana}")
        durs.append(row)
    json.dump(durs, open(f"{out}/durations.json", "w"))
    Path(f"{out}/kana.txt").write_text("\n".join(kana_log) + "\n", encoding="utf-8")
    return durs

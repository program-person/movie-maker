"""台本(Script) → voice/{シーン}_{セリフ}.wav ＋ durations.json ＋ kana.txt（読み確認用）"""
import json, os, wave
from pathlib import Path

HERE = Path(__file__).parent
VV = HERE / "vv"
ORT_LIB = VV / "voicevox_onnxruntime-linux-x64-1.17.3/lib/libvoicevox_onnxruntime.so.1.17.3"
DIC = VV / "open_jtalk_dic_utf_8-1.11"
VVM = VV / "0.vvm"   # ずんだもん（ノーマル=3 など）入り


def open_synth():
    from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
    ort = Onnxruntime.load_once(filename=str(ORT_LIB))
    syn = Synthesizer(ort, OpenJtalk(str(DIC)))
    with VoiceModelFile.open(str(VVM)) as m:
        syn.load_voice_model(m)
    return syn


def synth(script, out="voice"):
    os.makedirs(out, exist_ok=True)
    syn = open_synth()
    v = script.meta.voice
    durs, kana_log = [], []
    for s, sc in enumerate(script.scenes):
        row = []
        for i, ln in enumerate(sc.lines):
            q = syn.create_audio_query(ln.speak, v.style_id)
            q.speed_scale = v.speed
            fn = f"{out}/{s}_{i}.wav"
            Path(fn).write_bytes(syn.synthesis(q, v.style_id))
            with wave.open(fn) as w:
                row.append(w.getnframes() / w.getframerate())
            kana = "".join(m.text for ap in q.accent_phrases for m in ap.moras)
            kana_log.append(f"{s}-{i} {row[-1]:5.2f}s  {kana}")
        durs.append(row)
    json.dump(durs, open(f"{out}/durations.json", "w"))
    Path(f"{out}/kana.txt").write_text("\n".join(kana_log) + "\n", encoding="utf-8")
    return durs

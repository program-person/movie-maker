"""台本JSON → 動画

  python3 build.py check   台本.json              # 検証＋描画前チェック（lint）
  python3 build.py voice   台本.json              # 音声合成（kana.txt で読みを確認）
  python3 build.py scene   台本.json <番号>       # シーン1つを描画（300秒制限対策で分割）
  python3 build.py finish  台本.json <出力.mp4>   # 結合＋声＋BGM＋音量調整 → verify
  python3 build.py verify  台本.json <出力.mp4>   # 描画後チェック（コマ数・長さ・音量）
  python3 build.py all     台本.json <出力.mp4>   # 短い台本なら一括
  python3 build.py preview 台本.json <番号> <秒> <出力.png>

作業ファイルは build/<台本名>/ に置く。
"""
import json, subprocess, sys, wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import schema
from draw import W, H, FPS, BG, clamp, subtitle
from scenes import RENDERERS

HERE = Path(__file__).parent
PRE, GAP, POST, FIRST_PRE, LAST_POST = 0.45, 0.22, 0.6, 0.3, 1.2
SR = 24000
def mix(voice, bgm):
    """声と BGM を混ぜるフィルタ（入力番号を指定）。声の間は BGM を下げる（サイドチェイン）"""
    return (f"[{voice}:a]aresample=44100,pan=stereo|c0=c0|c1=c0,volume=1.25,asplit=2[v1][v2];"
            f"[{bgm}:a]volume=0.2[bg];"
            "[bg][v1]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[bgd];"
            "[bgd][v2]amix=inputs=2:duration=first:normalize=0")
TP_MARGIN = 0.5      # AAC 変換でピークが少し上がる分（実測 +0.2dB）の余裕
LUFS_TOL = 1.0       # verify で許容するラウドネスのずれ（LU）


class Job:
    def __init__(self, path):
        self.script = schema.load(path)
        self.dir = HERE / "build" / Path(path).stem
        self.voice = self.dir / "voice"
        self.dir.mkdir(parents=True, exist_ok=True)

    # 台本と合成済み音声がずれていないか（セリフを直して voice を忘れる事故の防止）
    def manifest(self):
        return {"voice": self.script.meta.voice.model_dump(),
                "speak": [[ln.speak for ln in sc.lines] for sc in self.script.scenes]}

    def durations(self):
        mf = self.voice / "manifest.json"
        if not mf.exists() or json.loads(mf.read_text(encoding="utf-8")) != self.manifest():
            sys.exit("音声が台本と一致しません。先に `build.py voice` を実行してください。")
        return json.loads((self.voice / "durations.json").read_text())

    def timeline(self):
        durs, out, tg = self.durations(), [], 0.0
        last = len(durs) - 1
        for s, ds in enumerate(durs):
            cues, t = [], FIRST_PRE if s == 0 else PRE
            for du in ds:
                cues.append(t); t += du + GAP
            length = t - GAP + (LAST_POST if s == last else POST)
            n = int(round(length * FPS))            # フレーム単位に丸めてから開始時刻を積む
            out.append({"start": tg, "len": n / FPS, "frames": n, "cues": cues, "durs": ds})
            tg += n / FPS
        return out, tg

    def frame(self, s, sc_t, t):
        sc = self.script.scenes[s]
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        RENDERERS[sc.type](d, t, sc, sc_t["cues"], sc.credit or self.script.meta.credit)
        subtitle(d, t, sc_t["cues"], sc_t["durs"], sc.lines, GAP)
        fade = min(clamp(t / 0.2) if s > 0 else 1.0, clamp((sc_t["len"] - t) / 0.25))
        if fade < 1:
            img = Image.blend(Image.new("RGB", (W, H), BG), img, fade)
        return img


def cmd_voice(job):
    from voice import synth
    synth(job.script, str(job.voice))
    (job.voice / "manifest.json").write_text(json.dumps(job.manifest(), ensure_ascii=False), encoding="utf-8")
    print((job.voice / "kana.txt").read_text(encoding="utf-8"), end="")


def cmd_scene(job, s):
    tl, _ = job.timeline(); sc_t = tl[s]
    out = job.dir / f"seg_{s}.mp4"
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "fast",
                          "-pix_fmt", "yuv420p", "-crf", "21", str(out)], stdin=subprocess.PIPE)
    for i in range(sc_t["frames"]):
        p.stdin.write(job.frame(s, sc_t, i / FPS).tobytes())
    p.stdin.close()
    if p.wait() != 0: sys.exit("ffmpeg 失敗")
    print(f"scene {s} ({job.script.scenes[s].type}) {sc_t['len']:.2f}s → {out.name}")


def cmd_finish(job, out):
    tl, total = job.timeline()
    missing = [s for s in range(len(tl)) if not (job.dir / f"seg_{s}.mp4").exists()]
    if missing: sys.exit(f"未描画のシーン: {missing}")
    # 声トラック
    buf = np.zeros(int((total + 1) * SR), dtype=np.float32)
    for s, sc_t in enumerate(tl):
        for i, c in enumerate(sc_t["cues"]):
            with wave.open(str(job.voice / f"{s}_{i}.wav")) as w:
                assert w.getframerate() == SR
                x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
            p = int(round((sc_t["start"] + c) * SR)); buf[p:p + len(x)] += x
    vt = job.dir / "voice_track.wav"
    with wave.open(str(vt), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(np.clip(buf[:int(total * SR)], -32768, 32767).astype(np.int16).tobytes())
    bgm = job.dir / "bgm.wav"
    subprocess.run(["python3", str(HERE / "bgm.py"), f"{total:.3f}", str(bgm)], check=True)
    segs = job.dir / "segs.txt"
    segs.write_text("".join(f"file 'seg_{s}.mp4'\n" for s in range(len(tl))))
    vid = job.dir / "video_only.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(segs),
                    "-c", "copy", str(vid)], check=True)
    # 音量：1回目で測り、2回目にその値を渡して目標へ合わせる（loudnorm の2パス）
    au = job.script.meta.audio
    ln = f"loudnorm=I={au.lufs}:TP={au.true_peak - TP_MARGIN}:LRA=11"
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(vt), "-i", str(bgm), "-filter_complex",
                        f"{mix(0, 1)},{ln}:print_format=json[a]", "-map", "[a]", "-f", "null", "-"],
                       capture_output=True, text=True, check=True)
    m = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    ln += (f":measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
           f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    # -shortest は付けない（付けると AAC の端数で最後の1コマが落ちていた）
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(vid), "-i", str(vt), "-i", str(bgm),
                    "-filter_complex", f"{mix(1, 2)},{ln},aresample=44100[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out], check=True)
    print(f"done {total:.2f}s → {out}")
    if not cmd_verify(job, out):
        sys.exit("描画後チェックでエラー")


def _probe(out, stream):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries",
                        "stream=width,height,r_frame_rate,nb_frames,duration", "-of", "json", out],
                       capture_output=True, text=True, check=True)
    st = json.loads(r.stdout)["streams"]
    return st[0] if st else None


def _decoded_len(out, sr=8000):
    """音声を実際に復号した長さ（秒）。ffprobe の duration は AAC の前後の詰め物を含むので使わない"""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", out, "-map", "a:0", "-ac", "1", "-ar", str(sr),
                        "-f", "s16le", "-"], capture_output=True, check=True)
    return len(r.stdout) / 2 / sr


def cmd_verify(job, out):
    """描画後チェック。結果を表示し、エラーがなければ True"""
    tl, total = job.timeline()
    frames = sum(x["frames"] for x in tl)
    au = job.script.meta.audio
    v, a = _probe(out, "v:0"), _probe(out, "a:0")
    errors, info = [], []
    if not v:
        errors.append("映像のストリームがない")
    else:
        if (v["width"], v["height"], v["r_frame_rate"]) != (W, H, f"{FPS}/1"):
            errors.append(f"形式が違う：{v['width']}x{v['height']} {v['r_frame_rate']}")
        if int(v["nb_frames"]) != frames:
            errors.append(f"コマ数 {v['nb_frames']}（計算 {frames}）")
        info.append(f"{v['nb_frames']} コマ")
    if not a:
        errors.append("音声のストリームがない")
    else:
        alen = _decoded_len(out)
        if abs(alen - total) > 0.05:
            errors.append(f"音声の長さ {alen:.3f}s（計算 {total:.3f}s、許容 ±0.05s）")
        r = subprocess.run(["ffmpeg", "-nostats", "-i", out, "-map", "a:0", "-af", "ebur128=peak=true",
                            "-f", "null", "-"], capture_output=True, text=True, check=True)
        summ = r.stderr[r.stderr.rindex("Summary:"):]
        lufs = float(summ.split("I:")[1].split()[0])
        tp = float(summ.split("Peak:")[1].split()[0])
        if abs(lufs - au.lufs) > LUFS_TOL:
            errors.append(f"ラウドネス {lufs:.1f} LUFS（目標 {au.lufs:g} ±{LUFS_TOL:g}）")
        if tp > au.true_peak:
            errors.append(f"トゥルーピーク {tp:.1f} dBTP（上限 {au.true_peak:g}）")
        info += [f"音声 {alen:.3f}s", f"{lufs:.1f} LUFS", f"{tp:.1f} dBTP"]
    for e in errors: print(f"[エラー] verify: {e}")
    print(f"verify: {' / '.join(info)} → {'NG' if errors else 'OK'}")
    return not errors


if __name__ == "__main__":
    cmd, path, *rest = sys.argv[1:]
    job = Job(path)
    if cmd in ("voice", "all", "check"):
        import lint
        if not lint.report(job.script):
            sys.exit("描画前チェックでエラー。台本を直してください。")
    if cmd == "check":
        sc = job.script.scenes
        print(f"OK: {job.script.meta.title} / {len(sc)} シーン {[x.type for x in sc]}")
    elif cmd == "voice":
        cmd_voice(job)
    elif cmd == "scene":
        cmd_scene(job, int(rest[0]))
    elif cmd == "finish":
        cmd_finish(job, rest[0])
    elif cmd == "verify":
        sys.exit(0 if cmd_verify(job, rest[0]) else 1)
    elif cmd == "all":
        cmd_voice(job)
        for s in range(len(job.script.scenes)): cmd_scene(job, s)
        cmd_finish(job, rest[0])
    elif cmd == "preview":
        tl, _ = job.timeline(); s = int(rest[0])
        job.frame(s, tl[s], float(rest[1])).save(rest[2])
    else:
        sys.exit(__doc__)

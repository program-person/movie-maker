"""legacy/make_vertical.py と新しい描画が同じ画を出すかを画素単位で比べる（ステップ3の合格判定用）

  python3 tests/compare_legacy.py 台本.json <新シーン番号> <legacy シーン番号> [--step N] [--real]

同じ cue・同じ長さを両方に渡し、全コマ（--step で間引き可）の差分を数える。
既定は仮の声の長さ（全セリフ3秒）。--real なら build/<台本名>/voice の実際の長さを使う。
差があったコマは build/compare/ に 新・旧・差分 の PNG を保存する。
"""
import json, os, sys, tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("path"); ap.add_argument("s_new", type=int); ap.add_argument("s_old", type=int)
    ap.add_argument("--step", type=int, default=1); ap.add_argument("--real", action="store_true")
    o = ap.parse_args()
    path, s_new, s_old, step = o.path, o.s_new, o.s_old, o.step

    job = build.Job(path)
    n_lines = [len(sc.lines) for sc in job.script.scenes]
    if o.real:
        durs = job.durations()
    else:
        durs = [[3.0] * n for n in n_lines]
    job.durations = lambda: durs              # 合成済み音声がなくても timeline を作れるようにする
    tl, _ = job.timeline()
    sc_t = tl[s_new]

    # legacy は import 時に voice_v/durations.json を読むので、仮のディレクトリに置いてから import
    tmp = tempfile.mkdtemp()
    os.makedirs(f"{tmp}/voice_v")
    old_durs = [[0.0]] * 9
    old_durs[s_old] = sc_t["durs"]
    json.dump(old_durs, open(f"{tmp}/voice_v/durations.json", "w"))
    cwd = os.getcwd(); os.chdir(tmp)
    sys.path.insert(0, str(ROOT / "legacy"))
    import make_vertical as mv
    os.chdir(cwd)

    if len(mv.N[s_old]) != len(job.script.scenes[s_new].lines):
        sys.exit("セリフ数が legacy と違います")
    for i, ln in enumerate(job.script.scenes[s_new].lines):
        if ln.text != mv.N[s_old][i][0] or ln.speak != mv.N[s_old][i][1]:
            print(f"注意: lines[{i}] が legacy の台本と違う")

    # legacy の s（シーン番号）は字幕の参照と最初のシーンのフェード判定に使われる。
    # 新側の s_new と「最初のシーンかどうか」がそろっていないと比較にならない
    if (s_new == 0) != (s_old == 0):
        sys.exit("最初のシーンかどうかが新旧で違うため、フェードが一致しません")

    old_sc = {"cues": sc_t["cues"], "durs": sc_t["durs"], "len": sc_t["len"]}
    out = ROOT / "build" / "compare"; out.mkdir(parents=True, exist_ok=True)
    bad, worst = [], (0, None)
    frames = range(0, sc_t["frames"], step)
    for i in frames:
        t = i / build.FPS
        a = np.asarray(job.frame(s_new, sc_t, t), dtype=np.int16)
        b = np.asarray(mv.render_frame(s_old, old_sc, t), dtype=np.int16)
        n = int((np.abs(a - b).max(axis=2) > 0).sum())
        if n:
            bad.append(i)
            if n > worst[0]:
                worst = (n, i)
                Image.fromarray(a.astype(np.uint8)).save(out / f"s{s_new}_new.png")
                Image.fromarray(b.astype(np.uint8)).save(out / f"s{s_new}_old.png")
                diff = ImageChops.difference(Image.fromarray(a.astype(np.uint8)), Image.fromarray(b.astype(np.uint8)))
                diff.point(lambda v: 255 if v else 0).save(out / f"s{s_new}_diff.png")
    kind = job.script.scenes[s_new].type
    if bad:
        print(f"NG scene {s_new}({kind}) vs legacy {s_old}: {len(bad)}/{len(frames)} コマで差 "
              f"（最大 {worst[0]} 画素 @ {worst[1] / build.FPS:.2f}s、画像は build/compare/）")
        sys.exit(1)
    print(f"OK scene {s_new}({kind}) vs legacy {s_old}: {len(frames)} コマすべて一致（{sc_t['len']:.2f}s）")


if __name__ == "__main__":
    main()

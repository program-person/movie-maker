"""完成した mp4 をわざと壊し、verify が見つけるかの確認

  python3 tests/verify_negative.py 台本.json 完成.mp4

1コマ欠け／音が大きすぎ／小さすぎ／音声なし／音声が短い、の5つを作って verify にかける。
先に元の mp4 自体が verify を通ることも確かめる。
"""
import subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

script, good = sys.argv[1], sys.argv[2]
job = build.Job(script)
tl, _ = job.timeline()
n = sum(x["frames"] for x in tl)
tmp = Path(tempfile.mkdtemp())
V = ["-c:v", "copy"]
A = ["-c:a", "aac", "-b:a", "192k"]
CASES = {
    "1コマ欠け": ["-frames:v", str(n - 1), "-c", "copy"],
    "音が大きすぎ": V + ["-af", "volume=6dB"] + A,
    "音が小さすぎ": V + ["-af", "volume=-6dB"] + A,
    "音声なし": V + ["-an"],
    "音声が短い": V + ["-af", "atrim=0:1"] + A,
}
if not build.cmd_verify(job, good):
    sys.exit("元の mp4 が verify を通らないので、比較になりません")
ng = 0
for name, args in CASES.items():
    out = str(tmp / "bad.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", good, *args, out], check=True)
    print(f"--- {name}")
    if build.cmd_verify(job, out):
        ng += 1; print(f"[NG] {name}: 通ってしまった")
print(f"{len(CASES) - ng}/{len(CASES)} 件を検出")
sys.exit(1 if ng else 0)

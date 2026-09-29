"""わざと壊した台本がスキーマで弾かれるかの確認。python3 tests/schema_negative.py"""
import copy, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pydantic import ValidationError  # noqa: E402
from schema import Script  # noqa: E402

base = json.loads((ROOT / "samples/opus55_full.json").read_text(encoding="utf-8"))
Script.model_validate(base)
S = lambda d, i: d["scenes"][i]      # 0 hook, 1 tier, 2 bars, 3 price, 4 cards, 5-7 list, 8 end

CASES = [
    # --- ステップ1からある分 ---
    ("未知の型", lambda d: S(d, 0).update(type="chart")),
    ("キーの打ち間違い", lambda d: S(d, 7)["items"][0].update(nte="x")),
    ("list の cue が範囲外", lambda d: S(d, 7)["items"][2].update(cue=4)),
    ("hook の ask.cue 範囲外", lambda d: S(d, 0)["ask"].update(cue=2)),
    ("出典なし", lambda d: d["meta"].update(sources=[])),
    ("URL不正", lambda d: d["meta"]["sources"][0].update(url="anthropic.com")),
    ("speak 欠落", lambda d: S(d, 0)["lines"][0].pop("speak")),
    ("番号の形式", lambda d: S(d, 7).update(num="7")),
    ("list 項目4つ", lambda d: S(d, 7)["items"].append({"main": "x", "cue": 0})),
    ("空文字の字幕", lambda d: S(d, 0)["lines"][1].update(text="")),
    ("cue が負", lambda d: S(d, 7)["items"][0].update(cue=-1)),
    # --- ステップ3で追加 ---
    ("delay が負", lambda d: S(d, 1)["tiers"][1].update(delay=-0.1)),
    ("delay が大きすぎ", lambda d: S(d, 8)["items"][1].update(delay=6)),
    ("色名の間違い", lambda d: S(d, 1)["tiers"][0].update(color="orange")),
    ("tier が1段", lambda d: S(d, 1).update(tiers=S(d, 1)["tiers"][:1])),
    ("bars の値の個数違い", lambda d: S(d, 2)["rows"][0].update(values=[1, 2])),
    ("bars の値が max 超え", lambda d: S(d, 2)["rows"][1].update(values=[1, 2, 101])),
    ("price の note.cue 範囲外", lambda d: S(d, 3)["note"].update(cue=4)),
    ("price の summary 3行", lambda d: S(d, 3)["summary"].update(lines=["a", "b", "c"])),
    ("cards 3枚", lambda d: S(d, 4)["items"].append(S(d, 4)["items"][0])),
    ("end の y が字幕枠に入る", lambda d: S(d, 8)["items"][0].update(y=1300)),
]

ng = 0
for name, mutate in CASES:
    d = copy.deepcopy(base); mutate(d)
    try:
        Script.model_validate(d); print(f"[NG] {name}: 通ってしまった"); ng += 1
    except ValidationError as e:
        err = e.errors()[0]
        print(f"[OK] {name}: {'.'.join(map(str, err['loc']))} → {err['msg']}")
print(f"{len(CASES) - ng}/{len(CASES)} 件を弾いた")
sys.exit(1 if ng else 0)

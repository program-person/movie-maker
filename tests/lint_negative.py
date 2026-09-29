"""わざと壊した台本を lint が見つけるかの確認。python3 tests/lint_negative.py"""
import copy, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import lint  # noqa: E402
from schema import Script  # noqa: E402

base = json.loads((ROOT / "samples/opus55_full.json").read_text(encoding="utf-8"))
S = lambda d, i: d["scenes"][i]      # 0 hook, 1 tier, 2 bars, 3 price, 4 cards, 5-7 list, 8 end
LONG = "とても長い説明文がここに入って画面の幅を大きく超えてしまうような場合を想定した文章"

# (名前, 壊し方, 期待：エラーか警告か, 期待するメッセージの一部)
CASES = [
    ("hook のタイトルが長い", lambda d: S(d, 0).update(title=["Claude Opus 5.5 Ultra Max"]), "error", "横にはみ出し"),
    ("クレジットが長い", lambda d: S(d, 1).update(credit="出典：" + LONG), "error", "横にはみ出し"),
    ("list の項目が長く字幕と重なる", lambda d: [it.update(main=LONG, note=LONG) for it in S(d, 5)["items"]],
     "error", "字幕枠と重なる"),
    ("字幕が長く本文と重なる", lambda d: S(d, 6)["lines"][0].update(text=LONG * 3), "error", "字幕枠と重なる"),
    ("end の文字が重なる", lambda d: S(d, 8)["items"][2].update(y=600), "error", "が重なる"),
    ("price の項目名が長い", lambda d: S(d, 3)["rows"][0].update(name=LONG), "error", "が重なる"),
    ("bars の見出しが長い", lambda d: S(d, 2)["rows"][0].update(label="コマンドライン作業の長いベンチマーク"),
     "error", "が重なる"),
    ("tier の名前が長い", lambda d: S(d, 1)["tiers"][0].update(name="Mythos / Fable / Opus / Sonnet"),
     "error", "枠からはみ出す"),
    ("cards の下段が長い", lambda d: S(d, 4)["items"][0].update(rest=LONG), "error", "枠からはみ出す"),
    ("price のまとめが長い", lambda d: S(d, 3)["summary"].update(lines=["典型的な作業で 約40%安くなって出力も速い"]),
     "error", "枠からはみ出す"),
    ("手動改行の直後が句読点", lambda d: S(d, 5)["items"][0].update(main="大事な情報を\n、先に書く"),
     "warn", "行頭に"),
    ("speak に英字", lambda d: S(d, 0)["lines"][1].update(speak="Claude がまとめるのだ。"), "warn", "英字"),
]

ng = 0
for name, mutate, want, key in CASES:
    d = copy.deepcopy(base); mutate(d)
    errors, warns = lint.lint(Script.model_validate(d))
    hit = [m for m in (errors if want == "error" else warns) if key in m]
    if hit:
        print(f"[OK] {name}: {hit[0]}")
    else:
        ng += 1
        print(f"[NG] {name}: 見つからない（エラー {errors[:2]} / 警告 {warns[:2]}）")
print(f"{len(CASES) - ng}/{len(CASES)} 件を検出")
sys.exit(1 if ng else 0)

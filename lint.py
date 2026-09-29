"""描画前チェック（声の合成も不要）

  python3 lint.py 台本.json      # build.py check / voice からも呼ばれる

エラー（止める）：画面の安全範囲からのはみ出し／本文と字幕枠の重なり／文字どうしの重なり／
                  文字がカードや枠の境界をまたぐ
警告（表示だけ）：行頭禁則／speak に残った英字

描画関数は変えず、描画の受け口（ImageDraw）を「描いた位置を記録してから本物に渡す」記録係に差し替えて、
全要素が出そろった状態の位置を調べる。
"""
import re
import sys

from PIL import Image, ImageDraw

import schema
from draw import W, H, BG, X0, X1, NO_HEAD, subtitle
from scenes import RENDERERS

SAFE_X = (X0 - 10, X1 + 10)       # 字幕枠と同じ幅。右側は縦型SNSのボタン列を避ける
SAFE_Y = (150, 1580)              # 上端 150 は仮の値（上部タブを避ける目安・要検証）／1580 以降は何も置かない
SPEAK_OK = {"AI"}                 # そのままで正しく読まれると確認済みの英字
VOICE_CREDIT = "音声：VOICEVOX:ずんだもん"


class Recorder:
    """ImageDraw の代わりに渡す記録係。描いたものの外接矩形を items に残す"""

    def __init__(self):
        self.real = ImageDraw.Draw(Image.new("RGB", (W, H), BG))
        self.items = []           # (種類, (x0, y0, x1, y1), 文字列 or None)

    def text(self, xy, text, font=None, anchor=None, **kw):
        box = self.real.textbbox(xy, text, font=font, anchor=anchor)
        self.items.append(("text", box, text))

    def rectangle(self, box, **kw):
        self.items.append(("rect", tuple(box), None))

    def rounded_rectangle(self, box, **kw):
        self.items.append(("rect", tuple(box), None))


def _overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _inside(a, b):
    return b[0] <= a[0] and b[1] <= a[1] and a[2] <= b[2] and a[3] <= b[3]


def _short(s, n=14):
    s = s.replace("\n", "⏎")
    return s if len(s) <= n else s[:n] + "…"


def lint_scene(script, s):
    """シーン s を調べて (errors, warnings) を返す"""
    sc = script.scenes[s]
    cr = sc.credit or script.meta.credit
    tag = f"scene {s}({sc.type})"
    errors, warns = [], []

    # 本文：cue を 0,1,2… とし、十分あとの時刻で描く（全要素が出そろい、棒も伸びきった状態）
    rec = Recorder()
    cues = [float(i) for i in range(len(sc.lines))]
    RENDERERS[sc.type](rec, 1e4, sc, cues, cr)
    credit_texts = {cr, VOICE_CREDIT}
    body = [it for it in rec.items if it[2] not in credit_texts]

    # 字幕：1行ずつ表示させて枠と文字を記録
    subs = []
    for i in range(len(sc.lines)):
        r = Recorder()
        c = [10.0 * k for k in range(len(sc.lines))]
        subtitle(r, c[i], c, [1.0] * len(sc.lines), sc.lines, 0.0)
        subs.append(r.items)
    sub_top = min(it[1][1] for items in subs for it in items if it[0] == "rect")

    # 1) 安全範囲
    for kind, (x0, y0, x1, y1), txt in rec.items + [it for items in subs for it in items]:
        what = f"「{_short(txt)}」" if txt else "枠"
        if x0 < SAFE_X[0] or x1 > SAFE_X[1]:
            errors.append(f"{tag}: {what} が横にはみ出し（x {x0:.0f}〜{x1:.0f}、許容 {SAFE_X[0]}〜{SAFE_X[1]}）")
        if y0 < SAFE_Y[0] or y1 > SAFE_Y[1]:
            errors.append(f"{tag}: {what} が縦にはみ出し（y {y0:.0f}〜{y1:.0f}、許容 {SAFE_Y[0]}〜{SAFE_Y[1]}）")

    # 2) 本文と字幕枠（一番背の高い字幕の上端より下に本文が来たら重なり）
    for kind, box, txt in body:
        if box[3] > sub_top:
            what = f"「{_short(txt)}」" if txt else "枠"
            errors.append(f"{tag}: {what} が字幕枠と重なる（下端 y {box[3]:.0f}、字幕枠の上端 {sub_top:.0f}）")

    # 3) 文字どうし
    texts = [it for it in body if it[0] == "text"]
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            if _overlap(texts[i][1], texts[j][1]):
                errors.append(f"{tag}: 「{_short(texts[i][2])}」と「{_short(texts[j][2])}」が重なる")

    # 4) 文字が枠の境界をまたぐ（枠と重ならない、または枠の内側に収まる、のどちらかなら正常）
    rects = [it[1] for it in body if it[0] == "rect"]
    for kind, box, txt in texts:
        for rb in rects:
            if _overlap(box, rb) and not _inside(box, rb):
                errors.append(f"{tag}: 「{_short(txt)}」が枠からはみ出す（文字 y {box[1]:.0f}〜{box[3]:.0f}／"
                              f"x {box[0]:.0f}〜{box[2]:.0f}、枠 y {rb[1]:.0f}〜{rb[3]:.0f}／x {rb[0]:.0f}〜{rb[2]:.0f}）")

    # 5) 行頭禁則（描かれた各行の先頭。本文と字幕の両方）
    for kind, box, txt in body + [it for items in subs for it in items]:
        if txt and txt[0] in NO_HEAD:
            warns.append(f"{tag}: 行頭に「{txt[0]}」がある行「{_short(txt)}」")

    # 6) speak の英字（VOICEVOX はアルファベットを1文字ずつ読んだり崩れたりする）
    for i, ln in enumerate(sc.lines):
        words = [w for w in re.findall(r"[A-Za-z]+", ln.speak) if w not in SPEAK_OK]
        if words:
            warns.append(f"{tag}: lines[{i}].speak に英字 {words}（カタカナにするか、読みを kana.txt で確認）")

    return errors, warns


def lint(script):
    errors, warns = [], []
    for s in range(len(script.scenes)):
        e, w = lint_scene(script, s)
        errors += e; warns += w
    return errors, warns


def report(script):
    """結果を表示し、エラーがあれば False"""
    errors, warns = lint(script)
    for w in warns: print(f"[警告] {w}")
    for e in errors: print(f"[エラー] {e}")
    print(f"lint: エラー {len(errors)} 件、警告 {len(warns)} 件")
    return not errors


if __name__ == "__main__":
    sys.exit(0 if report(schema.load(sys.argv[1])) else 1)

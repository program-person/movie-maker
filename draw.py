"""縦型（1080x1920）描画の共通部品。make_video.py / make_vertical.py から移植"""
import re
from PIL import ImageFont

W, H, FPS = 1080, 1920, 30
BG = (20, 20, 19)
FG = (240, 238, 230)
SUB = (170, 166, 155)
ACC = (217, 119, 87)
WARN = (230, 190, 90)
CARD = (38, 37, 34)
GRAY = (110, 108, 100)
BLUE = (106, 155, 204)
PALETTE = {"fg": FG, "sub": SUB, "acc": ACC, "warn": WARN, "gray": GRAY, "blue": BLUE}  # 台本の color 名 → RGB
X0, X1 = 70, 940            # 右側は TikTok のボタン列を避ける

FONT_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
_cache = {}
def F(size, bold=True):
    k = (size, bold)
    if k not in _cache:
        _cache[k] = ImageFont.truetype(FONT_B if bold else FONT_R, size, index=0)  # index 0 = JP
    return _cache[k]

def clamp(x): return max(0.0, min(1.0, x))
def ease(x): x = clamp(x); return 1 - (1 - x) ** 3
def mix(c, a): return tuple(int(BG[i] + (c[i] - BG[i]) * a) for i in range(3))
def appear(t, start, dur=0.5): return ease((t - start) / dur)

# ---------- 折り返し ----------
_TOK = re.compile(r"[A-Za-z0-9.%$+\-]+ ?|.", re.S)
NO_HEAD = set("、。，．！？」』）)ーぁぃぅぇぉっゃゅょァィゥェォッャュョ…%")

def wrap(s, font, maxw):
    """英数字のかたまりは途中で切らない／句読点・小さい文字を行頭に置かない"""
    lines, cur = [], ""
    for tok in _TOK.findall(s):
        if cur and font.getlength(cur + tok) > maxw and tok[0] not in NO_HEAD:
            lines.append(cur.rstrip()); cur = tok.lstrip()
        else:
            cur += tok
    if cur: lines.append(cur)
    return lines

def wrap_sub(s, font, maxw):
    """字幕用：読点・句点で区切ったまとまりごとに詰める"""
    lines, cur = [], ""
    for ph in re.findall(r"[^、。！？]+[、。！？]*", s):
        if font.getlength(cur + ph) <= maxw:
            cur += ph
        elif font.getlength(ph) <= maxw:
            if cur: lines.append(cur)
            cur = ph
        else:
            parts = wrap(cur + ph, font, maxw)
            lines += parts[:-1]; cur = parts[-1]
    if cur: lines.append(cur)
    return lines

def para(d, x, y, s, size, color=FG, a=1.0, bold=True, maxw=X1 - X0, lh=None, anchor="la"):
    """折り返し付きテキスト（\\n で手動改行）。描いた高さを返す"""
    f = F(size, bold); lh = lh or int(size * 1.35)
    y += (1 - a) * 30
    ls = [l for part in s.split("\n") for l in wrap(part, f, maxw)]
    for k, l in enumerate(ls):
        d.text((x, y + k * lh), l, font=f, fill=mix(color, a), anchor=anchor)
    return len(ls) * lh

# ---------- 共通パーツ ----------
def header(d, t, num, title):
    a = appear(t, 0.0)
    para(d, X0, 200, num, 36, ACC, a)
    para(d, X0, 248, title, 64, FG, a)
    d.rectangle([X0, 340, X0 + int(360 * a), 346], fill=ACC)

def card(d, box, a):
    d.rounded_rectangle(box, radius=24, fill=mix(CARD, a))

def credit(d, src):
    d.text((X0, 1500), src, font=F(24, False), fill=SUB)
    d.text((X0, 1534), "音声：VOICEVOX:ずんだもん", font=F(24, False), fill=SUB)

def subtitle(d, t, cues, durs, lines, gap):
    for c, du, ln in zip(cues, durs, lines):
        if c - 0.05 <= t < c + du + gap * 0.8:
            f = F(46)
            ls = wrap_sub(ln.text, f, X1 - X0 - 60)
            lh, pad = 64, 22
            y1 = 1470; y0 = y1 - (lh * len(ls) + pad * 2)
            d.rounded_rectangle([X0 - 10, y0, X1 + 10, y1], radius=20, fill=(10, 10, 9), outline=ACC, width=3)
            for k, l in enumerate(ls):
                d.text(((X0 + X1) // 2, y0 + pad + k * lh + lh // 2), l, font=f, fill=FG, anchor="mm")
            return

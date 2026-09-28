import subprocess
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1280, 720, 30
BG = (20, 20, 19)
FG = (240, 238, 230)
SUB = (170, 166, 155)
ACC = (217, 119, 87)     # Opus 5.5
C_OLD = (110, 108, 100)  # Opus 5
C_FAB = (106, 155, 204)  # Fable 5.1
WARN = (230, 190, 90)

FONT_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
_cache = {}
def F(size, bold=True):
    k = (size, bold)
    if k not in _cache:
        _cache[k] = ImageFont.truetype(FONT_B if bold else FONT_R, size, index=0)
    return _cache[k]

def clamp(x): return max(0.0, min(1.0, x))
def ease(x):
    x = clamp(x); return 1 - (1 - x) ** 3
def mix(c, a): return tuple(int(BG[i] + (c[i] - BG[i]) * a) for i in range(3))

def appear(t, start, dur=0.5): return ease((t - start) / dur)

def text(d, xy, s, size, color=FG, a=1.0, bold=True, anchor="la", dy=True):
    x, y = xy
    if dy: y += (1 - a) * 24
    d.text((x, y), s, font=F(size, bold), fill=mix(color, a), anchor=anchor)

def header(d, t, num, title):
    a = appear(t, 0.0)
    text(d, (80, 60), num, 26, ACC, a)
    text(d, (80, 95), title, 46, FG, a)
    d.rectangle([80, 165, 80 + int(300 * a), 169], fill=ACC)

def footer(d, s="出典：Anthropic公式発表（2026/9/22）"):
    d.text((W - 40, H - 30), s, font=F(16, False), fill=SUB, anchor="rs")

# ---------------- scenes ----------------
def s_title(d, t):
    a = appear(t, 0.2, 0.8)
    text(d, (W // 2, 230), "Claude Opus 5.5", 84, ACC, a, anchor="mm")
    text(d, (W // 2, 330), "で、何が変わった？", 52, FG, appear(t, 0.8), anchor="mm")
    text(d, (W // 2, 430), "2026年9月22日リリース ／ Opus 5 との比較", 28, SUB, appear(t, 1.4), False, anchor="mm")
    footer(d, "出典：Anthropic公式発表・各種報道")

def s_summary(d, t):
    header(d, t, "01", "ひとことで言うと")
    text(d, (W // 2, 330), "上位モデル Fable 5.1 並みの性能を", 44, FG, appear(t, 0.6), anchor="mm")
    text(d, (W // 2, 410), "Opus 5 より 約40% 安く", 60, ACC, appear(t, 1.3), anchor="mm")
    text(d, (W // 2, 540), "※ Fable 5.1 … Opus より上の「Mythos」ティアのモデル", 22, SUB, appear(t, 2.2), False, anchor="mm")
    footer(d)

BENCH = [
    ("Terminal-Bench 4.0", "コマンドライン上の複数ステップ作業", 52.3, 55.8, 66.4),
    ("CursorBench 4.0", "実際の開発現場由来のあいまいなコーディング課題", 46.6, 51.8, 57.8),
    ("OSWorld 2.0", "パソコン画面の操作（コンピュータユース）", 74.0, 80.7, 81.8),
]
def s_bench(d, t):
    header(d, t, "02", "性能：ベンチマーク（性能テスト）")
    # legend
    lx = 760
    for i, (name, c) in enumerate([("Opus 5", C_OLD), ("Fable 5.1", C_FAB), ("Opus 5.5", ACC)]):
        a = appear(t, 0.3)
        d.rectangle([lx + i * 170, 192, lx + i * 170 + 22, 214], fill=mix(c, a))
        text(d, (lx + i * 170 + 32, 188), name, 22, FG, a, False, dy=False)
    for r, (name, desc, o5, f5, o55) in enumerate(BENCH):
        y0 = 250 + r * 140
        a = appear(t, 0.6 + r * 0.6)
        text(d, (80, y0), name, 28, FG, a)
        text(d, (80, y0 + 38), desc, 18, SUB, a, False)
        g = ease((t - (1.0 + r * 0.6)) / 1.4)
        for j, (v, c) in enumerate([(o5, C_OLD), (f5, C_FAB), (o55, ACC)]):
            yy = y0 + 4 + j * 30
            x0 = 520
            w = int(640 * v / 100 * g)
            d.rectangle([x0, yy, x0 + max(w, 1), yy + 22], fill=mix(c, clamp(g * 2)))
            if g > 0.05:
                d.text((x0 + w + 10, yy - 3), f"{v * g:.1f}%", font=F(20), fill=mix(FG if c != ACC else ACC, clamp(g * 2)))
    footer(d)

PRICE = [("入力", 5.0, 4.0, "−20%"), ("出力", 25.0, 20.0, "−20%"), ("キャッシュ読取", 0.50, 0.20, "−60%")]
def s_price(d, t):
    header(d, t, "03", "コストと速度")
    text(d, (80, 200), "100万トークンあたりの料金（API）", 24, SUB, appear(t, 0.4), False)
    for r, (name, old, new, pct) in enumerate(PRICE):
        y = 260 + r * 90
        a = appear(t, 0.8 + r * 0.5)
        text(d, (80, y), name, 32, FG, a)
        text(d, (400, y), (f"${old:.2f}" if old < 1 else f"${old:g}"), 32, C_OLD, a)
        text(d, (540, y), "→", 32, SUB, a)
        text(d, (610, y), (f"${new:.2f}" if new < 1 else f"${new:g}"), 40, ACC, appear(t, 1.2 + r * 0.5))
        text(d, (800, y + 4), pct, 32, ACC, appear(t, 1.5 + r * 0.5))
    a = appear(t, 3.3)
    text(d, (80, 540), "典型的な作業で 約40%安 ／ 出力速度 30%以上アップ", 32, FG, a)
    text(d, (80, 600), "※ キャッシュ読取 … 同じ前置き文を使い回すときの割安料金。エージェント作業のコストの大半を占める", 19, SUB, appear(t, 4.0), False)
    footer(d)

CASES = [
    ("68万行", "のコード移行を 1日未満 で完了（テスター報告）"),
    ("20万行", "の監査・修正：Opus 5 は20時間超 → 3時間未満"),
    ("C → Rust", "移植（HAProxy）：Fable 5.1 より速く、コスト 51%減"),
]
def s_cases(d, t):
    header(d, t, "04", "長くて大きい仕事に強い")
    for r, (big, rest) in enumerate(CASES):
        y = 250 + r * 120
        a = appear(t, 0.6 + r * 0.9)
        d.rectangle([80, y - 5, 86, y + 60], fill=mix(ACC, a))
        text(d, (110, y), big, 48, ACC, a)
        bw = d.textlength(big, font=F(48))
        text(d, (120 + bw, y + 16), rest, 28, FG, a, False)
    text(d, (80, 620), "※ HAProxy … Webアクセスを複数サーバーに振り分ける有名なソフト", 19, SUB, appear(t, 3.4), False)
    footer(d)

def bullets(d, t, items, y0=240, gap=95, start=0.6, step=0.9):
    for r, it in enumerate(items):
        main, note = it if isinstance(it, tuple) else (it, None)
        y = y0 + r * gap
        a = appear(t, start + r * step)
        d.ellipse([84, y + 14, 100, y + 30], fill=mix(ACC, a))
        text(d, (120, y), main, 34, FG, a)
        if note: text(d, (120, y + 48), note, 19, SUB, a, False)

def s_writing(d, t):
    header(d, t, "05", "文章がわかりやすくなった")
    bullets(d, t, [
        ("いちばん大事な情報を先に書く", None),
        ("専門用語や独特な言い回しを減らす", None),
        ("指定した「書き方ルール」に従う", "Opus 5 への「読みにくい」というフィードバックへの対応"),
    ])
    footer(d)

def s_safety(d, t):
    header(d, t, "06", "安全性")
    bullets(d, t, [
        ("自動行動監査で過去最高スコア", "約2,000の模擬シナリオでAIの振る舞いを検査するテスト"),
        ("決められた境界を越えようとする頻度 約85%減", "Opus 5・Mythos 5.1 との比較"),
        ("プロンプトインジェクションへの耐性アップ", "Webページなど外部データに紛れ込んだ不正な指示のこと"),
    ], gap=120)
    footer(d)

def s_caveats(d, t):
    header(d, t, "07", "注意点")
    items = [
        ("thinking（考えてから答えるモード）はオフにできない", None),
        ("サイバーセキュリティ系の作業の多くは Opus 4.8 に振り替え", "安全対策（セーフガード）のため"),
        ("第三者評価では「1タスクあたりのトークン消費が多い」との指摘も", "公式の「約40%安い」とは測り方が違う可能性あり → 要検証"),
    ]
    for r, (main, note) in enumerate(items):
        y = 240 + r * 120
        a = appear(t, 0.6 + r * 0.9)
        text(d, (84, y), "!", 34, WARN, a)
        text(d, (120, y), main, 30, FG, a)
        if note: text(d, (120, y + 46), note, 19, SUB, a, False)
    footer(d, "出典：Anthropic公式発表／Artificial Analysis（Wccftech経由）")

def s_end(d, t):
    text(d, (W // 2, 280), "次は Sonnet 5.5・Haiku 5.5", 48, FG, appear(t, 0.3), anchor="mm")
    text(d, (W // 2, 360), "数週間以内に登場予定", 36, ACC, appear(t, 0.9), anchor="mm")
    text(d, (W // 2, 520), "この動画は Python（Pillow）＋ ffmpeg でコードから生成しました", 22, SUB, appear(t, 1.8), False, anchor="mm")

SCENES = [(s_title, 5), (s_summary, 6.5), (s_bench, 9), (s_price, 9), (s_cases, 8.5),
          (s_writing, 7), (s_safety, 8.5), (s_caveats, 9.5), (s_end, 5.5)]

def main(out):
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                          "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", out],
                         stdin=subprocess.PIPE)
    for fn, dur in SCENES:
        n = int(dur * FPS)
        for i in range(n):
            t = i / FPS
            img = Image.new("RGB", (W, H), BG)
            fn(ImageDraw.Draw(img), t)
            # fade in / out
            fade = min(clamp(t / 0.3), clamp((dur - t) / 0.4))
            if fade < 1:
                img = Image.blend(Image.new("RGB", (W, H), BG), img, fade)
            p.stdin.write(img.tobytes())
    p.stdin.close(); p.wait()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2:  # preview: scene index, time
        fn, _ = SCENES[int(sys.argv[1])]
        img = Image.new("RGB", (W, H), BG); fn(ImageDraw.Draw(img), float(sys.argv[2]))
        img.save(sys.argv[3] if len(sys.argv) > 3 else "/home/claude/prev.png")
    else:
        main(sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/outputs/opus55_whats_new.mp4")

import json, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw
from make_video import BG, FG, SUB, ACC, C_OLD, C_FAB, WARN, F, clamp, ease, mix, appear
from narration_v import N

W, H, FPS = 1080, 1920, 30
PRE, GAP, POST = 0.45, 0.22, 0.6
VOICE = "voice_v"
DUR = json.load(open(f"{VOICE}/durations.json"))
X0, X1 = 70, 940            # 右側はTikTokのボタン類を避けて広めに空ける
CARD = (38, 37, 34)
SRC = "出典：Anthropic公式発表（2026/9/22）"

# ---------- 描画ヘルパー ----------
import re
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

def para(d, x, y, s, size, color=FG, a=1.0, bold=True, maxw=X1 - X0, lh=None, anchor="la"):
    """折り返し付きテキスト。描いた高さを返す"""
    f = F(size, bold); lh = lh or int(size * 1.35)
    y += (1 - a) * 30
    ls = [l for part in s.split("\n") for l in wrap(part, f, maxw)]  # \n は手動改行
    for k, l in enumerate(ls):
        d.text((x, y + k * lh), l, font=f, fill=mix(color, a), anchor=anchor)
    return len(ls) * lh

def header(d, t, num, title):
    a = appear(t, 0.0)
    para(d, X0, 200, num, 36, ACC, a)
    para(d, X0, 248, title, 64, FG, a)
    d.rectangle([X0, 340, X0 + int(360 * a), 346], fill=ACC)

def card(d, box, a):
    d.rounded_rectangle(box, radius=24, fill=mix(CARD, a))

def credit(d, src=SRC):
    d.text((X0, 1500), src, font=F(24, False), fill=SUB)
    d.text((X0, 1534), "音声：VOICEVOX:ずんだもん", font=F(24, False), fill=SUB)

# ---------- 字幕 ----------
def wrap_sub(s, font, maxw):
    """読点・句点で区切ったまとまりごとに詰める（語の途中で改行しにくくする）"""
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

def subtitle(d, t, sc, s):
    for i, (c, du) in enumerate(zip(sc["cues"], sc["durs"])):
        if c - 0.05 <= t < c + du + GAP * 0.8:
            f = F(46)
            ls = wrap_sub(N[s][i][0], f, X1 - X0 - 60)
            lh, pad = 64, 22
            h = lh * len(ls) + pad * 2
            y1 = 1470; y0 = y1 - h
            d.rounded_rectangle([X0 - 10, y0, X1 + 10, y1], radius=20, fill=(10, 10, 9), outline=ACC, width=3)
            for k, l in enumerate(ls):
                d.text(((X0 + X1) // 2, y0 + pad + k * lh + lh // 2), l, font=f, fill=FG, anchor="mm")
            return

# ---------- シーン ----------
def s_hook(d, t, c):
    para(d, W // 2, 330, "Claude", 110, ACC, appear(t, 0.0), anchor="mt", maxw=2000)
    para(d, W // 2, 460, "Opus 5.5", 110, ACC, appear(t, 0.15), anchor="mt", maxw=2000)
    para(d, W // 2, 650, "上位モデル並みの性能で", 58, FG, appear(t, 1.2), anchor="mt", maxw=2000)
    a = appear(t, 2.6, 0.35)
    sc = 0.7 + 0.3 * a
    para(d, W // 2, 760, "約40%安く", int(130 * sc), ACC, a, anchor="mt", maxw=2000)
    para(d, W // 2, 940, "何が変わった？", 52, SUB, appear(t, c[1]), anchor="mt", maxw=2000)
    credit(d, "出典：Anthropic公式発表・各種報道")

def s_tier(d, t, c):
    header(d, t, "01", "Opus 5.5 ってなに？")
    para(d, X0, 390, "Anthropic（Claudeを作っているAI企業）が 2026年9月22日に発表", 32, SUB, appear(t, c[0]), False)
    tiers = [("Mythos / Fable", "最上位モデル", C_FAB, c[2]),
             ("Opus 5.5", "今回の新モデル", ACC, c[0] + 0.4),
             ("Opus 5", "前のモデル", C_OLD, c[1])]
    for r, (name, desc, col, st) in enumerate(tiers):
        a = appear(t, st)
        y = 540 + r * 210
        inset = [60, 0, 60][r] if r != 1 else 0
        box = [X0 + inset, y, X1 - inset, y + 170]
        d.rounded_rectangle(box, radius=24, fill=mix(CARD, a), outline=mix(col, a), width=5)
        para(d, (X0 + X1) // 2, y + 28, name, 60, col, a, anchor="mt", maxw=2000)
        para(d, (X0 + X1) // 2, y + 108, desc, 30, SUB, a, False, anchor="mt", maxw=2000)
        if r < 2:
            para(d, (X0 + X1) // 2, y + 172, "▲", 28, SUB, a, anchor="mt", maxw=2000)
    credit(d)

BENCH = [("コマンドライン作業", "Terminal-Bench 4.0", 52.3, 55.8, 66.4),
         ("開発現場に近い課題", "CursorBench 4.0", 46.6, 51.8, 57.8),
         ("パソコン操作", "OSWorld 2.0", 74.0, 80.7, 81.8)]

def s_bench(d, t, c):
    header(d, t, "02", "性能テストの結果")
    a0 = appear(t, 0.3)
    for i, (name, col) in enumerate([("Opus 5", C_OLD), ("Fable 5.1", C_FAB), ("Opus 5.5", ACC)]):
        x = X0 + i * 270
        d.rectangle([x, 385, x + 30, 415], fill=mix(col, a0))
        d.text((x + 42, 380), name, font=F(30, False), fill=mix(FG, a0))
    for r, (jp, en, o5, f5, o55) in enumerate(BENCH):
        y0 = 460 + r * 250
        st = c[r + 1]
        a = appear(t, st)
        para(d, X0, y0, jp, 44, FG, a)
        d.text((X1, y0 + 14), en, font=F(26, False), fill=mix(SUB, a), anchor="ra")
        g = ease((t - (st + 0.2)) / 1.2)
        for j, (v, col) in enumerate([(o5, C_OLD), (f5, C_FAB), (o55, ACC)]):
            yy = y0 + 72 + j * 50
            w = int(700 * v / 100 * g)
            if g > 0:
                d.rectangle([X0, yy, X0 + max(w, 1), yy + 38], fill=mix(col, clamp(g * 2)))
            if g > 0.05:
                d.text((X0 + w + 14, yy - 2), f"{v * g:.1f}%", font=F(34),
                       fill=mix(ACC if col == ACC else FG, clamp(g * 2)))
    credit(d)

PRICE = [("入力", "$5", "$4", "−20%"), ("出力", "$25", "$20", "−20%"), ("キャッシュ読取", "$0.50", "$0.20", "−60%")]

def s_price(d, t, c):
    header(d, t, "03", "お値段と速さ")
    para(d, X0, 380, "100万トークンあたりのAPI料金", 32, SUB, appear(t, c[0]), False)
    starts = [c[1], c[1] + 0.35, c[2]]
    for r, (name, old, new, pct) in enumerate(PRICE):
        a = appear(t, starts[r])
        y = 450 + r * 175
        card(d, [X0, y, X1, y + 150], a)
        para(d, X0 + 36, y + 22, name, 36, SUB, a)
        para(d, X0 + 36, y + 74, old, 44, C_OLD, a, maxw=2000)
        ow = F(44).getlength(old)
        para(d, X0 + 56 + ow, y + 74, "→", 44, SUB, a, maxw=2000)
        para(d, X0 + 130 + ow, y + 62, new, 60, ACC, appear(t, starts[r] + 0.25), maxw=2000)
        d.text((X1 - 36, y + 75), pct, font=F(56), fill=mix(ACC, appear(t, starts[r] + 0.45)), anchor="ra")
    a = appear(t, c[3])
    d.rounded_rectangle([X0, 990, X1, 1150], radius=24, fill=mix(ACC, a))
    para(d, (X0 + X1) // 2, 1010, "典型的な作業で 約40%安", 50, BG if a > 0.5 else FG, a, anchor="mt", maxw=2000)
    para(d, (X0 + X1) // 2, 1080, "出力スピード 30%以上アップ", 42, BG if a > 0.5 else FG, a, anchor="mt", maxw=2000)
    para(d, X0, 1170, "※キャッシュ読取…同じ前置き文を使い回すときの割安料金", 26, SUB, appear(t, c[2] + 0.8), False)
    credit(d)

def s_cases(d, t, c):
    header(d, t, "04", "大きな仕事に強い")
    items = [("68万行", "のコード移行を", "1日未満で完了（テスター報告）"),
             ("20万行", "の監査・修正が", "Opus 5 の20時間超 → 3時間未満")]
    for r, (big, mid, rest) in enumerate(items):
        a = appear(t, c[r + 1])
        y = 420 + r * 330
        card(d, [X0, y, X1, y + 290], a)
        para(d, X0 + 40, y + 30, big, 110, ACC, a, maxw=2000)
        bw = F(110).getlength(big)
        para(d, X0 + 60 + bw, y + 92, mid, 40, FG, a, maxw=2000)
        para(d, X0 + 40, y + 190, rest, 40, FG, a, False)
    credit(d)

def list_scene(d, t, c, num, title, items, mark="●", mcol=ACC):
    header(d, t, num, title)
    y = 420
    for r, (main, note) in enumerate(items):
        a = appear(t, c[r + 1])
        d.text((X0, y + (1 - a) * 30), mark, font=F(44), fill=mix(mcol, a))
        h = para(d, X0 + 70, y, main, 50, FG, a, maxw=X1 - X0 - 70)
        if note:
            h += 8 + para(d, X0 + 70, y + h + 8, note, 30, SUB, a, False, maxw=X1 - X0 - 70)
        y += h + 60
    credit(d)

def s_writing(d, t, c):
    list_scene(d, t, c, "05", "文章が読みやすく", [
        ("大事な情報を先に書く", None),
        ("専門用語やクセのある\n言い回しを減らす", None),
        ("指定した書き方のルールを守る", "Opus 5 への「読みにくい」という声に対応")])

def s_safety(d, t, c):
    list_scene(d, t, c, "06", "安全性アップ", [
        ("AIの振る舞いテストで\n過去最高スコア", "約2,000の模擬シナリオで検査"),
        ("決められた範囲を\n越えようとする頻度が約85%減", "Opus 5・Mythos 5.1 との比較"),
        ("プロンプトインジェクションに\n強くなった", "Webページなどに紛れ込んだ不正な指示のこと")])

def s_caveats(d, t, c):
    list_scene(d, t, c, "07", "注意点", [
        ("thinking モードは\nオフにできない", "考えてから答えるモードのこと"),
        ("サイバーセキュリティ系の作業の\n多くは Opus 4.8 に振り替え", "安全対策のため"),
        ("「トークン消費が多い」という\n第三者の指摘も", "公式の「約40%安」とは測り方が違う可能性 → 要検証")],
        mark="!", mcol=WARN)
    # 出典を差し替え
    d.rectangle([X0, 1495, W, 1570], fill=BG)
    credit(d, "出典：Anthropic公式／Artificial Analysis（Wccftech経由）")

def s_end(d, t, c):
    para(d, W // 2, 480, "次に来るのは", 50, SUB, appear(t, c[0]), anchor="mt", maxw=2000)
    para(d, W // 2, 580, "Sonnet 5.5", 96, FG, appear(t, c[0] + 0.3), anchor="mt", maxw=2000)
    para(d, W // 2, 710, "Haiku 5.5", 96, FG, appear(t, c[0] + 0.5), anchor="mt", maxw=2000)
    para(d, W // 2, 870, "数週間以内に登場予定", 52, ACC, appear(t, c[0] + 1.0), anchor="mt", maxw=2000)
    credit(d, "出典：Anthropic公式発表（2026/9/22）／BGM：自作")

FUNCS = [s_hook, s_tier, s_bench, s_price, s_cases, s_writing, s_safety, s_caveats, s_end]

# ---------- タイムライン・合成 ----------
def build_timeline():
    scenes, tg = [], 0.0
    for s, durs in enumerate(DUR):
        pre = 0.3 if s == 0 else PRE
        cues, t = [], pre
        for du in durs:
            cues.append(t); t += du + GAP
        length = t - GAP + (1.2 if s == len(DUR) - 1 else POST)
        scenes.append({"start": tg, "len": length, "cues": cues, "durs": durs}); tg += length
    return scenes, tg

def render_frame(s, sc, t):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    FUNCS[s](d, t, sc["cues"])
    subtitle(d, t, sc, s)
    fade = min(clamp(t / 0.2) if s > 0 else 1.0, clamp((sc["len"] - t) / 0.25))
    if fade < 1:
        img = Image.blend(Image.new("RGB", (W, H), BG), img, fade)
    return img

def build_voice_track(scenes, total, sr=24000, out="voice_track_v.wav"):
    buf = np.zeros(int((total + 1) * sr), dtype=np.float32)
    for s, sc in enumerate(scenes):
        for i, c in enumerate(sc["cues"]):
            with wave.open(f"{VOICE}/{s}_{i}.wav") as w:
                x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
            p = int((sc["start"] + c) * sr); buf[p:p + len(x)] += x
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(np.clip(buf[:int(total * sr)], -32768, 32767).astype(np.int16).tobytes())

FILT = ("[1:a]aresample=44100,pan=stereo|c0=c0|c1=c0,volume=1.25,asplit=2[v1][v2];"
        "[2:a]volume=0.2[bg];"
        "[bg][v1]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[bgd];"
        "[bgd][v2]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]")

def main(out):
    scenes, total = build_timeline()
    print(f"total {total:.1f}s")
    build_voice_track(scenes, total)
    subprocess.run(["python3", "bgm.py", f"{total:.3f}", "bgm_v.wav"], check=True)
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "fast",
                          "-pix_fmt", "yuv420p", "-crf", "21", "video_only_v.mp4"], stdin=subprocess.PIPE)
    for s, sc in enumerate(scenes):
        for i in range(int(round(sc["len"] * FPS))):
            p.stdin.write(render_frame(s, sc, i / FPS).tobytes())
    p.stdin.close(); p.wait()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "video_only_v.mp4", "-i", "voice_track_v.wav",
                    "-i", "bgm_v.wav", "-filter_complex", FILT, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True)

if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/outputs/opus55_tiktok_vertical.mp4")

# ---- 分割レンダリング（1回の実行時間制限対策） ----
def render_scene(s, out):
    scenes, _ = build_timeline(); sc = scenes[s]
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "fast",
                          "-pix_fmt", "yuv420p", "-crf", "21", out], stdin=subprocess.PIPE)
    for i in range(int(round(sc["len"] * FPS))):
        p.stdin.write(render_frame(s, sc, i / FPS).tobytes())
    p.stdin.close(); p.wait()

def finish(out):
    scenes, total = build_timeline()
    build_voice_track(scenes, total)
    subprocess.run(["python3", "bgm.py", f"{total:.3f}", "bgm_v.wav"], check=True)
    open("segs.txt", "w").write("".join(f"file 'seg_{s}.mp4'\n" for s in range(len(scenes))))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "segs.txt",
                    "-c", "copy", "video_only_v.mp4"], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "video_only_v.mp4", "-i", "voice_track_v.wav",
                    "-i", "bgm_v.wav", "-filter_complex", FILT, "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out], check=True)

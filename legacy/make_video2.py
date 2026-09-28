import json, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw
from make_video import (W, H, FPS, BG, FG, SUB, ACC, C_OLD, C_FAB, WARN, F,
                        clamp, ease, mix, appear, text, header, BENCH, PRICE, CASES)
from narration import N

PRE, GAP, POST = 0.7, 0.35, 0.9
DUR = json.load(open("voice/durations.json"))

# ---------- タイムライン計算 ----------
def build_timeline():
    scenes = []
    t_global = 0.0
    for s, durs in enumerate(DUR):
        pre = 1.0 if s == 0 else PRE
        cues, t = [], pre
        for d in durs:
            cues.append(t); t += d + GAP
        length = t - GAP + POST
        scenes.append({"start": t_global, "len": length, "cues": cues, "durs": durs})
        t_global += length
    return scenes, t_global

def top_right(d, src):
    d.text((W - 40, 36), src, font=F(15, False), fill=SUB, anchor="rs")
    d.text((W - 40, 58), "VOICEVOX:ずんだもん", font=F(15, False), fill=SUB, anchor="rs")

SRC = "出典：Anthropic公式発表（2026/9/22）"

# ---------- 字幕 ----------
def wrap(s, font, maxw):
    lines, cur = [], ""
    for ch in s:
        if font.getlength(cur + ch) > maxw:
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur: lines.append(cur)
    return lines

def subtitle(d, t, sc, s):
    for i, (c, du) in enumerate(zip(sc["cues"], sc["durs"])):
        if c - 0.05 <= t < c + du + GAP * 0.8:
            f = F(24)
            ls = wrap(N[s][i][0], f, W - 200)
            lh, pad = 34, 10
            h = lh * len(ls) + pad * 2
            y0 = 708 - h
            d.rounded_rectangle([80, y0, W - 80, 708], radius=10, fill=(38, 37, 34))
            for k, l in enumerate(ls):
                d.text((W // 2, y0 + pad + k * lh + lh // 2), l, font=f, fill=FG, anchor="mm")
            return

# ---------- シーン ----------
def s_title(d, t, c):
    text(d, (W // 2, 220), "Claude Opus 5.5", 84, ACC, appear(t, 0.2, 0.8), anchor="mm")
    text(d, (W // 2, 320), "で、何が変わった？", 52, FG, appear(t, c[1]), anchor="mm")
    text(d, (W // 2, 410), "2026年9月22日リリース ／ Opus 5 との比較", 28, SUB, appear(t, c[1] + 0.6), False, anchor="mm")
    top_right(d, "出典：Anthropic公式発表・各種報道")

def s_summary(d, t, c):
    header(d, t, "01", "ひとことで言うと")
    text(d, (W // 2, 310), "上位モデル Fable 5.1 並みの性能を", 44, FG, appear(t, c[1]), anchor="mm")
    text(d, (W // 2, 390), "Opus 5 より 約40% 安く", 60, ACC, appear(t, c[2]), anchor="mm")
    text(d, (W // 2, 500), "※ Fable 5.1 … Opus より上の「Mythos」ティアのモデル", 22, SUB, appear(t, c[3]), False, anchor="mm")
    top_right(d, SRC)

def s_bench(d, t, c):
    header(d, t, "02", "性能：ベンチマーク（性能テスト）")
    lx = 760
    for i, (name, col) in enumerate([("Opus 5", C_OLD), ("Fable 5.1", C_FAB), ("Opus 5.5", ACC)]):
        a = appear(t, 0.3)
        d.rectangle([lx + i * 170, 192, lx + i * 170 + 22, 214], fill=mix(col, a))
        text(d, (lx + i * 170 + 32, 188), name, 22, FG, a, False, dy=False)
    for r, (name, desc, o5, f5, o55) in enumerate(BENCH):
        y0 = 240 + r * 130
        st = c[r + 1]
        a = appear(t, st)
        text(d, (80, y0), name, 28, FG, a)
        text(d, (80, y0 + 38), desc, 18, SUB, a, False)
        g = ease((t - (st + 0.3)) / 1.4)
        for j, (v, col) in enumerate([(o5, C_OLD), (f5, C_FAB), (o55, ACC)]):
            yy = y0 + 4 + j * 30
            x0 = 520
            w = int(640 * v / 100 * g)
            if g > 0:
                d.rectangle([x0, yy, x0 + max(w, 1), yy + 22], fill=mix(col, clamp(g * 2)))
            if g > 0.05:
                d.text((x0 + w + 10, yy - 3), f"{v * g:.1f}%", font=F(20),
                       fill=mix(ACC if col == ACC else FG, clamp(g * 2)))
    top_right(d, SRC)

def s_price(d, t, c):
    header(d, t, "03", "コストと速度")
    text(d, (80, 200), "100万トークンあたりの料金（API）", 24, SUB, appear(t, c[0] + 0.3), False)
    starts = [c[1], c[1] + 0.4, c[2]]
    for r, (name, old, new, pct) in enumerate(PRICE):
        y = 250 + r * 80
        st = starts[r]
        fmt = lambda v: f"${v:.2f}" if v < 1 else f"${v:g}"
        text(d, (80, y), name, 32, FG, appear(t, st))
        text(d, (400, y), fmt(old), 32, C_OLD, appear(t, st))
        text(d, (540, y), "→", 32, SUB, appear(t, st))
        text(d, (610, y), fmt(new), 40, ACC, appear(t, st + 0.3))
        text(d, (800, y + 4), pct, 32, ACC, appear(t, st + 0.5))
    text(d, (80, 500), "典型的な作業で 約40%安 ／ 出力速度 30%以上アップ", 32, FG, appear(t, c[3]))
    text(d, (80, 560), "※ キャッシュ読取 … 同じ前置き文を使い回すときの割安料金。エージェント作業のコストの大半を占める",
         19, SUB, appear(t, c[2] + 0.8), False)
    top_right(d, SRC)

def s_cases(d, t, c):
    header(d, t, "04", "長くて大きい仕事に強い")
    for r, (big, rest) in enumerate(CASES):
        y = 230 + r * 110
        a = appear(t, c[r + 1])
        d.rectangle([80, y - 5, 86, y + 60], fill=mix(ACC, a))
        text(d, (110, y), big, 48, ACC, a)
        bw = d.textlength(big, font=F(48))
        text(d, (120 + bw, y + 16), rest, 28, FG, a, False)
    text(d, (80, 570), "※ HAProxy … Webアクセスを複数サーバーに振り分ける有名なソフト", 19, SUB, appear(t, c[3] + 0.8), False)
    top_right(d, SRC)

def bullet_scene(d, t, c, num, title, items, gap=110):
    header(d, t, num, title)
    for r, (main, note) in enumerate(items):
        y = 230 + r * gap
        a = appear(t, c[r + 1])
        d.ellipse([84, y + 14, 100, y + 30], fill=mix(ACC, a))
        text(d, (120, y), main, 34, FG, a)
        if note: text(d, (120, y + 48), note, 19, SUB, a, False)
    top_right(d, SRC)

def s_writing(d, t, c):
    bullet_scene(d, t, c, "05", "文章がわかりやすくなった", [
        ("いちばん大事な情報を先に書く", None),
        ("専門用語や独特な言い回しを減らす", None),
        ("指定した「書き方ルール」に従う", "Opus 5 への「読みにくい」というフィードバックへの対応")])

def s_safety(d, t, c):
    bullet_scene(d, t, c, "06", "安全性", [
        ("自動行動監査で過去最高スコア", "約2,000の模擬シナリオでAIの振る舞いを検査するテスト"),
        ("決められた境界を越えようとする頻度 約85%減", "Opus 5・Mythos 5.1 との比較"),
        ("プロンプトインジェクションへの耐性アップ", "Webページなど外部データに紛れ込んだ不正な指示のこと")], gap=115)

def s_caveats(d, t, c):
    header(d, t, "07", "注意点")
    items = [("thinking（考えてから答えるモード）はオフにできない", None),
             ("サイバーセキュリティ系の作業の多くは Opus 4.8 に振り替え", "安全対策（セーフガード）のため"),
             ("第三者評価では「1タスクあたりのトークン消費が多い」との指摘も",
              "公式の「約40%安い」とは測り方が違う可能性あり → 要検証")]
    for r, (main, note) in enumerate(items):
        y = 230 + r * 115
        a = appear(t, c[r + 1])
        text(d, (84, y), "!", 34, WARN, a)
        text(d, (120, y), main, 30, FG, a)
        if note: text(d, (120, y + 46), note, 19, SUB, a, False)
    top_right(d, "出典：Anthropic公式発表／Artificial Analysis（Wccftech経由）")

def s_end(d, t, c):
    text(d, (W // 2, 240), "次は Sonnet 5.5・Haiku 5.5", 48, FG, appear(t, c[0]), anchor="mm")
    text(d, (W // 2, 320), "数週間以内に登場予定", 36, ACC, appear(t, c[0] + 0.8), anchor="mm")
    text(d, (W // 2, 440), "音声：VOICEVOX:ずんだもん　／　BGM：numpy で自作", 22, SUB, appear(t, c[1]), False, anchor="mm")
    text(d, (W // 2, 480), "映像：Python（Pillow）＋ ffmpeg", 22, SUB, appear(t, c[1] + 0.3), False, anchor="mm")

FUNCS = [s_title, s_summary, s_bench, s_price, s_cases, s_writing, s_safety, s_caveats, s_end]

def render_frame(s, sc, t):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    FUNCS[s](d, t, sc["cues"])
    subtitle(d, t, sc, s)
    fade = min(clamp(t / 0.3), clamp((sc["len"] - t) / 0.4))
    if fade < 1:
        img = Image.blend(Image.new("RGB", (W, H), BG), img, fade)
    return img

def build_voice_track(scenes, total, sr=24000):
    out = np.zeros(int((total + 1) * sr), dtype=np.float32)
    for s, sc in enumerate(scenes):
        for i, c in enumerate(sc["cues"]):
            with wave.open(f"voice/{s}_{i}.wav") as w:
                assert w.getframerate() == sr
                x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
            p = int((sc["start"] + c) * sr)
            out[p:p + len(x)] += x
    out = out[:int(total * sr)]
    with wave.open("voice_track.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(np.clip(out, -32768, 32767).astype(np.int16).tobytes())

def main(out):
    scenes, total = build_timeline()
    print(f"total {total:.1f}s")
    build_voice_track(scenes, total)
    subprocess.run(["python3", "bgm.py", f"{total:.3f}", "bgm.wav"], check=True)
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                          "-pix_fmt", "yuv420p", "-crf", "20", "video_only.mp4"], stdin=subprocess.PIPE)
    for s, sc in enumerate(scenes):
        for i in range(int(round(sc["len"] * FPS))):
            p.stdin.write(render_frame(s, sc, i / FPS).tobytes())
    p.stdin.close(); p.wait()
    # 声 + BGM（声が鳴っている間はBGMを自動で下げる：サイドチェインコンプレッサー）
    filt = ("[1:a]aresample=44100,pan=stereo|c0=c0|c1=c0,volume=1.25,asplit=2[v1][v2];"
            "[2:a]volume=0.22[bg];"
            "[bg][v1]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[bgd];"
            "[bgd][v2]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "video_only.mp4", "-i", "voice_track.wav",
                    "-i", "bgm.wav", "-filter_complex", filt, "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out],
                   check=True)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        scenes, _ = build_timeline()
        s = int(sys.argv[2]); sc = scenes[s]
        render_frame(s, sc, float(sys.argv[3])).save(sys.argv[4])
    else:
        main(sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/outputs/opus55_whats_new_zundamon.mp4")

"""シーン型ごとの描画。RENDERERS[type](d, t, sc, cues, credit_text)"""
from draw import (W, X0, X1, BG, FG, SUB, ACC, WARN, CARD, GRAY, PALETTE,
                  F, clamp, ease, mix, appear, para, header, card, credit)

CX = (X0 + X1) // 2


def at(c, x):
    """要素 x を出す時刻（cue 番目のセリフ開始 + delay）"""
    return c[x.cue] + x.delay


def hook(d, t, sc, c, cr):
    n = len(sc.title)
    y = 330 + (2 - n) * 65                     # 1行なら少し下げて中央寄せ
    for k, line in enumerate(sc.title):
        para(d, W // 2, y + k * 130, line, 110, ACC, appear(t, 0.15 * k), anchor="mt", maxw=2000)
    para(d, W // 2, 650, sc.lead, 58, FG, appear(t, 1.2), anchor="mt", maxw=2000)
    a = appear(t, 2.6, 0.35)
    para(d, W // 2, 760, sc.big, int(130 * (0.7 + 0.3 * a)), ACC, a, anchor="mt", maxw=2000)
    if sc.ask:
        para(d, W // 2, 940, sc.ask.text, 52, SUB, appear(t, at(c, sc.ask)), anchor="mt", maxw=2000)
    credit(d, cr)


def list_(d, t, sc, c, cr):
    mark, mcol = ("!", WARN) if sc.style == "warn" else ("●", ACC)
    header(d, t, sc.num, sc.title)
    y = 420
    for it in sc.items:
        a = appear(t, at(c, it))
        d.text((X0, y + (1 - a) * 30), mark, font=F(44), fill=mix(mcol, a))
        h = para(d, X0 + 70, y, it.main, 50, FG, a, maxw=X1 - X0 - 70)
        if it.note:
            h += 8 + para(d, X0 + 70, y + h + 8, it.note, 30, SUB, a, False, maxw=X1 - X0 - 70)
        y += h + 60
    credit(d, cr)


def tier(d, t, sc, c, cr):
    header(d, t, sc.num, sc.title)
    if sc.intro:
        para(d, X0, 390, sc.intro.text, 32, SUB, appear(t, at(c, sc.intro)), False)
    last = len(sc.tiers) - 1
    for r, tr in enumerate(sc.tiers):
        a, col = appear(t, at(c, tr)), PALETTE[tr.color]
        y = 540 + r * 210
        inset = 0 if tr.highlight else 60
        d.rounded_rectangle([X0 + inset, y, X1 - inset, y + 170], radius=24,
                            fill=mix(CARD, a), outline=mix(col, a), width=5)
        para(d, CX, y + 28, tr.name, 60, col, a, anchor="mt", maxw=2000)
        para(d, CX, y + 108, tr.desc, 30, SUB, a, False, anchor="mt", maxw=2000)
        if r < last:
            para(d, CX, y + 172, "▲", 28, SUB, a, anchor="mt", maxw=2000)
    credit(d, cr)


def bars(d, t, sc, c, cr):
    header(d, t, sc.num, sc.title)
    a0 = appear(t, 0.3)
    for i, s in enumerate(sc.legend):
        x = X0 + i * 270
        d.rectangle([x, 385, x + 30, 415], fill=mix(PALETTE[s.color], a0))
        d.text((x + 42, 380), s.name, font=F(30, False), fill=mix(FG, a0))
    for r, row in enumerate(sc.rows):
        y0, st = 460 + r * 250, at(c, row)
        a = appear(t, st)
        para(d, X0, y0, row.label, 44, FG, a)
        if row.sublabel:
            d.text((X1, y0 + 14), row.sublabel, font=F(26, False), fill=mix(SUB, a), anchor="ra")
        g = ease((t - (st + 0.2)) / 1.2)       # 棒は 0.2秒遅れて 1.2秒で伸びる
        for j, (v, s) in enumerate(zip(row.values, sc.legend)):
            col, yy = PALETTE[s.color], y0 + 72 + j * 50
            w = int(700 * v / sc.max * g)
            if g > 0:
                d.rectangle([X0, yy, X0 + max(w, 1), yy + 38], fill=mix(col, clamp(g * 2)))
            if g > 0.05:
                d.text((X0 + w + 14, yy - 2), f"{v * g:.1f}{sc.unit}", font=F(34),
                       fill=mix(ACC if s.color == "acc" else FG, clamp(g * 2)))
    credit(d, cr)


def price(d, t, sc, c, cr):
    header(d, t, sc.num, sc.title)
    if sc.intro:
        para(d, X0, 380, sc.intro.text, 32, SUB, appear(t, at(c, sc.intro)), False)
    for r, row in enumerate(sc.rows):
        st = at(c, row)
        a = appear(t, st)
        y = 450 + r * 175
        card(d, [X0, y, X1, y + 150], a)
        para(d, X0 + 36, y + 22, row.name, 36, SUB, a)
        para(d, X0 + 36, y + 74, row.old, 44, GRAY, a, maxw=2000)
        ow = F(44).getlength(row.old)
        para(d, X0 + 56 + ow, y + 74, "→", 44, SUB, a, maxw=2000)
        para(d, X0 + 130 + ow, y + 62, row.new, 60, ACC, appear(t, st + 0.25), maxw=2000)
        d.text((X1 - 36, y + 75), row.change, font=F(56), fill=mix(ACC, appear(t, st + 0.45)), anchor="ra")
    if sc.summary:
        a = appear(t, at(c, sc.summary))
        d.rounded_rectangle([X0, 990, X1, 1150], radius=24, fill=mix(ACC, a))
        for k, (line, size) in enumerate(zip(sc.summary.lines, (50, 42))):
            para(d, CX, 1010 + k * 70, line, size, BG if a > 0.5 else FG, a, anchor="mt", maxw=2000)
    if sc.note:
        para(d, X0, 1170, sc.note.text, 26, SUB, appear(t, at(c, sc.note)), False)
    credit(d, cr)


def cards(d, t, sc, c, cr):
    header(d, t, sc.num, sc.title)
    for r, it in enumerate(sc.items):
        a = appear(t, at(c, it))
        y = 420 + r * 330
        card(d, [X0, y, X1, y + 290], a)
        para(d, X0 + 40, y + 30, it.big, 110, ACC, a, maxw=2000)
        bw = F(110).getlength(it.big)
        para(d, X0 + 60 + bw, y + 92, it.mid, 40, FG, a, maxw=2000)
        para(d, X0 + 40, y + 190, it.rest, 40, FG, a, False)
    credit(d, cr)


def end(d, t, sc, c, cr):
    for it in sc.items:
        para(d, W // 2, it.y, it.text, it.size, PALETTE[it.color], appear(t, at(c, it)), anchor="mt", maxw=2000)
    credit(d, cr)


RENDERERS = {"hook": hook, "list": list_, "tier": tier, "bars": bars,
             "price": price, "cards": cards, "end": end}

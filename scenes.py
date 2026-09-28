"""シーン型ごとの描画。RENDERERS[type](d, t, sc, cues, credit_text)"""
from draw import W, X0, X1, FG, SUB, ACC, WARN, F, mix, appear, para, header, credit


def hook(d, t, sc, c, cr):
    n = len(sc.title)
    y = 330 + (2 - n) * 65                     # 1行なら少し下げて中央寄せ
    for k, line in enumerate(sc.title):
        para(d, W // 2, y + k * 130, line, 110, ACC, appear(t, 0.15 * k), anchor="mt", maxw=2000)
    para(d, W // 2, 650, sc.lead, 58, FG, appear(t, 1.2), anchor="mt", maxw=2000)
    a = appear(t, 2.6, 0.35)
    para(d, W // 2, 760, sc.big, int(130 * (0.7 + 0.3 * a)), ACC, a, anchor="mt", maxw=2000)
    if sc.ask:
        para(d, W // 2, 940, sc.ask.text, 52, SUB, appear(t, c[sc.ask.cue]), anchor="mt", maxw=2000)
    credit(d, cr)


def list_(d, t, sc, c, cr):
    mark, mcol = ("!", WARN) if sc.style == "warn" else ("●", ACC)
    header(d, t, sc.num, sc.title)
    y = 420
    for it in sc.items:
        a = appear(t, c[it.cue])
        d.text((X0, y + (1 - a) * 30), mark, font=F(44), fill=mix(mcol, a))
        h = para(d, X0 + 70, y, it.main, 50, FG, a, maxw=X1 - X0 - 70)
        if it.note:
            h += 8 + para(d, X0 + 70, y + h + 8, it.note, 30, SUB, a, False, maxw=X1 - X0 - 70)
        y += h + 60
    credit(d, cr)


RENDERERS = {"hook": hook, "list": list_}

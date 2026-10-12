"""Render a Layout in the coloured style of reference.png: thick grey walls, cream floors,
brown door swings, blue windows, green dimension lines, 'Main Entrance' marker."""
from __future__ import annotations

import math
import os

import matplotlib
from PIL import Image, ImageDraw, ImageFont

from layout import E, P, Layout

SS = 2
C = dict(bg="#ffffff", wall="#7f7f7f", edge="#575757", floor="#f6f5ea", door="#8b3a1c",
         glass="#2d7dd2", glassfill="#e3f1fb", dim="#1f8a3c", text="#1b1b1b", sub="#6b6b6b")
_FD = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")


def _f(px, bold=False):
    return ImageFont.truetype(os.path.join(_FD, "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"), int(px * SS))


def _label(text, font, color, rot=False):
    bb = font.getbbox(text)
    im = Image.new("RGBA", (bb[2] + 6, bb[3] + 6), (255, 255, 255, 0))
    ImageDraw.Draw(im).text((0, 0), text, font=font, fill=color)
    im = im.crop(im.getbbox() or (0, 0, 1, 1))
    return im.rotate(90, expand=True) if rot else im


def _zones(r, span):
    out = []
    for o in r.doors:
        if o.kind == "open":
            continue
        p0, p1, face, h, inw, _, _ = span(r, o)
        out.append((p0, p1, face, face + inw * o.width, h))
    return out


def render(lay: Layout, path: str):
    W, H = lay.outer_w, lay.outer_h
    ent_side = lay.entrance[1] if lay.entrance else None
    s = min(36.0, 1250 / W, 1450 / H) * SS
    ml, mr, mt, mb = 190 * SS, (330 if ent_side == "E" else 210) * SS, 170 * SS, (420 if ent_side == "S" else 250) * SS
    cw, ch = int(W * s + ml + mr), int(H * s + mt + mb)
    X = lambda v: ml + v * s
    Y = lambda v: mt + v * s
    img = Image.new("RGB", (cw, ch), C["bg"])
    d = ImageDraw.Draw(img)

    # walls = whole footprint, rooms are cut out of it
    d.rectangle([X(0), Y(0), X(W), Y(H)], fill=C["wall"], outline=C["edge"], width=2 * SS)
    for r in lay.rooms:
        d.rectangle([X(r.x), Y(r.y), X(r.x2), Y(r.y2)], fill=C["floor"], outline=C["edge"], width=SS)

    def span(r, o):
        """(p0, p1, face coordinate, horizontal?, inward sign, cut rect) for an opening of room r."""
        if o.wall == "N": p0, face, h, inw = r.x + o.offset, r.y, True, 1
        elif o.wall == "S": p0, face, h, inw = r.x + o.offset, r.y2, True, -1
        elif o.wall == "W": p0, face, h, inw = r.y + o.offset, r.x, False, 1
        else: p0, face, h, inw = r.y + o.offset, r.x2, False, -1
        p1 = p0 + o.width
        out0, out1 = (face - o.thick, face) if o.wall in "NW" else (face, face + o.thick)
        rect = [X(p0), Y(out0), X(p1), Y(out1)] if h else [X(out0), Y(p0), X(out1), Y(p1)]
        return p0, p1, face, h, inw, rect, (out0, out1)

    # openings: wall cuts first
    for r in lay.rooms:
        for o in r.doors:
            p0, p1, face, h, inw, rect, _ = span(r, o)
            d.rectangle(rect, fill=C["floor"])
        for o in r.windows:
            p0, p1, face, h, inw, rect, (a, b) = span(r, o)
            d.rectangle(rect, fill=C["glassfill"], outline=C["glass"], width=2 * SS)
            m = (a + b) / 2
            ln = [(X(p0), Y(m)), (X(p1), Y(m))] if h else [(X(m), Y(p0)), (X(m), Y(p1))]
            d.line(ln, fill=C["glass"], width=2 * SS)

    # door leaves + swing arcs (hinge at the opening end nearest a room corner)
    for r in lay.rooms:
        for o in r.doors:
            if o.kind == "open":
                continue
            p0, p1, face, h, inw, _, _ = span(r, o)
            L = r.w if o.wall in "NS" else r.h
            hinge_start = o.offset <= L - o.offset - o.width
            hp, op = (p0, p1) if hinge_start else (p1, p0)
            sg = 1 if op > hp else -1
            R = o.width
            pt = (lambda al, out: (X(al), Y(face + out * inw))) if h else (lambda al, out: (X(face + out * inw), Y(al)))
            arc = [pt(hp + sg * R * math.cos(t), R * math.sin(t)) for t in [i * math.pi / 2 / 28 for i in range(29)]]
            d.line(arc, fill=C["door"], width=2 * SS)
            d.line([pt(hp, 0), pt(hp, R)], fill=C["door"], width=5 * SS)

    # dimensions
    def arrow(p, q, hsz=7 * SS, one=False):
        d.line([p, q], fill=C["dim"], width=2 * SS)
        ang = math.atan2(q[1] - p[1], q[0] - p[0])
        for tip, a in (((q, ang + math.pi),) if one else ((p, ang), (q, ang + math.pi))):
            pts = [tip, (tip[0] + hsz * math.cos(a + .4), tip[1] + hsz * math.sin(a + .4)),
                   (tip[0] + hsz * math.cos(a - .4), tip[1] + hsz * math.sin(a - .4))]
            d.polygon(pts, fill=C["dim"])

    def dim(p, q, text, horiz, side):
        arrow(p, q)
        lab = _label(text, _f(17), C["dim"], rot=not horiz)
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        off = 16 * SS
        if horiz:
            pos = (mx - lab.width / 2, my + side * off - lab.height / 2)
        else:
            pos = (mx + side * off - lab.width / 2, my - lab.height / 2)
        img.paste(lab, (int(pos[0]), int(pos[1])), lab)

    fmt = lambda v: f"{v:.1f}'"
    dim((X(0), Y(-3)), (X(W), Y(-3)), fmt(W), True, -1)
    dim((X(-3), Y(0)), (X(-3), Y(H)), fmt(H), False, -1)
    rx = W + (8.5 if ent_side == "E" else 3)
    for r in sorted((r for r in lay.rooms if abs(r.x2 - (W - E)) < 1e-6 and r.kind != "passage"), key=lambda r: r.y):
        dim((X(rx), Y(r.y)), (X(rx), Y(r.y2)), fmt(r.h), False, 1)
    by = H + (6.5 if ent_side == "S" else 3)
    for r in sorted((r for r in lay.rooms if abs(r.y2 - (H - E)) < 1e-6), key=lambda r: r.x):
        dim((X(r.x), Y(by)), (X(r.x2), Y(by)), fmt(r.w), True, 1)
    dim((X(0), Y(by + 3)), (X(W), Y(by + 3)), fmt(W), True, 1)

    # main entrance marker
    if lay.entrance:
        r = next(q for q in lay.rooms if q.name == lay.entrance[0])
        o = next(o for o in r.doors if o.kind == "entrance")
        c = (r.x if o.wall in "NS" else r.y) + o.offset + o.width / 2
        if o.wall == "S":
            arrow((X(c), Y(H + 3.4)), (X(c), Y(H + 1.0)), 10 * SS, True)
            lab = _label("Main Entrance", _f(16, True), C["dim"])
            img.paste(lab, (int(X(c) - lab.width / 2), int(Y(H + 3.6))), lab)
        elif o.wall == "E":
            arrow((X(W + 3.4), Y(c)), (X(W + 1.0), Y(c)), 10 * SS, True)
            lab = _label("Main Entrance", _f(16, True), C["dim"], rot=True)
            img.paste(lab, (int(X(W + 4.3)), int(Y(c) - lab.height / 2)), lab)

    # room labels (kept clear of door swings by shifting away from them)
    for r in lay.rooms:
        if r.kind == "passage":
            continue
        lines = [_label(r.label or r.name, _f(19, True), C["text"]),
                 _label(f"{r.w:.1f}' x {r.h:.1f}'", _f(16), C["text"]),
                 _label(f"{r.area} sq ft", _f(15), C["sub"])]
        gap = 5 * SS
        tot = sum(i.height for i in lines) + gap * 2
        bw, bh = max(i.width for i in lines), tot
        # door-swing footprints (feet) inside this room
        zones = []
        for o in r.doors:
            if o.kind == "open":
                continue
            p0, p1, face, h, inw, _, _ = span(r, o)
            R = o.width
            zones.append((p0, p1, face, face + inw * R) if h else (face, face + inw * R, p0, p1))
        zones = [(min(z[0], z[1]), max(z[0], z[1]), min(z[2], z[3]), max(z[2], z[3])) for z in zones] if False else \
                [((min(p0, p1), max(p0, p1), min(f0, f1), max(f0, f1)) if hz else (min(f0, f1), max(f0, f1), min(p0, p1), max(p0, p1)))
                 for (p0, p1, f0, f1, hz) in _zones(r, span)]
        best = None
        for fy in (.5, .4, .6, .3, .7, .2, .8, .86, .14):
            for fx in (.5, .4, .6, .3, .7, .25, .75):
                gx, gy = r.x + r.w * fx, r.y + r.h * fy
                bx0, bx1 = gx - bw / s / 2 - .15, gx + bw / s / 2 + .15
                by0, by1 = gy - bh / s / 2 - .15, gy + bh / s / 2 + .15
                if bx0 < r.x or bx1 > r.x2 or by0 < r.y or by1 > r.y2:
                    continue
                if any(not (bx1 < z[0] or bx0 > z[1] or by1 < z[2] or by0 > z[3]) for z in zones):
                    continue
                best = (gx, gy); break
            if best: break
        gx, gy = best or ((r.x + r.x2) / 2, (r.y + r.y2) / 2)
        cx, cy = X(gx), Y(gy)
        yy = cy - tot / 2
        for im in lines:
            img.paste(im, (int(cx - im.width / 2), int(yy)), im)
            yy += im.height + gap

    img = img.resize((cw // SS, ch // SS), Image.LANCZOS)
    img.save(path)
    return path

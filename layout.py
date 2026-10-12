"""Requirements (dataset JSON schema) -> room layout with correct proportions and wall-aware doors.

Model: all rooms are rectangles given by their INTERIOR size (feet). Exterior walls are E thick,
partitions are P thick, so rooms are separated by exactly P and the footprint is
E + interior + partitions + E. Dimensions printed on the plan are interior dimensions.
Coordinates: x right, y down.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

EPS = 1e-6
E, P = 1.0, 0.5          # exterior / partition wall thickness (ft)
DOOR_W = 3.0

MIN_AREA = {"living": 100, "master": 100, "bedroom": 90, "kitchen": 60, "toilet": 25,
            "foyer": 40, "balcony": 20}
MIN_DIM = {"living": 9, "master": 9, "bedroom": 9, "kitchen": 6, "toilet": 4, "foyer": 5, "balcony": 3.5}
NEEDS_WINDOW = {"living", "master", "bedroom", "kitchen", "toilet"}


@dataclass
class Opening:
    wall: str            # N/S/E/W of the owning room
    offset: float        # ft from start of that wall (left for N/S, top for E/W)
    width: float
    kind: str = "door"   # door | open (cased opening) | window | entrance
    thick: float = P     # wall thickness being cut


@dataclass
class Room:
    name: str
    kind: str            # living master bedroom kitchen toilet foyer balcony passage
    x: float
    y: float
    w: float
    h: float
    label: str | None = None
    doors: list = field(default_factory=list)
    windows: list = field(default_factory=list)

    x2 = property(lambda s: s.x + s.w)
    y2 = property(lambda s: s.y + s.h)
    area = property(lambda s: round(s.w * s.h))


@dataclass
class Layout:
    rooms: list
    outer_w: float
    outer_h: float
    entrance: tuple | None = None      # (room name, wall)
    notes: list = field(default_factory=list)
    requirements: dict = field(default_factory=dict)

    total_area = property(lambda s: round(s.outer_w * s.outer_h))


# ------------------------------------------------------------ requirements -> spec
def spec_from_requirements(req: dict) -> dict:
    r = req.get("rooms", {}) or {}
    notes = []
    bhk = req.get("bhk")
    if not bhk:
        bhk = 1 + int(r.get("bedroom_count") or 0)
    if (req.get("type") or "").lower() == "studio":
        bhk = 1
        notes.append("Studio mapped to the 1BHK template.")
    if bhk > 3:
        notes.append(f"{bhk}BHK requested - templates support up to 3BHK, using 3BHK.")
        bhk = 3
    bhk = max(1, int(bhk))
    area = req.get("area_sqft")
    scale = 1.0
    if area:
        base = {1: 616, 2: 750, 3: 1170}[bhk]
        scale = min(1.35, max(0.8, math.sqrt(float(area) / base)))
    spec = {"bhk": bhk, "balcony": bool(r.get("balcony")), "dining": bool(r.get("dining")),
            "scale": scale, "notes": notes}
    for k in ("study", "puja", "utility", "portico"):
        if r.get(k):
            notes.append(f"'{k}' requested but this template set has no dedicated {k} room - not placed.")
    return spec


# ------------------------------------------------------------ geometry helpers
def _ov(a0, a1, b0, b1):
    return min(a1, b1) - max(a0, b0)


def shared_edge(a: Room, b: Room):
    """Wall of `a` facing `b` across one partition: (wall, lo, hi) in global coords."""
    if abs(b.x - a.x2 - P) < EPS and _ov(a.y, a.y2, b.y, b.y2) > EPS:
        return "E", max(a.y, b.y), min(a.y2, b.y2)
    if abs(a.x - b.x2 - P) < EPS and _ov(a.y, a.y2, b.y, b.y2) > EPS:
        return "W", max(a.y, b.y), min(a.y2, b.y2)
    if abs(b.y - a.y2 - P) < EPS and _ov(a.x, a.x2, b.x, b.x2) > EPS:
        return "S", max(a.x, b.x), min(a.x2, b.x2)
    if abs(a.y - b.y2 - P) < EPS and _ov(a.x, a.x2, b.x, b.x2) > EPS:
        return "N", max(a.x, b.x), min(a.x2, b.x2)
    return None


def wall_len(r, wall):
    return r.w if wall in "NS" else r.h


def is_exterior(r, wall, lay):
    return {"N": abs(r.y - E) < EPS, "W": abs(r.x - E) < EPS,
            "S": abs(r.y2 - (lay.outer_h - E)) < EPS, "E": abs(r.x2 - (lay.outer_w - E)) < EPS}[wall]


def _stack(x, y, w, items, total):
    fills = [i for i in items if i[2] is None]
    rem = total - sum(i[2] for i in items if i[2] is not None) - P * (len(items) - 1)
    out, cy = [], y
    for name, kind, h in items:
        hh = h if h is not None else rem / len(fills)
        out.append(Room(name, kind, x, cy, w, hh))
        cy += hh + P
    return out


# ------------------------------------------------------------ templates
def generate_layout(req: dict) -> Layout:
    spec = spec_from_requirements(req)
    bhk, f = spec["bhk"], spec["scale"]
    d = lambda v: round(v * f * 2) / 2
    bal = spec["balcony"]
    rooms, conns = [], []
    foyer_label = "Dining / Foyer" if spec["dining"] else "Foyer"

    if bhk == 1:                       # mirrors the reference: foyer + passage + living + bedroom
        LW, tw, b, kh, th = d(8), d(5), d(11.5), d(9), d(7)
        bal_h, liv_h, bed_h = d(4), d(11), d(10)
        liv_total = liv_h if bal else liv_h + bal_h + P
        Hi = bed_h + P + liv_total + ((P + bal_h) if bal else 0)
        fh = Hi - kh - th - 2 * P
        rooms += [Room("Kitchen", "kitchen", E, E, LW, kh),
                  Room("Toilet", "toilet", E, E + kh + P, tw, th),
                  Room("Passage", "passage", E + tw + P, E + kh + P, LW - tw - P, th),
                  Room("Foyer", "foyer", E, E + kh + th + 2 * P, LW, fh, label=foyer_label)]
        items = ([("Balcony", "balcony", bal_h)] if bal else []) + \
                [("Living Room", "living", liv_total if not bal else None), ("Bedroom", "master", bed_h)]
        if bal:
            items[1] = ("Living Room", "living", None)
        rooms += _stack(E + LW + P, E, b, items, Hi)
        Wout, entrance = E + LW + P + b + E, ("Foyer", "S")
        conns = [("Kitchen", "Living Room", "door", 1.0), ("Toilet", "Passage", "door", .5),
                 ("Passage", "Living Room", "open", .5), ("Passage", "Foyer", "open", .5),
                 ("Bedroom", "Living Room", "door", 0.0)]
    else:
        LW, tw, kh, th = d(10), d(5.5), d(9 if bhk == 2 else 10), d(7)
        b, mast, bal_h = d(12.5 if bhk == 2 else 13), d(10), d(4)
        Hi = d(28 if bhk == 2 else 31)
        rooms += [Room("Kitchen", "kitchen", E, E, LW, kh),
                  Room("Toilet", "toilet", E, E + kh + P, tw, th),
                  Room("Passage", "passage", E + tw + P, E + kh + P, LW - tw - P, th),
                  Room("Bedroom 2", "bedroom", E, E + kh + th + 2 * P, LW, Hi - kh - th - 2 * P)]
        items = ([("Balcony", "balcony", bal_h)] if bal else []) + \
                [("Living Room", "living", None), ("Master Bedroom", "master", mast)]
        rooms += _stack(E + LW + P, E, b, items, Hi)
        Wout = E + LW + P + b + E
        conns = [("Kitchen", "Living Room", "door", 1.0), ("Toilet", "Passage", "door", .5),
                 ("Passage", "Living Room", "open", .5), ("Bedroom 2", "Passage", "door", .5),
                 ("Master Bedroom", "Living Room", "door", 0.0)]
        entrance = ("Living Room", "E")
        if bhk == 3:
            c = d(10)
            rooms += _stack(E + LW + P + b + P, E, c, [("Bedroom 3", "bedroom", d(11)),
                            ("Toilet 2", "toilet", d(5)), ("Foyer", "foyer", None)], Hi)
            rooms[-1].label = foyer_label
            Wout += P + c
            entrance = ("Foyer", "S")
            conns += [("Bedroom 3", "Living Room", "door", 0.0), ("Toilet 2", "Living Room", "door", .5),
                      ("Foyer", "Living Room", "open", .5)]
    if bal:
        conns.append(("Balcony", "Living Room", "door", 0.0))
    lay = Layout(rooms, Wout, E + Hi + E, entrance, spec["notes"], req)
    _add_openings(lay, conns)
    return lay


def _room(lay, name):
    return next(r for r in lay.rooms if r.name == name)


def _add_openings(lay: Layout, conns):
    for a_name, b_name, kind, frac in conns:
        a, b = _room(lay, a_name), _room(lay, b_name)
        e = shared_edge(a, b)
        if not e:
            continue
        wall, lo, hi = e
        base = a.x if wall in "NS" else a.y
        if kind == "open":
            a.doors.append(Opening(wall, lo - base, hi - lo, "open"))
            continue
        dw = 2.5 if a.kind == "toilet" else DOOR_W
        m = min(0.75, max(0.0, (hi - lo - dw) / 2))
        start = lo + m + max(0.0, hi - lo - dw - 2 * m) * frac
        a.doors.append(Opening(wall, start - base, dw, "door"))
    # main entrance
    name, wall = lay.entrance
    r = _room(lay, name)
    L = wall_len(r, wall)
    off = 1.2 if wall == "S" else min(max(1.5, L * 0.72), L - DOOR_W - 1.0)
    r.doors.append(Opening(wall, off, DOOR_W, "entrance", E))
    # windows on exterior walls
    pref = {"kitchen": "NW", "toilet": "WNES", "living": "ESNW", "master": "SEWN", "bedroom": "WSEN"}
    for r in lay.rooms:
        if r.kind not in pref:
            continue
        width = 2.0 if r.kind == "toilet" else (3.5 if r.kind == "kitchen" else 4.0)
        for wall in pref[r.kind]:
            if is_exterior(r, wall, lay) and _put_window(r, wall, width):
                break


def _put_window(r, wall, width):
    L = wall_len(r, wall)
    width = min(width, L * 0.6)
    if width < 1.5:
        return False
    for frac in (0.5, 0.3, 0.7):
        c = L * frac
        lo, hi = c - width / 2, c + width / 2
        if lo < 0.8 or hi > L - 0.8:
            continue
        if any(o.wall == wall and not (hi + 0.8 < o.offset or lo - 0.8 > o.offset + o.width) for o in r.doors):
            continue
        r.windows.append(Opening(wall, lo, width, "window", E))
        return True
    return False


# ------------------------------------------------------------ validation
def validate(lay: Layout) -> list:
    issues, rooms = [], lay.rooms
    for i, a in enumerate(rooms):
        if a.x < E - EPS or a.y < E - EPS or a.x2 > lay.outer_w - E + EPS or a.y2 > lay.outer_h - E + EPS:
            issues.append(f"{a.name}: outside footprint")
        for b in rooms[i + 1:]:
            gx, gy = max(b.x - a.x2, a.x - b.x2), max(b.y - a.y2, a.y - b.y2)
            if gx < P - EPS and gy < P - EPS:
                issues.append(f"Overlap / wall too thin: {a.name} / {b.name}")
    for r in rooms:
        if r.area < MIN_AREA.get(r.kind, 0):
            issues.append(f"{r.name}: {r.area} sq ft below minimum {MIN_AREA[r.kind]}")
        if min(r.w, r.h) < MIN_DIM.get(r.kind, 0):
            issues.append(f"{r.name}: narrow side {min(r.w, r.h):g} ft below minimum {MIN_DIM[r.kind]}")
        via_balcony = any(o2.kind == "door" and o2.wall and shared_edge(r, q) and q.kind == "balcony"
                          for q in rooms for o2 in q.doors if shared_edge(q, r) and shared_edge(q, r)[0] == o2.wall)
        if r.kind in NEEDS_WINDOW and not r.windows and not via_balcony:
            issues.append(f"{r.name}: no window / ventilation")
    adj = {r.name: set() for r in rooms}
    for r in rooms:
        for o in r.doors:
            if o.kind == "entrance":
                continue
            mid = (r.x if o.wall in "NS" else r.y) + o.offset + o.width / 2
            for q in rooms:
                e = shared_edge(r, q) if q is not r else None
                if e and e[0] == o.wall and e[1] - EPS <= mid <= e[2] + EPS:
                    adj[r.name].add(q.name); adj[q.name].add(r.name)
    if not lay.entrance:
        issues.append("No main entrance")
    else:
        seen, q = {lay.entrance[0]}, deque([lay.entrance[0]])
        while q:
            for n in adj[q.popleft()]:
                if n not in seen:
                    seen.add(n); q.append(n)
        issues += [f"{r.name}: not reachable from the main entrance" for r in rooms if r.name not in seen]
    return issues

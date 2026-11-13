"""Generate EduAI illustration SVGs (original artwork, no third-party photos).

Usage (from frontend/): python scripts/generate-illustrations.py public/images
"""
import os
import sys

NAVY = "#14213D"
NAVY2 = "#22325a"
GOLD = "#C9A227"
GOLD_L = "#E6C95E"
PAPER = "#F4F2EC"
FONT = "Public Sans, Segoe UI, Arial, sans-serif"

SKINS = ["#E8B894", "#C98E66", "#A86F4C", "#F1C9A5", "#8D5A3B"]
HAIRS = ["#2B1D16", "#3B2A20", "#1A1A1A", "#5A3B26", "#24180F"]
SHIRTS = ["#3D628E", "#FFFFFF", "#26745F", "#8C621A", "#6B4C9A", "#B5483F"]


def svg(w, h, body, defs="", bg=True):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'font-family="{FONT}"><defs>{defs}</defs>{body}</svg>\n')


def room_defs(p=""):
    return (f'<linearGradient id="{p}wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#DCD6CA"/>'
            f'<stop offset="1" stop-color="#C4BCAE"/></linearGradient>'
            f'<linearGradient id="{p}win" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#EAF3FB"/>'
            f'<stop offset="1" stop-color="#B9D3EA"/></linearGradient>'
            f'<linearGradient id="{p}desk" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9C7652"/>'
            f'<stop offset="1" stop-color="#6E5038"/></linearGradient>'
            f'<radialGradient id="{p}vig" cx=".5" cy=".45" r=".75"><stop offset=".6" stop-color="#000" stop-opacity="0"/>'
            f'<stop offset="1" stop-color="#000" stop-opacity=".28"/></radialGradient>')


def room(x, y, w, h, p="", window=True, shelf=True, desk=True, desk_y=None):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{p}wall)"/>']
    if window:
        wx, wy, ww, wh = x + w * .06, y + h * .08, w * .26, h * .42
        out.append(f'<rect x="{wx}" y="{wy}" width="{ww}" height="{wh}" rx="4" fill="#F7F4EE"/>'
                   f'<rect x="{wx + 8}" y="{wy + 8}" width="{ww - 16}" height="{wh - 16}" fill="url(#{p}win)"/>'
                   f'<rect x="{wx + ww / 2 - 3}" y="{wy + 8}" width="6" height="{wh - 16}" fill="#F7F4EE"/>'
                   f'<rect x="{wx + 8}" y="{wy + wh / 2 - 3}" width="{ww - 16}" height="6" fill="#F7F4EE"/>')
    if shelf:
        sx, sy, sw = x + w * .66, y + h * .22, w * .28
        out.append(f'<rect x="{sx}" y="{sy}" width="{sw}" height="9" fill="#8A6A4C"/>')
        bx = sx + 10
        for i, (bw, bh, c) in enumerate([(14, 46, "#3D628E"), (12, 40, "#B5483F"), (16, 50, GOLD), (11, 38, "#26745F"), (14, 44, NAVY2)]):
            out.append(f'<rect x="{bx}" y="{sy - bh}" width="{bw}" height="{bh}" fill="{c}"/>')
            bx += bw + 3
        px = sx + sw - 34
        out.append(f'<rect x="{px}" y="{sy - 26}" width="24" height="26" rx="3" fill="#C9874F"/>'
                   f'<path d="M{px + 12} {sy - 26}c-14-10-16-30-4-40c2 14 8 22 4 40zm0 0c10-12 24-14 30-8c-10 2-18 6-30 8z" fill="#4E8A5A"/>')
    if desk:
        dy = desk_y if desk_y is not None else y + h * .84
        out.append(f'<rect x="{x}" y="{dy}" width="{w}" height="{y + h - dy}" fill="url(#{p}desk)"/>'
                   f'<rect x="{x}" y="{dy}" width="{w}" height="6" fill="#B48D66"/>')
    return "".join(out)


def person(cx, cy, s=1.0, skin=SKINS[0], hair=HAIRS[0], shirt=SHIRTS[0], turn=0.0, eyes=True, mouth="smile", hijab=None):
    """Head centre (cx, cy), scale s. turn in [-1, 1]: negative = looking to viewer's left."""
    hx, hy = 62 * s, 76 * s
    o = []
    # torso
    o.append(f'<path d="M{cx - 150 * s} {cy + 330 * s} C{cx - 150 * s} {cy + 150 * s} {cx - 120 * s} {cy + 105 * s} {cx} {cy + 100 * s} '
             f'C{cx + 120 * s} {cy + 105 * s} {cx + 150 * s} {cy + 150 * s} {cx + 150 * s} {cy + 330 * s}Z" fill="{shirt}"/>')
    if shirt == "#FFFFFF":
        o.append(f'<path d="M{cx - 150 * s} {cy + 330 * s} C{cx - 150 * s} {cy + 150 * s} {cx - 120 * s} {cy + 105 * s} {cx} {cy + 100 * s} '
                 f'C{cx + 120 * s} {cy + 105 * s} {cx + 150 * s} {cy + 150 * s} {cx + 150 * s} {cy + 330 * s}Z" fill="none" stroke="#D5D8DC" stroke-width="{2 * s}"/>')
    # neck
    o.append(f'<path d="M{cx - 26 * s} {cy + 50 * s}h{52 * s}v{55 * s}c-{10 * s} {16 * s}-{42 * s} {16 * s}-{52 * s} 0z" fill="{skin}"/>')
    o.append(f'<path d="M{cx - 26 * s} {cy + 70 * s}c{16 * s} {12 * s} {36 * s} {12 * s} {52 * s} 0v-{18 * s}h-{52 * s}z" fill="#000" opacity=".12"/>')
    if hijab:
        o.append(f'<path d="M{cx - hx * 1.35} {cy + 120 * s}C{cx - hx * 1.5} {cy - 40 * s} {cx - hx * 1.2} {cy - hy * 1.25} {cx} {cy - hy * 1.25}'
                 f'C{cx + hx * 1.2} {cy - hy * 1.25} {cx + hx * 1.5} {cy - 40 * s} {cx + hx * 1.35} {cy + 120 * s}'
                 f'C{cx + 60 * s} {cy + 150 * s} {cx - 60 * s} {cy + 150 * s} {cx - hx * 1.35} {cy + 120 * s}Z" fill="{hijab}"/>')
    # head
    hxx = hx * (1 - .18 * abs(turn))
    o.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{hxx}" ry="{hy}" fill="{skin}"/>')
    # ears
    if not hijab:
        if turn > -.6:
            o.append(f'<ellipse cx="{cx - hxx + 2 * s}" cy="{cy + 8 * s}" rx="{11 * s}" ry="{17 * s}" fill="{skin}"/>')
        if turn < .6:
            o.append(f'<ellipse cx="{cx + hxx - 2 * s}" cy="{cy + 8 * s}" rx="{11 * s}" ry="{17 * s}" fill="{skin}"/>')
    # hair
    if not hijab:
        o.append(f'<path d="M{cx - hxx - 4 * s} {cy - 4 * s}C{cx - hxx - 10 * s} {cy - hy * 1.1} {cx + hxx + 10 * s} {cy - hy * 1.15} {cx + hxx + 4 * s} {cy - 4 * s}'
                 f'C{cx + hxx - 6 * s} {cy - 40 * s} {cx + 20 * s * (1 + turn)} {cy - 52 * s} {cx - 10 * s + turn * 20 * s} {cy - 46 * s}'
                 f'C{cx - 40 * s} {cy - 42 * s} {cx - hxx + 4 * s} {cy - 36 * s} {cx - hxx - 4 * s} {cy - 4 * s}Z" fill="{hair}"/>')
    else:
        o.append(f'<path d="M{cx - hxx - 2 * s} {cy - 8 * s}C{cx - hxx} {cy - hy * 1.02} {cx + hxx} {cy - hy * 1.02} {cx + hxx + 2 * s} {cy - 8 * s}'
                 f'C{cx + hxx - 10 * s} {cy - 50 * s} {cx - hxx + 10 * s} {cy - 50 * s} {cx - hxx - 2 * s} {cy - 8 * s}Z" fill="{hijab}"/>')
    if eyes:
        fx = cx + turn * hxx * .55
        sp = 24 * s * (1 - .35 * abs(turn))
        for ex in (fx - sp, fx + sp):
            o.append(f'<ellipse cx="{ex}" cy="{cy + 4 * s}" rx="{6 * s}" ry="{7 * s}" fill="#2A1E18"/>'
                     f'<circle cx="{ex + 2 * s + turn * 2 * s}" cy="{cy + 2 * s}" r="{2 * s}" fill="#fff"/>')
            o.append(f'<path d="M{ex - 11 * s} {cy - 14 * s}q{11 * s} -{7 * s} {22 * s} 0" stroke="{hair}" stroke-width="{4 * s}" fill="none" stroke-linecap="round"/>')
        o.append(f'<path d="M{fx + turn * 8 * s} {cy + 10 * s}l{-5 * s + turn * 8 * s} {20 * s}h{10 * s}" stroke="#000" stroke-opacity=".2" stroke-width="{3 * s}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
        if mouth == "smile":
            o.append(f'<path d="M{fx - 16 * s} {cy + 44 * s}q{16 * s} {12 * s} {32 * s} 0" stroke="#8E4B3B" stroke-width="{4 * s}" fill="none" stroke-linecap="round"/>')
        elif mouth == "open":
            o.append(f'<ellipse cx="{fx}" cy="{cy + 46 * s}" rx="{10 * s}" ry="{8 * s}" fill="#6E2F27"/>')
        else:
            o.append(f'<path d="M{fx - 13 * s} {cy + 46 * s}h{26 * s}" stroke="#8E4B3B" stroke-width="{4 * s}" stroke-linecap="round"/>')
    return "".join(o)


def box(x, y, w, h, label, s=1.0, color=GOLD, dashed=False, label_below=False, ls=None):
    ss = s
    s = ls or s
    dash = f' stroke-dasharray="{14 * s} {9 * s}"' if dashed else ""
    tw = len(label) * 10.2 * s + 22 * s
    ly = y + h + 4 * s if label_below else y - 34 * s
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{6 * ss}" fill="none" stroke="{color}" stroke-width="{6 * ss}"{dash}/>'
            f'<rect x="{x - 2.5 * s}" y="{ly}" width="{tw}" height="{30 * s}" rx="{4 * s}" fill="{color}"/>'
            f'<text x="{x + 9 * s}" y="{ly + 21 * s}" font-size="{17 * s}" font-weight="700" fill="{NAVY}">{label}</text>')


def cam_ui(w, h, s=1.0, time="10:24:37"):
    m = 26 * s
    L = 46 * s
    c = []
    for (x, y, dx, dy) in [(m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)]:
        c.append(f'<path d="M{x} {y + dy * L}V{y}H{x + dx * L}" stroke="#fff" stroke-opacity=".85" stroke-width="{4 * s}" fill="none"/>')
    c.append(f'<rect x="{m + 14 * s}" y="{m + 14 * s}" width="{86 * s}" height="{30 * s}" rx="{15 * s}" fill="#000" fill-opacity=".45"/>'
             f'<circle cx="{m + 32 * s}" cy="{m + 29 * s}" r="{7 * s}" fill="#E5484D"/>'
             f'<text x="{m + 46 * s}" y="{m + 35 * s}" font-size="{16 * s}" font-weight="700" fill="#fff">REC</text>'
             f'<rect x="{w - m - 120 * s}" y="{m + 14 * s}" width="{106 * s}" height="{30 * s}" rx="{15 * s}" fill="#000" fill-opacity=".45"/>'
             f'<text x="{w - m - 67 * s}" y="{m + 35 * s}" font-size="{16 * s}" font-weight="600" fill="#fff" text-anchor="middle">{time}</text>')
    return "".join(c)


def phone(x, y, s=1.0, rot=-8):
    return (f'<g transform="rotate({rot} {x} {y})"><rect x="{x - 34 * s}" y="{y - 62 * s}" width="{68 * s}" height="{124 * s}" rx="{11 * s}" fill="#1E2430"/>'
            f'<rect x="{x - 28 * s}" y="{y - 52 * s}" width="{56 * s}" height="{100 * s}" rx="{5 * s}" fill="#5B8BD0"/>'
            f'<rect x="{x - 22 * s}" y="{y - 42 * s}" width="{44 * s}" height="{8 * s}" rx="2" fill="#fff" opacity=".7"/>'
            f'<rect x="{x - 22 * s}" y="{y - 28 * s}" width="{30 * s}" height="{6 * s}" rx="2" fill="#fff" opacity=".5"/>'
            f'<rect x="{x - 22 * s}" y="{y - 16 * s}" width="{38 * s}" height="{6 * s}" rx="2" fill="#fff" opacity=".5"/></g>')


def hand(x, y, s=1.0, skin=SKINS[0], rot=0):
    return (f'<g transform="rotate({rot} {x} {y})"><rect x="{x - 40 * s}" y="{y - 6 * s}" width="{80 * s}" height="{48 * s}" rx="{22 * s}" fill="{skin}"/>'
            f'<rect x="{x - 46 * s}" y="{y - 30 * s}" width="{22 * s}" height="{50 * s}" rx="{11 * s}" fill="{skin}"/>'
            f'<path d="M{x - 40 * s} {y + 40 * s}l{-10 * s} {120 * s}h{100 * s}l{-10 * s} -{120 * s}z" fill="{skin}"/></g>')


def book(x, y, w, s=1.0):
    h = w * .42
    return (f'<path d="M{x} {y + 10 * s}Q{x + w / 4} {y - 12 * s} {x + w / 2} {y + 6 * s}Q{x + 3 * w / 4} {y - 12 * s} {x + w} {y + 10 * s}'
            f'L{x + w + 10 * s} {y + h}Q{x + 3 * w / 4} {y + h - 18 * s} {x + w / 2} {y + h + 8 * s}Q{x + w / 4} {y + h - 18 * s} {x - 10 * s} {y + h}Z" fill="#7A2E2A"/>'
            f'<path d="M{x + 6 * s} {y + 6 * s}Q{x + w / 4} {y - 14 * s} {x + w / 2} {y + 2 * s}V{y + h - 4 * s}Q{x + w / 4} {y + h - 26 * s} {x - 2 * s} {y + h - 8 * s}Z" fill="#FBF8F1"/>'
            f'<path d="M{x + w / 2} {y + 2 * s}Q{x + 3 * w / 4} {y - 14 * s} {x + w - 6 * s} {y + 6 * s}L{x + w + 2 * s} {y + h - 8 * s}Q{x + 3 * w / 4} {y + h - 26 * s} {x + w / 2} {y + h - 4 * s}Z" fill="#F1ECE0"/>'
            + "".join(f'<path d="M{x + 18 * s} {y + (18 + i * 15) * s}q{w / 8} -{6 * s} {w / 2 - 34 * s} 0" stroke="#9AA3AE" stroke-width="{3 * s}" fill="none"/>'
                      f'<path d="M{x + w / 2 + 16 * s} {y + (18 + i * 15) * s}q{w / 8} -{6 * s} {w / 2 - 34 * s} 0" stroke="#9AA3AE" stroke-width="{3 * s}" fill="none"/>'
                      for i in range(int((h - 40 * s) / (15 * s)))))


def vig(w, h, p=""):
    return f'<rect width="{w}" height="{h}" fill="url(#{p}vig)"/>'


# ---------------- AI signal cards (800 x 800, subject in the central band) ----------------
W = H = 800


def signal_phone():
    b = room(0, 0, W, H) + person(400, 330, 1.25, SKINS[1], HAIRS[0], SHIRTS[0], turn=0.0, mouth="flat")
    b += hand(560, 520, 1.1, SKINS[1], rot=-12) + phone(565, 450, 1.25, rot=-10)
    b += box(470, 352, 170, 200, "Ponsel 87%", ls=1.9)
    b += vig(W, H) + cam_ui(W, H, 1.5)
    return svg(W, H, b, room_defs())


def signal_book():
    b = room(0, 0, W, H, desk_y=600) + person(400, 290, 1.15, SKINS[0], HAIRS[3], SHIRTS[1], turn=.05)
    b += book(225, 595, 350, 1.2)
    b += hand(205, 690, .9, SKINS[0], rot=15) + hand(595, 690, .9, SKINS[0], rot=-15)
    b += box(196, 570, 408, 190, "Buku 74%", ls=1.9)
    b += vig(W, H) + cam_ui(W, H, 1.5)
    return svg(W, H, b, room_defs())


def signal_person():
    b = room(0, 0, W, H) + person(560, 270, .85, SKINS[2], HAIRS[2], SHIRTS[2], turn=-.45, mouth="open")
    b += person(360, 360, 1.2, SKINS[3], HAIRS[1], SHIRTS[4], turn=0, mouth="flat", hijab="#3D628E")
    b += box(268, 240, 184, 236, "Wajah 1", ls=1.7)
    b += box(495, 168, 132, 186, "Wajah 2", ls=1.7, label_below=True)
    b += vig(W, H) + cam_ui(W, H, 1.5)
    return svg(W, H, b, room_defs())


def signal_turn():
    b = room(0, 0, W, H) + person(400, 340, 1.25, SKINS[4], HAIRS[4], SHIRTS[3], turn=-1.0, mouth="flat")
    b += (f'<path d="M260 210 C200 190 150 205 115 240" stroke="{GOLD_L}" stroke-width="9" fill="none" stroke-linecap="round"/>'
          f'<path d="M108 210 L112 248 L150 240" stroke="{GOLD_L}" stroke-width="9" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
    b += box(310, 225, 180, 230, "Menoleh 3x", ls=1.9, label_below=True)
    b += vig(W, H) + cam_ui(W, H, 1.5)
    return svg(W, H, b, room_defs())


def signal_noface():
    b = room(0, 0, W, H)
    # empty office chair
    b += (f'<path d="M270 300 Q400 250 530 300 L520 560 H280Z" fill="#2F3A4F"/>'
          f'<path d="M290 320 Q400 280 510 320 L502 540 H298Z" fill="#3B475E"/>')
    # person leaving the frame at the right edge (shoulder + arm only)
    b += f'<path d="M700 330 C760 320 820 330 820 360 V680 H690 C680 560 670 420 700 330Z" fill="{SHIRTS[5]}"/>'
    b += f'<ellipse cx="800" cy="250" rx="60" ry="76" fill="{SKINS[0]}"/>'
    b += box(200, 255, 400, 320, "Wajah tidak terdeteksi", dashed=True, color="#F1C1BE", ls=1.6)
    b += vig(W, H) + cam_ui(W, H, 1.5)
    return svg(W, H, b, room_defs())


def signal_voice():
    b = room(0, 0, W, H, shelf=False)
    # half-open door with a second (talking) silhouette in the background
    b += (f'<rect x="560" y="80" width="190" height="600" fill="#5A4636"/>'
          f'<rect x="575" y="95" width="160" height="585" fill="#2A2420"/>'
          f'<path d="M575 95 L640 120 V700 L575 680Z" fill="#8A6A4C"/>'
          f'<g opacity=".85"><ellipse cx="690" cy="250" rx="36" ry="44" fill="#4A3B33"/>'
          f'<path d="M630 470 C630 340 650 310 690 305 C730 310 750 340 750 470Z" fill="#4A3B33"/></g>')
    b += person(340, 350, 1.2, SKINS[0], HAIRS[1], SHIRTS[0], turn=.25, mouth="flat")
    # sound waves from the door towards the student
    for i, r in enumerate((60, 100, 140)):
        b += f'<path d="M{600 - r * .2} {250 - r} A{r} {r} 0 0 0 {600 - r * .2} {250 + r}" stroke="{GOLD_L}" stroke-width="8" fill="none" stroke-linecap="round" opacity="{1 - i * .22}"/>'
    # audio meter chip
    bars = [18, 34, 56, 40, 70, 46, 28, 60, 36, 20]
    b += '<rect x="60" y="200" width="300" height="120" rx="14" fill="#000" fill-opacity=".55"/>'
    b += f'<text x="82" y="240" font-size="26" font-weight="700" fill="{GOLD_L}">Suara lain 68%</text>'
    for i, bh in enumerate(bars):
        b += f'<rect x="{92 + i * 21}" y="{300 - bh * .55}" width="12" height="{bh * .55}" rx="3" fill="#fff" opacity=".9"/>'
    b += vig(W, H) + cam_ui(W, H, 1.5)
    return svg(W, H, b, room_defs())


# ---------------- Landing cards (1200 x 675, 16:9) ----------------
CW, CH = 1200, 675


def laptop(x, y, w, screen_body, s=1.0):
    h = w * .62
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{14 * s}" fill="#262D3B"/>'
            f'<rect x="{x + 14 * s}" y="{y + 14 * s}" width="{w - 28 * s}" height="{h - 28 * s}" rx="{4 * s}" fill="#fff"/>'
            f'<circle cx="{x + w / 2}" cy="{y + 7 * s}" r="{3 * s}" fill="#5DD39E"/>'
            f'<svg x="{x + 14 * s}" y="{y + 14 * s}" width="{w - 28 * s}" height="{h - 28 * s}" viewBox="0 0 {w - 28 * s} {h - 28 * s}">{screen_body}</svg>'
            f'<path d="M{x - 50 * s} {y + h}h{w + 100 * s}l-{20 * s} {26 * s}h-{w + 60 * s}z" fill="#AEB5C0"/>'
            f'<rect x="{x + w / 2 - 60 * s}" y="{y + h}" width="{120 * s}" height="{8 * s}" rx="3" fill="#8D95A2"/>')


def card_bg(p=""):
    return (f'<linearGradient id="{p}cb" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#F7F3E8"/>'
            f'<stop offset="1" stop-color="#E4DCC8"/></linearGradient>')


def check(x, y, ok=True, s=1.0):
    c = "#26745F" if ok else GOLD
    return (f'<circle cx="{x}" cy="{y}" r="{16 * s}" fill="{c}"/>'
            f'<path d="M{x - 7 * s} {y}l{5 * s} {5 * s}l{9 * s} -{10 * s}" stroke="#fff" stroke-width="{4 * s}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')


def card_cek():
    rows = [("Kamera", "Terdeteksi"), ("Mikrofon", "Aktif"), ("Peramban", "Chrome 131"), ("Koneksi", "Stabil")]
    sw, sh = 532, 330
    sc = f'<rect width="{sw}" height="{sh}" fill="#FAFAF7"/><rect width="{sw}" height="44" fill="{NAVY}"/>'
    sc += f'<text x="20" y="29" font-size="18" font-weight="700" fill="#fff">Cek perangkat</text>'
    sc += f'<rect x="20" y="62" width="170" height="128" rx="8" fill="#C4BCAE"/>' + person(105, 112, .32, SKINS[1], HAIRS[0], SHIRTS[0])
    sc += f'<rect x="20" y="62" width="170" height="128" rx="8" fill="none" stroke="{GOLD}" stroke-width="3"/>'
    for i, (k, v) in enumerate(rows):
        y = 78 + i * 52
        sc += check(225, y, s=.8) + f'<text x="248" y="{y + 6}" font-size="18" font-weight="700" fill="{NAVY}">{k}</text>'
        sc += f'<text x="510" y="{y + 6}" font-size="15" fill="#536173" text-anchor="end">{v}</text>'
    sc += f'<rect x="20" y="276" width="{sw - 40}" height="38" rx="6" fill="{NAVY}"/><text x="{sw / 2}" y="301" font-size="17" font-weight="700" fill="{GOLD_L}" text-anchor="middle">Lanjut ke Persetujuan</text>'
    b = f'<rect width="{CW}" height="{CH}" fill="url(#cb)"/>'
    b += f'<circle cx="1060" cy="120" r="200" fill="{GOLD}" opacity=".12"/><circle cx="120" cy="600" r="160" fill="{NAVY}" opacity=".07"/>'
    b += f'<rect y="560" width="{CW}" height="115" fill="#B9A585"/>'
    b += laptop(320, 150, 560, sc)
    # webcam + headset icons on the desk
    b += f'<g transform="translate(130 430)"><rect width="110" height="110" rx="24" fill="#fff"/><circle cx="55" cy="50" r="28" fill="{NAVY}"/><circle cx="55" cy="50" r="12" fill="#5B8BD0"/><rect x="38" y="84" width="34" height="10" rx="4" fill="{NAVY}"/></g>'
    b += f'<g transform="translate(960 430)"><rect width="110" height="110" rx="24" fill="#fff"/><rect x="42" y="22" width="26" height="46" rx="13" fill="{NAVY}"/><path d="M30 56a25 25 0 0 0 50 0M55 81v12" stroke="{NAVY}" stroke-width="6" fill="none" stroke-linecap="round"/></g>'
    return svg(CW, CH, b, card_bg())


def card_panduan():
    b = f'<rect width="{CW}" height="{CH}" fill="url(#cb)"/>'
    b += room(0, 0, CW, CH, shelf=False, desk_y=520).replace('url(#wall)', '#E9E2D2')
    b += person(420, 250, 1.0, SKINS[2], HAIRS[1], SHIRTS[0], turn=.35)
    b += f'<rect y="520" width="{CW}" height="155" fill="url(#desk)"/>'
    # back of laptop
    b += f'<path d="M250 520 L300 360 H560 L540 520Z" fill="#AEB5C0"/><circle cx="425" cy="440" r="14" fill="#fff" opacity=".6"/>'
    # guide sheet with steps
    b += f'<g transform="translate(700 110) rotate(4)"><rect width="380" height="440" rx="10" fill="#fff" stroke="#D6D8DA" stroke-width="2"/>'
    b += f'<rect width="380" height="62" rx="10" fill="{NAVY}"/><rect y="40" width="380" height="22" fill="{NAVY}"/>'
    b += f'<text x="24" y="40" font-size="24" font-weight="700" fill="#fff">Panduan siswa</text>'
    steps = ["Cek perangkat", "Baca persetujuan", "Masuk ruang ujian", "Kerjakan soal", "Kumpulkan jawaban"]
    for i, t in enumerate(steps):
        y = 108 + i * 68
        b += f'<circle cx="44" cy="{y}" r="20" fill="{GOLD}"/><text x="44" y="{y + 7}" font-size="19" font-weight="700" fill="{NAVY}" text-anchor="middle">{i + 1}</text>'
        b += f'<text x="80" y="{y + 7}" font-size="21" font-weight="600" fill="{NAVY}">{t}</text>'
        b += f'<rect x="80" y="{y + 18}" width="{220 - i * 18}" height="7" rx="3" fill="#E1E4E8"/>'
    b += '</g>'
    return svg(CW, CH, b, card_bg() + room_defs())


def card_laporan():
    b = f'<rect width="{CW}" height="{CH}" fill="#1B2A4A"/>'
    b += f'<circle cx="1100" cy="80" r="240" fill="{GOLD}" opacity=".1"/>'
    # report document
    b += f'<g transform="translate(120 70)"><rect width="560" height="560" rx="12" fill="#fff"/>'
    b += f'<rect width="560" height="70" rx="12" fill="{PAPER}"/><rect y="50" width="560" height="20" fill="{PAPER}"/>'
    b += f'<text x="28" y="46" font-size="26" font-weight="700" fill="{NAVY}">Laporan Sesi Ujian</text>'
    b += f'<text x="532" y="46" font-size="16" fill="#8a6b0d" text-anchor="end" font-weight="700">FINAL</text>'
    hdr = ["Waktu", "Siswa", "Indikasi", "Keputusan"]
    xs = [28, 130, 250, 410]
    for x, t in zip(xs, hdr):
        b += f'<text x="{x}" y="112" font-size="16" font-weight="700" fill="#536173">{t}</text>'
    data = [("09.12", "Siswa 1", "Ponsel", ("Valid", "#26745F", "#E5F3ED")),
            ("09.25", "Siswa 4", "Menoleh", ("Tidak valid", "#687386", "#ECEFF1")),
            ("09.40", "Siswa 2", "Buku", ("Ditinjau", "#8C621A", "#F7EDCF")),
            ("10.05", "Siswa 6", "Suara lain", ("Valid", "#26745F", "#E5F3ED"))]
    for i, (t, s_, ind, (dec, fg, bgc)) in enumerate(data):
        y = 150 + i * 56
        b += f'<rect x="20" y="{y - 30}" width="520" height="1" fill="#E1E4E8"/>'
        b += f'<text x="28" y="{y}" font-size="17" fill="{NAVY}">{t}</text><text x="130" y="{y}" font-size="17" fill="{NAVY}">{s_}</text>'
        b += f'<text x="250" y="{y}" font-size="17" font-weight="600" fill="{NAVY}">{ind}</text>'
        b += f'<rect x="404" y="{y - 22}" width="{len(dec) * 10 + 24}" height="30" rx="15" fill="{bgc}"/><text x="416" y="{y - 1}" font-size="15" font-weight="700" fill="{fg}">{dec}</text>'
    # chart
    b += f'<text x="28" y="404" font-size="16" font-weight="700" fill="#536173">Indikasi per jam</text>'
    for i, v in enumerate([40, 90, 60, 120, 75, 30, 55]):
        b += f'<rect x="{40 + i * 70}" y="{530 - v}" width="40" height="{v}" rx="4" fill="{GOLD if i == 3 else "#3D628E"}"/>'
    b += f'<rect x="28" y="530" width="500" height="2" fill="#C5CBD5"/></g>'
    # supervisor badge / pen
    b += f'<g transform="translate(760 150)"><rect width="320" height="380" rx="14" fill="#22325a"/>'
    b += person(160, 120, .6, SKINS[3], HAIRS[1], SHIRTS[1], hijab="#8C621A")
    b += f'<rect x="0" y="230" width="320" height="150" fill="#22325a"/>'
    b += f'<text x="160" y="272" font-size="24" font-weight="700" fill="#fff" text-anchor="middle">Pengawas</text>'
    b += f'<text x="160" y="304" font-size="16" fill="#C5CBD5" text-anchor="middle">Meninjau &amp; memutuskan</text>'
    b += f'<rect x="60" y="326" width="200" height="34" rx="17" fill="{GOLD}"/><text x="160" y="349" font-size="16" font-weight="700" fill="{NAVY}" text-anchor="middle">Simpan Validasi</text></g>'
    return svg(CW, CH, b)


def card_cara_kerja():
    b = f'<rect width="{CW}" height="{CH}" fill="url(#cb)"/>'
    b += f'<path d="M0 470 H1200 V675 H0Z" fill="{NAVY}" opacity=".06"/>'
    steps = [("Kamera", "frame"), ("AI", "menandai"), ("Indikasi", "perlu ditinjau"), ("Pengawas", "memutuskan")]
    xs = [150, 450, 750, 1050]
    for i, ((t, sub), x) in enumerate(zip(steps, xs)):
        y = 300
        b += f'<circle cx="{x}" cy="{y}" r="102" fill="#fff"/><circle cx="{x}" cy="{y}" r="102" fill="none" stroke="{GOLD if i in (1, 2) else NAVY}" stroke-width="6"/>'
        if i == 0:
            b += f'<rect x="{x - 48}" y="{y - 32}" width="70" height="64" rx="10" fill="{NAVY}"/><path d="M{x + 22} {y - 12}l34 -20v64l-34 -20z" fill="{NAVY}"/><circle cx="{x - 13}" cy="{y}" r="16" fill="#5B8BD0"/>'
        elif i == 1:
            b += f'<rect x="{x - 46}" y="{y - 46}" width="92" height="92" rx="16" fill="{NAVY}"/><text x="{x}" y="{y + 14}" font-size="40" font-weight="800" fill="{GOLD_L}" text-anchor="middle">AI</text>'
            for k in range(4):
                b += f'<rect x="{x - 36 + k * 22}" y="{y - 62}" width="7" height="16" fill="{NAVY}"/><rect x="{x - 36 + k * 22}" y="{y + 46}" width="7" height="16" fill="{NAVY}"/>'
        elif i == 2:
            b += f'<rect x="{x - 56}" y="{y - 46}" width="112" height="84" rx="8" fill="#C4BCAE"/>' + f'<svg x="{x - 56}" y="{y - 46}" width="112" height="84" viewBox="{x - 56} {y - 46} 112 84">' + person(x, y - 12, .3, SKINS[1], HAIRS[0], SHIRTS[2]) + '</svg>'
            b += f'<rect x="{x - 26}" y="{y - 40}" width="52" height="60" rx="4" fill="none" stroke="{GOLD}" stroke-width="5"/><path d="M{x - 18} {y + 52}h36l-18 -26z" fill="{GOLD}"/><text x="{x}" y="{y + 50}" font-size="16" font-weight="800" fill="{NAVY}" text-anchor="middle">!</text>'
        else:
            b += f'<svg x="{x - 100}" y="{y - 100}" width="200" height="200" viewBox="{x - 100} {y - 100} 200 200"><clipPath id="cc"><circle cx="{x}" cy="{y}" r="96"/></clipPath><g clip-path="url(#cc)">' + person(x, y - 18, .55, SKINS[0], HAIRS[3], SHIRTS[0]) + '</g></svg>'
            b += check(x + 66, y - 66, s=1.4)
        b += f'<text x="{x}" y="{y + 150}" font-size="30" font-weight="700" fill="{NAVY}" text-anchor="middle">{t}</text>'
        b += f'<text x="{x}" y="{y + 182}" font-size="20" fill="#536173" text-anchor="middle">{sub}</text>'
        if i < 3:
            b += f'<path d="M{x + 116} {y}H{x + 184}" stroke="{GOLD}" stroke-width="7" stroke-linecap="round" stroke-dasharray="2 16"/><path d="M{x + 176} {y - 14}l14 14l-14 14" stroke="{GOLD}" stroke-width="7" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
    b += f'<text x="600" y="110" font-size="30" font-weight="700" fill="{NAVY}" text-anchor="middle">AI menandai — manusia yang memutuskan</text>'
    return svg(CW, CH, b, card_bg())


def card_privasi():
    b = f'<rect width="{CW}" height="{CH}" fill="#1B2A4A"/>'
    b += f'<circle cx="600" cy="330" r="290" fill="#fff" opacity=".04"/><circle cx="600" cy="330" r="210" fill="#fff" opacity=".05"/>'
    # shield with lock
    b += (f'<path d="M600 90 L790 160 V320 C790 450 700 540 600 585 C500 540 410 450 410 320 V160Z" fill="{GOLD}"/>'
          f'<path d="M600 120 L762 180 V320 C762 432 686 512 600 552 C514 512 438 432 438 320 V180Z" fill="{NAVY}"/>'
          f'<rect x="530" y="300" width="140" height="120" rx="16" fill="{GOLD_L}"/>'
          f'<path d="M555 300 V262 a45 45 0 0 1 90 0 V300" stroke="{GOLD_L}" stroke-width="20" fill="none"/>'
          f'<circle cx="600" cy="350" r="15" fill="{NAVY}"/><rect x="593" y="356" width="14" height="36" rx="5" fill="{NAVY}"/>')
    # consent card
    b += f'<g transform="translate(830 200)"><rect width="300" height="270" rx="14" fill="#fff"/>'
    b += f'<text x="24" y="46" font-size="22" font-weight="700" fill="{NAVY}">Persetujuan</text>'
    for i, t in enumerate(["Kamera dianalisis", "Tanpa rekaman audio", "Dihapus otomatis"]):
        y = 92 + i * 52
        b += f'<rect x="24" y="{y - 20}" width="28" height="28" rx="6" fill="#26745F"/><path d="M31 {y - 6}l6 6l10 -12" stroke="#fff" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
        b += f'<text x="66" y="{y + 1}" font-size="18" fill="{NAVY}">{t}</text>'
    b += f'<rect x="24" y="222" width="252" height="34" rx="6" fill="{NAVY}"/><text x="150" y="245" font-size="16" font-weight="700" fill="{GOLD_L}" text-anchor="middle">Setuju &amp; Masuk</text></g>'
    # retention clock
    b += (f'<g transform="translate(70 210)"><rect width="270" height="240" rx="14" fill="#fff"/>'
          f'<circle cx="135" cy="104" r="62" fill="{PAPER}" stroke="{NAVY}" stroke-width="8"/>'
          f'<path d="M135 66V104L162 120" stroke="{NAVY}" stroke-width="8" fill="none" stroke-linecap="round"/>'
          f'<text x="135" y="204" font-size="20" font-weight="700" fill="{NAVY}" text-anchor="middle">Masa simpan 24 jam</text></g>')
    return svg(CW, CH, b)


# ---------------- Webcam tile (used in banner and login) ----------------

def tile(x, y, w, h, idx, label=None, p="t", dashed=False, extra=""):
    s = w / 800
    sk, hr, sh = SKINS[idx % 5], HAIRS[idx % 5], SHIRTS[idx % 6]
    hij = "#3D628E" if idx % 4 == 1 else ("#6B4C9A" if idx % 4 == 3 and idx > 4 else None)
    inner = room(0, 0, 800, 600, p=p) + person(400, 260 + (idx % 3) * 10, 1.1, sk, hr, sh, turn=[0, .2, -.15, .6, 0, -.5][idx % 6], hijab=hij)
    if extra == "phone":
        inner += hand(560, 470, 1.0, sk, rot=-12) + phone(565, 400, 1.15)
    elif extra == "book":
        inner += book(250, 500, 300, 1.0)
    if label:
        bx = {"phone": (505, 318, 125, 170), "book": (230, 470, 340, 150)}.get(extra, (310, 160, 180, 220))
        inner += box(*bx, label, s=1.3, dashed=dashed)
    inner += vig(800, 600, p)
    ui = cam_ui(w, h, w / 560, time=f"10:{20 + idx:02d}:{(idx * 13) % 60:02d}")
    return (f'<svg x="{x}" y="{y}" width="{w}" height="{h}" viewBox="0 0 800 600" preserveAspectRatio="xMidYMid slice">{inner}</svg>'
            f'<g transform="translate({x} {y})">{ui}</g>')


def banner():
    BW, BH = 4120, 760
    b = f'<rect width="{BW}" height="{BH}" fill="{NAVY}"/>'
    tw = (BW - 60 - 5 * 30) / 6
    th = BH - 60
    spec = [(None, ""), ("Ponsel terlihat", "phone"), (None, ""), ("Buku terlihat", "book"), (None, ""), ("Perlu ditinjau", "")]
    for i, (lab, ex) in enumerate(spec):
        x = 30 + i * (tw + 30)
        b += f'<clipPath id="bc{i}"><rect x="{x}" y="30" width="{tw}" height="{th}" rx="10"/></clipPath>'
        b += f'<g clip-path="url(#bc{i})">' + tile(x, 30, tw, th, i, lab, p="t", extra=ex) + '</g>'
        if lab:
            b += f'<rect x="{x}" y="30" width="{tw}" height="{th}" rx="10" fill="none" stroke="{GOLD}" stroke-width="8"/>'
    return svg(BW, BH, b, room_defs("t"))


def login_grid():
    LW, LH = 1151, 798
    b = ""
    frames = [(40, 60, 640, 420, 1, "Ponsel terlihat", "phone"), (520, 330, 590, 400, 2, "Perlu ditinjau", ""), (110, 470, 420, 290, 4, None, "")]
    for i, (x, y, w, h, idx, lab, ex) in enumerate(frames):
        b += f'<rect x="{x + 10}" y="{y + 16}" width="{w}" height="{h}" rx="16" fill="#14213D" opacity=".18"/>'
        b += f'<rect x="{x - 10}" y="{y - 10}" width="{w + 20}" height="{h + 20}" rx="18" fill="#262D3B"/>'
        b += f'<clipPath id="lc{i}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8"/></clipPath>'
        b += f'<g clip-path="url(#lc{i})">' + tile(x, y, w, h, idx, lab, p="t", extra=ex) + '</g>'
        if lab:
            b += f'<rect x="{x - 10}" y="{y - 10}" width="{w + 20}" height="{h + 20}" rx="18" fill="none" stroke="{GOLD}" stroke-width="6"/>'
    return svg(LW, LH, b, room_defs("t"))


def fallback():
    w, h = 1200, 675
    b = (f'<rect width="{w}" height="{h}" fill="#E4E1D8"/>'
         f'<g transform="translate(600 300)" fill="none" stroke="{NAVY}" stroke-opacity=".45" stroke-width="12" stroke-linejoin="round" stroke-linecap="round">'
         f'<rect x="-120" y="-80" width="240" height="170" rx="18"/><circle cx="-45" cy="-22" r="22"/><path d="M-110 70 L-30 0 L30 50 L60 25 L110 70"/></g>'
         f'<text x="600" y="470" font-size="30" font-weight="700" fill="{NAVY}" fill-opacity=".55" text-anchor="middle">EduAI · gambar tidak tersedia</text>')
    return svg(w, h, b)


def main(root):
    files = {
        "sinyal-ai/ponsel-terlihat.svg": signal_phone(),
        "sinyal-ai/buku-terlihat.svg": signal_book(),
        "sinyal-ai/orang-lain-terlihat.svg": signal_person(),
        "sinyal-ai/sering-menoleh.svg": signal_turn(),
        "sinyal-ai/wajah-tidak-terlihat.svg": signal_noface(),
        "sinyal-ai/suara-lain-terdengar.svg": signal_voice(),
        "beranda/cek-perangkat.svg": card_cek(),
        "beranda/panduan-siswa.svg": card_panduan(),
        "beranda/laporan-pengawas.svg": card_laporan(),
        "beranda/cara-kerja-ai.svg": card_cara_kerja(),
        "beranda/privasi-persetujuan.svg": card_privasi(),
        "beranda/banner-indikasi.svg": banner(),
        "login/grid-indikasi.svg": login_grid(),
        "fallback-gambar.svg": fallback(),
    }
    for rel, content in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"{rel}: {len(content) / 1024:.1f} KB")


if __name__ == "__main__":
    main(sys.argv[1])

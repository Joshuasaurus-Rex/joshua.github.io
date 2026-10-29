"""Backend ohne KI-Modell: zeichnet 80er-Szenen prozedural (Pillow). Läuft überall."""
import math
import random

from PIL import Image, ImageDraw

W, H = 640, 360

SKY = {  # (oben, unten)
    "sunset_grid": ((25, 8, 70), (255, 80, 150)),
    "city_night": ((5, 5, 40), (90, 30, 140)),
    "palms": ((120, 30, 160), (255, 150, 60)),
    "space": ((2, 2, 20), (30, 10, 70)),
    "auto": ((25, 8, 70), (255, 100, 90)),
    "tanke": ((5, 5, 30), (40, 20, 90)),
    "bahnhof": ((15, 25, 55), (90, 110, 150)),
    "anzeige": ((10, 15, 40), (60, 70, 120)),
    "regen": ((20, 25, 40), (70, 80, 100)),
    "haus": ((10, 5, 40), (110, 40, 120)),
    "endstation": ((25, 8, 70), (255, 80, 150)),
}

NO_HERO = {"auto"}  # Szenen, in denen die Figur anders gezeichnet wird


def _font(size):
    from PIL import ImageFont
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _lerp(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


class ProceduralRenderer:
    def __init__(self, fps: int = 12, **_):
        self.size = (W, H)
        self.fps = fps  # 12 fps = "on twos", klassischer Cartoon-Takt

    def frame(self, scene, t: float, beat_phase: float, energy: float) -> Image.Image:
        img = Image.new("RGB", (W, H))
        d = ImageDraw.Draw(img)
        top, bot = SKY[scene.setting]
        horizon = int(H * 0.62)
        for y in range(horizon):  # Banding statt weichem Verlauf = Cel-Look
            band = (y // 12) * 12
            d.line([(0, y), (W, y)], fill=_lerp(top, bot, band / horizon))
        rng = random.Random(hash(scene.setting) & 0xFFFF)
        for _ in range(40):  # Sterne, blinken im Beat
            x, y = rng.randrange(W), rng.randrange(horizon)
            if rng.random() < 0.5 + 0.5 * math.sin(t * 6 + x):
                d.rectangle([x, y, x + 1, y + 1], fill=(255, 255, 255))
        getattr(self, f"_bg_{scene.setting}")(d, t, horizon, beat_phase)
        if scene.setting not in NO_HERO:
            self._character(d, t, horizon, beat_phase, energy, tears=scene.setting in ("tanke", "bahnhof", "anzeige"))
        if scene.setting in ("regen", "bahnhof"):
            self._rain(d, t) if scene.setting == "regen" else self._wind(d, t)
        return img

    # --- Hintergründe -------------------------------------------------------
    def _grid(self, d, t, horizon):
        d.rectangle([0, horizon, W, H], fill=(20, 0, 40))
        for i in range(-12, 13):  # Fluchtlinien
            d.line([(W / 2 + i * 8, horizon), (W / 2 + i * 90, H)], fill=(255, 0, 200), width=2)
        off = (t * 1.5) % 1
        for k in range(10):  # horizontale Linien laufen auf den Betrachter zu
            z = (k + off) / 10
            y = horizon + (H - horizon) * z ** 2
            d.line([(0, y), (W, y)], fill=(0, 220, 255), width=2)

    def _bg_sunset_grid(self, d, t, horizon, bp):
        r = 70
        cx, cy = W // 2, horizon - 10
        d.pieslice([cx - r, cy - r, cx + r, cy + r], 180, 360, fill=(255, 220, 60))
        for k in range(5):  # Streifen in der Sonne
            y = cy - r + 20 + k * 12
            d.rectangle([cx - r, y, cx + r, y + k * 2], fill=_lerp((255, 80, 150), (255, 80, 150), 0))
        self._grid(d, t, horizon)

    def _bg_city_night(self, d, t, horizon, bp):
        rng = random.Random(7)
        x = 0
        while x < W:
            w, h = rng.randrange(30, 70), rng.randrange(60, 170)
            d.rectangle([x, horizon - h, x + w, horizon], fill=(15, 10, 45), outline=(0, 220, 255))
            for wy in range(horizon - h + 8, horizon - 6, 14):
                if rng.random() < 0.5:
                    d.rectangle([x + 6, wy, x + 10, wy + 6], fill=(255, 230, 90))
            x += w + 4
        self._grid(d, t, horizon)

    def _bg_palms(self, d, t, horizon, bp):
        d.rectangle([0, horizon, W, H], fill=(255, 190, 90))
        for px in (90, 520):
            sway = math.sin(t * 2 + px) * 6
            d.line([(px, horizon), (px + sway, horizon - 140)], fill=(60, 20, 40), width=8)
            for ang in range(-60, 61, 30):
                a = math.radians(ang - 90)
                d.line([(px + sway, horizon - 140),
                        (px + sway + math.cos(a) * 70, horizon - 140 + math.sin(a) * 40 + 30)],
                       fill=(20, 150, 90), width=6)

    def _bg_space(self, d, t, horizon, bp):
        d.rectangle([0, horizon, W, H], fill=(10, 5, 35))
        d.ellipse([430, 40, 560, 170], fill=(255, 120, 60))
        d.ellipse([400, 90, 590, 120], outline=(255, 230, 150), width=4)
        lx = int((t * 300) % W)
        d.line([(lx, 30), (lx + 40, 50)], fill=(0, 255, 120), width=3)

    # --- Figur: einfacher "Rubber-Hose"-Held, hüpft im Beat -------------------
    def _character(self, d, t, horizon, bp, energy, tears=False):
        squash = 1 - 0.18 * (1 - bp) ** 2  # beim Beat gestaucht, danach gestreckt
        hop = 40 * math.sin(math.pi * bp) * (0.4 + energy)
        cx, base = W // 2, horizon + 90 - hop
        bw, bh = 54 / squash, 70 * squash
        ink = (10, 10, 20)
        arm = math.sin(t * 8) * 25
        for s in (-1, 1):  # Arme
            d.line([(cx + s * bw / 2, base - bh * 0.8),
                    (cx + s * (bw / 2 + 30), base - bh * 0.8 - 20 + s * arm)], fill=ink, width=8)
            d.line([(cx + s * (bw / 2 - 12), base), (cx + s * (bw / 2 - 12), base + 28)], fill=ink, width=8)
        d.ellipse([cx - bw / 2, base - bh, cx + bw / 2, base], fill=(255, 60, 120), outline=ink, width=4)
        hr = 34
        hy = base - bh - hr + 8
        d.ellipse([cx - hr, hy - hr, cx + hr, hy + hr], fill=(255, 225, 190), outline=ink, width=4)
        d.polygon([(cx - hr, hy - 6), (cx, hy - hr - 28), (cx + hr, hy - 6)], fill=(0, 220, 255), outline=ink)  # Haartolle
        for s in (-1, 1):  # Sonnenbrille
            d.rectangle([cx + s * 16 - 12, hy - 8, cx + s * 16 + 12, hy + 6], fill=ink)
        if tears:
            for s_ in (-1, 1):
                ty = hy + 10 + (t * 60 + s_ * 20) % 40
                d.ellipse([cx + s_ * 20 - 2, ty, cx + s_ * 20 + 3, ty + 8], fill=(80, 180, 255))
        mouth = 4 + int(10 * energy)  # Mund folgt der Lautstärke
        d.ellipse([cx - 10, hy + 12, cx + 10, hy + 12 + mouth], fill=(120, 20, 40), outline=ink, width=2)

    # --- Zusätzliche Szenen für "Endstation Wahnsinn" -------------------------
    def _led(self, d, box, text, color=(255, 60, 40)):
        d.rectangle(box, fill=(15, 5, 5), outline=(90, 90, 100), width=4)
        d.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), text, font=_font(int((box[3] - box[1]) * 0.6)),
               fill=color, anchor="mm")

    def _rain(self, d, t):
        rng = random.Random(3)
        for _ in range(90):
            x = rng.randrange(W)
            y = (rng.randrange(H) + t * 500) % H
            d.line([(x, y), (x - 6, y + 16)], fill=(150, 190, 255), width=1)

    def _wind(self, d, t):
        rng = random.Random(5)
        for _ in range(14):
            y = rng.randrange(H)
            x = (rng.randrange(W) - t * 400) % (W + 120) - 60
            d.line([(x, y), (x + 70, y)], fill=(210, 230, 255), width=1)

    def _bg_auto(self, d, t, horizon, bp):
        self._bg_sunset_grid(d, t, horizon, bp)
        bump = 3 * math.sin(math.pi * bp)
        cx, y = W // 2, horizon + 70 - bump
        ink = (10, 10, 20)
        d.rounded_rectangle([cx - 120, y - 40, cx + 120, y], 14, fill=(255, 60, 120), outline=ink, width=4)
        d.polygon([(cx - 60, y - 40), (cx - 35, y - 78), (cx + 50, y - 78), (cx + 80, y - 40)], fill=(0, 220, 255), outline=ink)
        d.ellipse([cx - 22, y - 74, cx + 14, y - 42], fill=(255, 225, 190), outline=ink, width=3)  # Fahrer
        d.rectangle([cx - 20, y - 64, cx + 12, y - 56], fill=ink)
        for wx in (-80, 80):
            d.ellipse([cx + wx - 24, y - 24, cx + wx + 24, y + 24], fill=ink)
            d.ellipse([cx + wx - 9, y - 9, cx + wx + 9, y + 9], fill=(200, 200, 210))
        if int(t * 4) % 2:  # Warnblinker
            d.rectangle([cx + 112, y - 34, cx + 124, y - 24], fill=(255, 200, 0))

    def _bg_tanke(self, d, t, horizon, bp):
        d.rectangle([0, horizon, W, H], fill=(25, 25, 45))
        d.rectangle([0, 60, W, 110], fill=(230, 230, 240), outline=(10, 10, 20), width=4)  # Dach
        for x in (30, W - 30):
            d.rectangle([x - 10, 110, x + 10, horizon], fill=(160, 160, 175))
        self._led(d, (90, 130, 310, 215), "2,20", (255, 50, 40))
        d.text((200, 118), "SUPER E10  €/L", font=_font(14), fill=(255, 255, 255), anchor="mm")
        d.rectangle([470, horizon - 90, 520, horizon + 10], fill=(255, 190, 0), outline=(10, 10, 20), width=3)  # Zapfsäule
        if int(t * 3) % 2:  # Tankanzeige blinkt
            d.polygon([(40, 300), (70, 300), (55, 275)], fill=(255, 60, 40))

    def _bg_bahnhof(self, d, t, horizon, bp):
        d.rectangle([0, horizon, W, H], fill=(55, 55, 70))
        for i in range(-5, 6):  # Gleise
            d.line([(W / 2 + i * 6, horizon), (W / 2 + i * 150, H)], fill=(140, 140, 150), width=3)
        for k in range(8):  # Schwellen
            z = (k / 8) ** 2
            y = horizon + (H - horizon) * z
            d.line([(W / 2 - 60 - z * 250, y), (W / 2 + 60 + z * 250, y)], fill=(90, 70, 50), width=3)
        d.rectangle([60, horizon - 110, 160, horizon - 60], fill=(0, 90, 170), outline=(255, 255, 255), width=3)
        d.text((110, horizon - 85), "GLEIS 3", font=_font(18), fill=(255, 255, 255), anchor="mm")
        d.line([(110, horizon - 60), (110, horizon + 10)], fill=(200, 200, 210), width=5)

    def _bg_anzeige(self, d, t, horizon, bp):
        self._bg_bahnhof(d, t, horizon, bp)
        text = "+++ 60 MIN VERSPAETUNG +++ EICHHOERNCHEN AUF DEM GLEIS +++ "
        d.rectangle([40, 30, W - 40, 90], fill=(15, 5, 5), outline=(90, 90, 100), width=4)
        f = _font(36)
        off = int(t * 140) % int(d.textlength(text, font=f))
        for k in range(2):
            d.text((50 - off + k * d.textlength(text, font=f), 60), text, font=f, fill=(255, 170, 30), anchor="lm")
        d.rectangle([0, 30, 40, 90], fill=(10, 10, 20))   # Ränder verdecken Überlauf
        d.rectangle([W - 40, 30, W, 90], fill=(10, 10, 20))
        sx, sy = 480, horizon + 40 + int(3 * math.sin(t * 10))  # Eichhörnchen
        d.ellipse([sx - 28, sy - 40, sx + 4, sy + 8], fill=(190, 110, 50), outline=(10, 10, 20), width=3)  # Schwanz
        d.ellipse([sx, sy - 18, sx + 34, sy + 14], fill=(170, 95, 40), outline=(10, 10, 20), width=3)
        d.ellipse([sx + 22, sy - 26, sx + 44, sy - 6], fill=(170, 95, 40), outline=(10, 10, 20), width=3)

    def _bg_regen(self, d, t, horizon, bp):
        d.rectangle([0, horizon, W, H], fill=(40, 45, 60))
        for x in range(0, W, 90):
            d.rectangle([x, horizon - 120 - (x * 7) % 50, x + 60, horizon], fill=(30, 30, 55))
        bx, by = 130, horizon + 70  # Fahrrad
        for wx in (-35, 35):
            d.ellipse([bx + wx - 28, by - 28, bx + wx + 28, by + 28], outline=(230, 230, 240), width=4)
        d.line([(bx - 35, by), (bx, by - 40), (bx + 35, by), (bx - 35, by)], fill=(255, 60, 120), width=4)
        d.line([(bx - 140, by - 100), (bx + 70, by + 40)], fill=(255, 40, 40), width=6)  # durchgestrichen
        d.line([(bx + 70, by - 100), (bx - 140, by + 40)], fill=(255, 40, 40), width=6)

    def _bg_haus(self, d, t, horizon, bp):
        d.rectangle([0, horizon, W, H], fill=(30, 15, 50))
        d.rectangle([380, horizon - 220, 560, horizon + 60], fill=(70, 35, 25), outline=(10, 10, 20), width=5)
        d.rectangle([396, horizon - 200, 544, horizon + 60], fill=(255, 215, 120))  # warmes Licht
        gap = max(0.0, 1 - (t * 1.2) % 3)  # Tür fällt zu
        d.rectangle([396, horizon - 200, 396 + int(148 * (1 - gap)), horizon + 60], fill=(130, 70, 40), outline=(10, 10, 20), width=4)
        if gap == 0.0 and (t * 1.2) % 3 < 1.15:
            d.text((300, 80), "BAM!", font=_font(60), fill=(255, 230, 0), anchor="mm")

    def _bg_endstation(self, d, t, horizon, bp):
        self._bg_sunset_grid(d, t, horizon, bp)
        on = bp < 0.6 or int(t * 2) % 2
        col = (255, 60, 200) if on else (120, 30, 100)
        f = _font(54)
        d.text((W // 2 + 3, 63), "ENDSTATION", font=f, fill=(0, 0, 0), anchor="mm")
        d.text((W // 2, 60), "ENDSTATION", font=f, fill=col, anchor="mm")
        d.text((W // 2, 112), "WAHNSINN", font=_font(40), fill=(0, 230, 255) if on else (0, 100, 120), anchor="mm")

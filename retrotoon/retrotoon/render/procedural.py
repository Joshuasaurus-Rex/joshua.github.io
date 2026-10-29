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
}


def _lerp(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


class ProceduralRenderer:
    def __init__(self, fps: int = 12, **_):
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
        self._character(d, t, horizon, beat_phase, energy)
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
    def _character(self, d, t, horizon, bp, energy):
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
        mouth = 4 + int(10 * energy)  # Mund folgt der Lautstärke
        d.ellipse([cx - 10, hy + 12, cx + 10, hy + 12 + mouth], fill=(120, 20, 40), outline=ink, width=2)

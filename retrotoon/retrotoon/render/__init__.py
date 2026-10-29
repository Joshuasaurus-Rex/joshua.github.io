from .procedural import ProceduralRenderer


def get_renderer(name: str, **kw):
    if name == "procedural":
        return ProceduralRenderer(**kw)
    if name == "diffusion":
        from .diffusion import DiffusionRenderer  # schwere Imports nur bei Bedarf
        return DiffusionRenderer(**kw)
    if name == "video":
        from .video import VideoRenderer
        return VideoRenderer(**kw)
    raise ValueError(f"Unbekanntes Backend: {name}")


def caption(img, text: str):
    """Lyric als gelber Untertitel mit schwarzer Kontur, passt sich der Breite an."""
    if not text:
        return img
    from PIL import ImageDraw
    from .procedural import _font
    d = ImageDraw.Draw(img)
    size = 26
    while size > 12 and d.textlength(text, font=_font(size)) > img.width - 30:
        size -= 2
    d.text((img.width // 2, img.height - 26), text, font=_font(size), fill=(255, 240, 80),
           anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))
    return img

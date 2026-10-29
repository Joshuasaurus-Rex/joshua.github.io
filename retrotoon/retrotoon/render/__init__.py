from .procedural import ProceduralRenderer


def get_renderer(name: str, **kw):
    if name == "procedural":
        return ProceduralRenderer(**kw)
    if name == "diffusion":
        from .diffusion import DiffusionRenderer  # schwere Imports nur bei Bedarf
        return DiffusionRenderer(**kw)
    raise ValueError(f"Unbekanntes Backend: {name}")

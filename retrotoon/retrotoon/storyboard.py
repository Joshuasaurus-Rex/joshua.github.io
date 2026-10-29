"""Storyboard: Lyrics + Beats -> Szenenliste. Optional per lokalem LLM (Ollama)."""
import json
import urllib.request
from dataclasses import dataclass

from .audio import AudioInfo

# Szenen-Presets im 80er-Look (Saturday-Morning / Synthwave)
SETTINGS = [
    ("sunset_grid", "neon sunset over a glowing perspective grid"),
    ("city_night", "retro skyline at night with neon signs"),
    ("palms", "palm trees against a magenta-orange gradient sky"),
    ("space", "starfield with a ringed planet and laser beams"),
]


@dataclass
class Scene:
    start: float
    end: float
    setting: str  # Key aus SETTINGS
    prompt: str  # Bildprompt für das Diffusion-Backend
    lyric: str


def _split_lyrics(text: str) -> list[str]:
    return [l.strip() for l in text.splitlines() if l.strip()]


def build(info: AudioInfo, lyrics: str, character: str, bars_per_scene: int = 4,
          llm: str | None = None) -> list[Scene]:
    beats_per_scene = bars_per_scene * 4
    cuts = [b for b in info.beats[::beats_per_scene] if b < info.duration] + [info.duration]
    if cuts[0] > 0.5:
        cuts.insert(0, 0.0)
    lines = _split_lyrics(lyrics)
    scenes: list[Scene] = []
    for i, (a, b) in enumerate(zip(cuts, cuts[1:])):
        key, desc = SETTINGS[i % len(SETTINGS)]
        lyric = lines[i % len(lines)] if lines else ""
        prompt = (f"1980s saturday morning cartoon style, cel shaded, bold outlines, "
                  f"flat vivid colors, VHS grain, {character}, {desc}")
        scenes.append(Scene(float(a), float(b), key, prompt, lyric))
    if llm:
        _refine_with_ollama(scenes, character, llm)
    return scenes


def _refine_with_ollama(scenes: list[Scene], character: str, model: str) -> None:
    """Lässt ein lokales LLM die Bildprompts passend zu den Lyrics ausformulieren."""
    for s in scenes:
        if not s.lyric:
            continue
        body = json.dumps({
            "model": model, "stream": False,
            "prompt": (f"Write one short image prompt (max 30 words, English) for a 1980s "
                       f"cartoon music video scene. Character: {character}. Setting: {s.setting}. "
                       f"Lyric: \"{s.lyric}\". Output only the prompt."),
        }).encode()
        try:
            req = urllib.request.Request("http://localhost:11434/api/generate", body,
                                         {"Content-Type": "application/json"})
            text = json.load(urllib.request.urlopen(req, timeout=120))["response"].strip()
            s.prompt = f"1980s saturday morning cartoon, cel shaded, bold outlines, VHS grain, {text}"
        except Exception as e:  # Ollama nicht erreichbar -> Standardprompt behalten
            print(f"[storyboard] Ollama nicht verfügbar ({e}); nutze Standardprompts")
            return

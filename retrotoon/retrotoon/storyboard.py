"""Storyboard: Lyrics + Beats -> Szenenliste. Optional per lokalem LLM (Ollama).

Lyrics-Format: `[Abschnitt]`-Überschriften, eine Zeile pro Phrase. Optional kann eine Zeile
mit `mm:ss ` beginnen, um die Zeit festzulegen; alle anderen werden proportional zur
Textlänge über den Gesangsbereich verteilt.
"""
import json
import re
import urllib.request
from dataclasses import dataclass

import numpy as np

from .audio import AudioInfo

STYLE = "1980s saturday morning cartoon style, cel shaded, bold outlines, flat vivid colors, VHS grain"

# Setting -> Bildbeschreibung (fürs Diffusion-Backend; das prozedurale nutzt den Key)
SETTINGS = {
    "sunset_grid": "neon sunset over a glowing perspective grid",
    "city_night": "retro skyline at night with neon signs",
    "palms": "palm trees against a magenta-orange gradient sky",
    "space": "starfield with a ringed planet and laser beams",
    "auto": "retro sports car on a neon highway at dusk",
    "tanke": "gas station at night, huge glowing price sign reading 2,20, a fuel pump",
    "bahnhof": "empty train platform at night, cold wind, sign Gleis 3, rails vanishing into the dark",
    "anzeige": "LED departure board showing 60 minutes delay, a squirrel sitting on the rails",
    "regen": "heavy neon rain in a city street, a bicycle",
    "haus": "front door of a house at night, door slamming shut",
    "endstation": "giant flashing neon sign ENDSTATION WAHNSINN over a sunset grid",
}

# Reihenfolge = Priorität; erster Treffer gewinnt
KEYWORDS = [
    ("anzeige", r"Eichhörnchen|Verspätung|Laufschrift"),
    ("regen", r"Fahrrad|regnet"),
    ("haus", r"Tür|Sound effect|Macht doch"),
    ("tanke", r"Tanke|Liter|Benzin|Portemonnaie|Tankanzeige|Luxus"),
    ("auto", r"Auto|Schlüssel|Karre|park"),
    ("bahnhof", r"Gleis|Bahnhof|Ticket|Wind|Bahn|pendeln"),
]


@dataclass
class Scene:
    start: float
    end: float
    setting: str
    prompt: str
    lyric: str
    section: str = ""


def _pick(text: str, section: str, prev: str) -> str:
    if section.lower().startswith(("chorus", "refrain")) or text.startswith("Endstation"):
        return "endstation"
    for key, rx in KEYWORDS:
        if re.search(rx, text, re.I):
            return key
    return prev


def _parse(text: str):
    """-> Liste (abschnitt, zeile, feste_zeit|None)"""
    out, section = [], ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.fullmatch(r"\[(.+)\]", line)
        if m:
            section = m.group(1)
            continue
        t = None
        m = re.match(r"(\d+):(\d\d(?:\.\d+)?)\s+(.*)", line)
        if m:
            t, line = int(m.group(1)) * 60 + float(m.group(2)), m.group(3)
        out.append((section, line, t))
    return out


def _snap(t: float, beats: np.ndarray) -> float:
    return float(beats[int(np.argmin(np.abs(beats - t)))]) if len(beats) else t


def build(info: AudioInfo, lyrics: str, character: str, bars_per_scene: int = 4,
          llm: str | None = None, vocal_start: float = 0.0, vocal_end: float | None = None) -> list[Scene]:
    items = _parse(lyrics)
    if not items:
        return _generic(info, character, bars_per_scene)

    end = vocal_end if vocal_end is not None else info.duration
    # Gewichte: Textlänge, neuer Abschnitt = kurze Pause
    w, prev_sec = [], None
    for sec, line, _ in items:
        w.append(max(len(line), 14) + (14 if sec != prev_sec else 0))
        prev_sec = sec
    cum = np.cumsum([0] + w) / sum(w)
    starts = [vocal_start + (end - vocal_start) * c for c in cum[:-1]]
    for i, (_, _, t) in enumerate(items):  # feste Zeiten überschreiben
        if t is not None:
            starts[i] = t
    starts = [_snap(s, info.beats) if i else 0.0 for i, s in enumerate(starts)]
    ends = starts[1:] + [info.duration]

    scenes, setting = [], "sunset_grid"
    for (sec, line, _), a, b in zip(items, starts, ends):
        setting = _pick(line, sec, setting)
        if line.startswith("(Sound effect"):
            line = "*BAM!*"
        prompt = f"{STYLE}, {character}, {SETTINGS[setting]}"
        scenes.append(Scene(a, b, setting, prompt, line, sec))
    scenes = [s for s in scenes if s.start < info.duration]
    if llm:
        _refine_with_ollama(scenes, character, llm)
    return scenes


def _generic(info: AudioInfo, character: str, bars: int) -> list[Scene]:
    """Ohne Lyrics: Szenenwechsel alle `bars` Takte durch die Standard-Looks."""
    keys = ["sunset_grid", "city_night", "palms", "space"]
    cuts = [b for b in info.beats[::bars * 4] if b < info.duration] + [info.duration]
    if cuts[0] > 0.5:
        cuts.insert(0, 0.0)
    return [Scene(float(a), float(b), keys[i % 4], f"{STYLE}, {character}, {SETTINGS[keys[i % 4]]}", "")
            for i, (a, b) in enumerate(zip(cuts, cuts[1:]))]


def _refine_with_ollama(scenes: list[Scene], character: str, model: str) -> None:
    """Lässt ein lokales LLM die Bildprompts passend zu den Lyrics ausformulieren."""
    for s in scenes:
        if not s.lyric:
            continue
        body = json.dumps({
            "model": model, "stream": False,
            "prompt": (f"Write one short image prompt (max 30 words, English) for a 1980s "
                       f"cartoon music video scene. Character: {character}. Setting: {SETTINGS[s.setting]}. "
                       f"Lyric (German): \"{s.lyric}\". Output only the prompt."),
        }).encode()
        try:
            req = urllib.request.Request("http://localhost:11434/api/generate", body,
                                         {"Content-Type": "application/json"})
            text = json.load(urllib.request.urlopen(req, timeout=120))["response"].strip()
            s.prompt = f"{STYLE}, {text}"
        except Exception as e:  # Ollama nicht erreichbar -> Standardprompt behalten
            print(f"[storyboard] Ollama nicht verfügbar ({e}); nutze Standardprompts")
            return

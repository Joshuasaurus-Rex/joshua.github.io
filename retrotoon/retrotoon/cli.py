import argparse
import json
from dataclasses import asdict
from pathlib import Path

from . import audio, compose, storyboard
from .render import get_renderer


def main():
    ap = argparse.ArgumentParser(prog="retrotoon", description="Musikvideo im 80er-Cartoon-Stil")
    ap.add_argument("song", help="Audiodatei (mp3/wav/…)")
    ap.add_argument("-l", "--lyrics", help="Textdatei mit Lyrics (eine Zeile pro Phrase)")
    ap.add_argument("-o", "--out", default="video.mp4")
    ap.add_argument("--character", default="a cool cartoon hero with sunglasses and a blue quiff")
    ap.add_argument("--backend", choices=["procedural", "diffusion"], default="procedural")
    ap.add_argument("--model", default="stabilityai/sdxl-turbo", help="Diffusion-Modell")
    ap.add_argument("--lora", help="Optionales LoRA für den Stil")
    ap.add_argument("--llm", help="Ollama-Modell für Storyboard-Prompts, z.B. llama3.2")
    ap.add_argument("--bars", type=int, default=4, help="Takte pro Szene")
    ap.add_argument("--limit", type=float, help="Nur die ersten N Sekunden rendern")
    ap.add_argument("--no-vhs", action="store_true")
    a = ap.parse_args()

    info = audio.analyze(a.song)
    if a.limit:
        info.duration = min(info.duration, a.limit)
    print(f"Dauer {info.duration:.1f}s · {info.bpm:.0f} BPM · {len(info.beats)} Beats")

    lyrics = Path(a.lyrics).read_text() if a.lyrics else ""
    scenes = storyboard.build(info, lyrics, a.character, a.bars, a.llm)
    sb = Path(a.out).with_suffix(".storyboard.json")
    sb.write_text(json.dumps([asdict(s) for s in scenes], indent=2, ensure_ascii=False))
    print(f"{len(scenes)} Szenen -> {sb}")

    r = get_renderer(a.backend, model=a.model, lora=a.lora)
    compose.render(info, scenes, r, a.song, a.out, vhs=not a.no_vhs)
    print(f"Fertig: {a.out}")


if __name__ == "__main__":
    main()

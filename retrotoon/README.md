# retrotoon

Lokale Pipeline für Musikvideos im 80er-Retro-Cartoon-Stil.

```
Song → Beat-/BPM-Analyse → Storyboard (optional lokales LLM) → Renderer → ffmpeg (VHS-Look) → MP4
```

## Benutzung

Voraussetzungen: Python 3.10+, `ffmpeg`, `pip install -r requirements.txt`.

```bash
python -m retrotoon song.mp3 -l lyrics.txt -o video.mp4          # prozedurales Backend, läuft überall
python -m retrotoon song.mp3 --limit 20 --bars 2                  # nur 20 s, Szenenwechsel alle 2 Takte
python -m retrotoon song.mp3 --backend diffusion --llm llama3.2   # lokale KI-Keyframes + Ollama-Prompts
```

## Backends

- `procedural` – Pillow-gezeichnete Synthwave-Szenen, Figur hüpft im Beat, Mund folgt der Lautstärke. Keine GPU nötig.
- `diffusion` – ein Keyframe pro Szene via `diffusers` (Standard: `sdxl-turbo`, optional `--lora` für den Stil), animiert mit Beat-Zoom und Schwenk. GPU empfohlen.

Das Storyboard landet als `<out>.storyboard.json` neben dem Video und kann angepasst werden.

## Realistischer Look (lokal, GPU)

```bash
python -m retrotoon song.mp3 -l songs/endstation_wahnsinn.txt --backend video --look realistic -o video.mp4 --vocal-end 190
```

Pro Szene: SDXL-Keyframe → LTX-Video-Clip (Image-to-Video). Clips werden in `cache/` abgelegt, ein erneuter Lauf
rechnet nur Neues. AMD (z. B. RX 7900 XT): ROCm-Build von PyTorch installieren, danach
`pip install diffusers transformers accelerate sentencepiece`. **Noch ungetestet** (kein GPU in der Entwicklungsumgebung).

## Zeitsteuerung der Lyrics

Anker in der Lyrics-Datei: `[Chorus @1:00]` oder `0:42 Zeile`. Dazwischen wird nach Textlänge verteilt.

## Nächste Schritte

- Figurenkonsistenz (LoRA/IP-Adapter), Image-to-Video-Modell für echte Bewegung
- Storyboard-JSON wieder einlesen, um Szenen von Hand zu ändern
- Lippensynchronität aus Lyrics-Timestamps (Whisper)

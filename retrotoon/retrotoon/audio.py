"""Audio-Analyse ohne schwere Abhängigkeiten: ffmpeg dekodiert, numpy rechnet."""
import subprocess
from dataclasses import dataclass

import numpy as np

SR = 22050
HOP = 512


@dataclass
class AudioInfo:
    duration: float
    bpm: float
    beats: np.ndarray  # Beat-Zeitpunkte in Sekunden
    energy: np.ndarray  # normierte Lautstärke je Hop (0..1)
    hop_s: float


def decode(path: str) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def analyze(path: str) -> AudioInfo:
    y = decode(path)
    n = len(y) // HOP
    frames = y[: n * HOP].reshape(n, HOP)
    energy = np.sqrt((frames ** 2).mean(axis=1))
    energy = energy / (energy.max() + 1e-9)

    # Onset-Stärke = positive Energieänderung
    flux = np.maximum(np.diff(energy, prepend=energy[0]), 0)
    hop_s = HOP / SR

    # Tempo per Autokorrelation im Bereich 70–180 BPM
    ac = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
    lo, hi = int(60 / 180 / hop_s), int(60 / 70 / hop_s)
    lag = lo + int(np.argmax(ac[lo:hi])) if hi < len(ac) else max(lo, 1)
    period = lag * hop_s
    bpm = 60.0 / period

    # Beat-Raster: Phase wählen, die am besten auf Onsets passt
    steps = max(int(round(period / hop_s)), 1)
    best_phase = max(range(steps), key=lambda p: flux[p::steps].sum())
    beats = np.arange(best_phase * hop_s, len(y) / SR, period)
    return AudioInfo(len(y) / SR, bpm, beats, energy, hop_s)

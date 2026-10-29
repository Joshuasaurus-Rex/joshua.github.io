"""Frames rendern und per ffmpeg mit Audio + Retro-Filtern (VHS-Look) zusammensetzen."""
import subprocess

import numpy as np

from .audio import AudioInfo

VHS = ("scale=1280:720:flags=neighbor,"
       "noise=alls=14:allf=t,"
       "eq=saturation=1.35:contrast=1.08,"
       "gblur=sigma=0.6,"
       "vignette=PI/5")


def render(info: AudioInfo, scenes, renderer, audio_path: str, out: str, vhs: bool = True):
    fps = renderer.fps
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "640x360",
           "-r", str(fps), "-i", "-", "-i", audio_path]
    if vhs:
        cmd += ["-vf", VHS]
    cmd += ["-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(info.duration * fps)
    beats = info.beats
    for i in range(n):
        t = i / fps
        scene = next((s for s in scenes if s.start <= t < s.end), scenes[-1])
        k = max(int(np.searchsorted(beats, t, side="right")) - 1, 0)
        period = beats[1] - beats[0] if len(beats) > 1 else 0.5
        phase = min(max((t - beats[k]) / period, 0.0), 1.0)
        e = float(info.energy[min(int(t / info.hop_s), len(info.energy) - 1)])
        p.stdin.write(renderer.frame(scene, t, phase, e).tobytes())
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError("ffmpeg fehlgeschlagen")

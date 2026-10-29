"""Realistisches Backend: Bildmodell (Keyframe) + Image-to-Video-Modell (Bewegung), komplett lokal.

Pro Szene: Prompt -> SDXL-Keyframe -> LTX-Video-Clip in Szenenlänge. Clips landen im Cache und
werden bei erneutem Lauf nicht neu berechnet. AMD: ROCm-PyTorch installieren (torch.cuda ist dort
die HIP-Schnittstelle, der Code braucht keine Änderung).

Benötigt: pip install torch diffusers transformers accelerate sentencepiece imageio imageio-ffmpeg
"""
import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

SIZE = (704, 384)  # Vielfache von 32
VIDEO_FPS = 24
NEG = "cartoon, drawing, text, watermark, blurry, deformed, extra limbs, low quality"


class VideoRenderer:
    def __init__(self, fps: int = VIDEO_FPS, model: str = "stabilityai/stable-diffusion-xl-base-1.0",
                 lora: str | None = None, cache: str = "cache", video_model: str = "Lightricks/LTX-Video", **_):
        self.size = SIZE
        self.fps = fps
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.model, self.lora, self.video_model = model, lora, video_model
        self._clips: dict[int, np.ndarray] = {}

    # --- Modelle nacheinander laden, damit 20 GB VRAM reichen -----------------
    def _keyframes(self, scenes):
        import torch
        from diffusers import AutoPipelineForText2Image

        todo = [s for s in scenes if not self._clip_path(s).exists() and not self._img_path(s).exists()]
        if not todo:
            return
        pipe = AutoPipelineForText2Image.from_pretrained(self.model, torch_dtype=torch.float16).to("cuda")
        if self.lora:
            pipe.load_lora_weights(self.lora)
        for i, s in enumerate(todo):
            print(f"[keyframe {i + 1}/{len(todo)}] {s.setting}")
            g = torch.Generator("cuda").manual_seed(1234)  # fester Seed -> ähnlichere Szenen
            img = pipe(prompt=s.prompt, negative_prompt=NEG, width=1024, height=576,
                       num_inference_steps=30, generator=g).images[0]
            img.save(self._img_path(s))
        del pipe
        torch.cuda.empty_cache()

    def _animate(self, scenes):
        import torch
        from diffusers import LTXImageToVideoPipeline

        todo = [s for s in scenes if not self._clip_path(s).exists()]
        if not todo:
            return
        pipe = LTXImageToVideoPipeline.from_pretrained(self.video_model, torch_dtype=torch.bfloat16)
        pipe.enable_model_cpu_offload()
        for i, s in enumerate(todo):
            n = min(max(int((s.end - s.start) * VIDEO_FPS) // 8 * 8 + 1, 25), 161)  # 8n+1 Frames
            print(f"[clip {i + 1}/{len(todo)}] {s.setting} {n} Frames")
            img = Image.open(self._img_path(s)).convert("RGB").resize(SIZE)
            frames = pipe(image=img, prompt=s.prompt, negative_prompt=NEG, width=SIZE[0], height=SIZE[1],
                          num_frames=n, num_inference_steps=40).frames[0]
            np.save(self._clip_path(s), np.stack([np.asarray(f) for f in frames]))
        del pipe
        torch.cuda.empty_cache()

    def prepare(self, scenes):
        self._keyframes(scenes)
        self._animate(scenes)

    # --- Abruf pro Videoframe -------------------------------------------------
    def _key(self, s):
        return hashlib.md5(f"{s.prompt}|{round(s.end - s.start, 1)}".encode()).hexdigest()[:12]

    def _img_path(self, s):
        return self.cache / f"{self._key(s)}.png"

    def _clip_path(self, s):
        return self.cache / f"{self._key(s)}.npy"

    def frame(self, scene, t, beat_phase, energy) -> Image.Image:
        k = id(scene)
        if k not in self._clips:
            self._clips[k] = np.load(self._clip_path(scene))
        clip = self._clips[k]
        i = int((t - scene.start) * VIDEO_FPS)
        n = len(clip)
        i = i % (2 * n - 2) if n > 1 else 0  # Ping-Pong, falls der Clip kürzer ist als die Szene
        i = i if i < n else 2 * n - 2 - i
        return Image.fromarray(clip[i])

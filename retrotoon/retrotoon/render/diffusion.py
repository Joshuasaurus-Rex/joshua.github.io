"""Backend mit lokalem Bildmodell (diffusers): ein Keyframe pro Szene + Ken-Burns-/Parallax-Animation.

Benötigt: pip install torch diffusers transformers accelerate  (GPU empfohlen).
Modell per --model wählbar, z.B. "stabilityai/sdxl-turbo" (schnell, wenig VRAM).
"""
import math

from PIL import Image

W, H = 640, 360


class DiffusionRenderer:
    def __init__(self, fps: int = 12, model: str = "stabilityai/sdxl-turbo", lora: str | None = None, **_):
        import torch
        from diffusers import AutoPipelineForText2Image

        self.fps = fps
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if dev == "cuda" else torch.float32
        self.pipe = AutoPipelineForText2Image.from_pretrained(model, torch_dtype=dtype).to(dev)
        if lora:  # z.B. ein 80er-Cartoon-LoRA für konsistenten Stil
            self.pipe.load_lora_weights(lora)
        self._cache: dict[int, Image.Image] = {}

    def _keyframe(self, scene) -> Image.Image:
        key = id(scene)
        if key not in self._cache:
            img = self.pipe(prompt=scene.prompt, num_inference_steps=4, guidance_scale=0.0,
                            width=1024, height=576).images[0]
            self._cache[key] = img.resize((int(W * 1.25), int(H * 1.25)))
        return self._cache[key]

    def frame(self, scene, t, beat_phase, energy) -> Image.Image:
        big = self._keyframe(scene)
        # Beat-Zoom + sanftes Schwenken
        zoom = 1 + 0.04 * (1 - beat_phase) ** 2 + 0.01 * energy
        cw, ch = W / zoom, H / zoom
        pan = math.sin(t * 0.7) * 20
        x0 = (big.width - cw) / 2 + pan
        y0 = (big.height - ch) / 2
        return big.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.LANCZOS)

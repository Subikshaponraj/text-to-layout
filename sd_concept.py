"""Optional: 512px concept sketch from Stable Diffusion 1.5 + your trained LoRA (model/).

Your LoRA was trained on black-and-white CAD plans, so this is a sketch of the *style of plan the model learned*,
not the exact-dimension coloured plan - that comes from layout.py/renderer.py.
"""
from __future__ import annotations


def generate_concept(prompt, out_path, lora_dir="model", base_model="runwayml/stable-diffusion-v1-5",
                     steps=30, guidance=7.5, seed=None, device=None):
    import torch
    from diffusers import StableDiffusionPipeline
    from peft import PeftModel

    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.float16 if device == "cuda" else torch.float32
    pipe = StableDiffusionPipeline.from_pretrained(base_model, torch_dtype=dtype, safety_checker=None)
    pipe.unet = PeftModel.from_pretrained(pipe.unet, lora_dir).merge_and_unload()
    pipe = pipe.to(device)
    gen = torch.Generator(device).manual_seed(seed) if seed is not None else None
    pipe(prompt, num_inference_steps=steps, guidance_scale=guidance, height=512, width=512,
         generator=gen).images[0].save(out_path)
    return out_path

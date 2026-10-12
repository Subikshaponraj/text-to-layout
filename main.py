#!/usr/bin/env python3
"""text -> (local LLM) requirements JSON -> layout -> coloured floor-plan PNG  [+ LoRA concept sketch]

  python main.py "2BHK apartment with balcony" -o outputs/plan.png --llm-model qwen2.5:7b
  python main.py "1BHK with balcony" --no-llm
  python main.py "3BHK" --sd                     # also writes <name>_concept.png (needs torch/diffusers/peft + GPU)
  python main.py --req-json my_requirements.json # skip extraction, use a dataset-style JSON
"""
import argparse
import json
import os

from extractor import extract_requirements, sd_prompt
from layout import generate_layout, validate
from renderer import render


def build(text, out, use_llm=True, llm_url=None, llm_model=None, req=None, sd=False,
          lora_dir="model", seed=None, steps=30):
    src = "json file" if req else None
    if req is None:
        req, src = extract_requirements(text, use_llm, llm_url, llm_model)
    lay = generate_layout(req)
    issues = validate(lay)
    render(lay, out)
    base = os.path.splitext(out)[0]
    json.dump(req, open(base + "_requirements.json", "w"), indent=2)
    res = {"plan": out, "requirements": req, "source": src, "size": (lay.outer_w, lay.outer_h),
           "area": lay.total_area, "notes": lay.notes, "issues": issues}
    if sd:
        from sd_concept import generate_concept
        res["concept"] = generate_concept(sd_prompt(req), base + "_concept.png", lora_dir, seed=seed, steps=steps)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("description", nargs="?", default="")
    ap.add_argument("-o", "--output", default="outputs/floor_plan.png")
    ap.add_argument("--no-llm", action="store_true", help="use the regex parser instead of the local LLM")
    ap.add_argument("--llm-url", help="default $LLM_URL or http://localhost:11434 (Ollama); end with /v1 for OpenAI-style")
    ap.add_argument("--llm-model", help="default $LLM_MODEL or llama3.1")
    ap.add_argument("--req-json", help="dataset-style requirements JSON (skips extraction)")
    ap.add_argument("--sd", action="store_true")
    ap.add_argument("--lora-dir", default="model")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--steps", type=int, default=30)
    a = ap.parse_args()
    req = json.load(open(a.req_json)) if a.req_json else None
    if not req and not a.description:
        ap.error("give a description or --req-json")
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    r = build(a.description, a.output, not a.no_llm, a.llm_url, a.llm_model, req, a.sd, a.lora_dir, a.seed, a.steps)
    print(f"Saved {r['plan']}  {r['size'][0]:g} x {r['size'][1]:g} ft, {r['area']} sq ft  [requirements: {r['source']}]")
    for n in r["notes"]: print("note:", n)
    for i in r["issues"]: print("WARNING:", i)

"""Text -> requirements JSON (same schema as floor_plan_dataset/prompts_json).

1. Asks your local LLM (Ollama native API, or any OpenAI-compatible server such as LM Studio / llama.cpp / vLLM).
2. If no LLM is reachable or it returns bad JSON, falls back to a regex parser, so the pipeline never blocks.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

SCHEMA_EXAMPLE = {
    "bhk": 2, "type": "house", "facing": None,
    "rooms": {"living_room": True, "hall": False, "master_bedroom": True, "bedroom_count": 1,
              "kitchen": True, "toilet": True, "bathroom_count": 1, "puja": False, "study": False,
              "balcony": True, "dining": False, "portico": False, "utility": False, "corridor": False},
    "style": {"vastu": False, "open_kitchen": False, "attached_bathroom": False},
    "area_sqft": None,
}
SYSTEM = (
    "You extract floor-plan requirements from a user's description. Reply with ONE JSON object only, "
    "no prose, using exactly this schema and key names:\n" + json.dumps(SCHEMA_EXAMPLE) + "\n"
    "Rules: bhk = number of bedrooms (integer) or null if not stated; bedroom_count = bedrooms OTHER than the "
    "master bedroom; booleans true only if the user asked for that room; area_sqft = number or null; "
    "facing = north/south/east/west or null."
)
_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def default_requirements(raw=""):
    req = json.loads(json.dumps(SCHEMA_EXAMPLE))
    req["bhk"] = None
    req["rooms"].update(bedroom_count=0, bathroom_count=0, balcony=False)
    req["raw_prompt"] = raw
    return req


def regex_extract(text: str) -> dict:
    t = text.lower()
    req = default_requirements(text)
    r = req["rooms"]
    m = re.search(r"(\d+|one|two|three|four|five)\s*-?\s*bhk", t) or \
        re.search(r"(\d+|one|two|three|four|five)\s*-?\s*bed(?:room)?s?", t)
    if m:
        v = m.group(1)
        req["bhk"] = int(v) if v.isdigit() else _NUM[v]
        r["bedroom_count"] = max(0, req["bhk"] - 1)
    for key, pat in {"balcony": r"balcon", "study": r"\bstudy\b", "puja": r"puja|pooja|prayer",
                     "dining": r"dining", "hall": r"\bhall\b", "portico": r"portico|porch",
                     "utility": r"utility|laundry", "corridor": r"corridor|passage"}.items():
        r[key] = bool(re.search(pat, t))
    if "studio" in t:
        req["type"] = "studio"
    m = re.search(r"(\d[\d,]*)\s*(?:sq\.?\s*ft|sqft|square f)", t)
    if m:
        req["area_sqft"] = int(m.group(1).replace(",", ""))
    for f in ("north", "south", "east", "west"):
        if f + "-facing" in t or f + " facing" in t:
            req["facing"] = f
    return req


def _post(url, payload, timeout):
    rq = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(rq, timeout=timeout) as resp:
        return json.loads(resp.read())


def llm_extract(text, base_url=None, model=None, timeout=60):
    base_url = (base_url or os.environ.get("LLM_URL") or "http://localhost:11434").rstrip("/")
    model = model or os.environ.get("LLM_MODEL") or "llama3.1"
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]
    if base_url.endswith("/v1"):   # OpenAI-compatible
        out = _post(base_url + "/chat/completions",
                    {"model": model, "messages": msgs, "temperature": 0,
                     "response_format": {"type": "json_object"}}, timeout)
        content = out["choices"][0]["message"]["content"]
    else:                          # Ollama
        out = _post(base_url + "/api/chat", {"model": model, "messages": msgs, "stream": False,
                                             "format": "json", "options": {"temperature": 0}}, timeout)
        content = out["message"]["content"]
    m = re.search(r"\{.*\}", content, re.S)
    return json.loads(m.group(0))


def normalize(req: dict, raw: str) -> dict:
    base = default_requirements(raw)
    base["bhk"] = int(req["bhk"]) if str(req.get("bhk") or "").isdigit() else None
    base["type"] = req.get("type") or "house"
    base["facing"] = req.get("facing")
    for k in base["rooms"]:
        v = (req.get("rooms") or {}).get(k, base["rooms"][k])
        base["rooms"][k] = int(v or 0) if k.endswith("_count") else bool(v)
    base["style"].update({k: bool(v) for k, v in (req.get("style") or {}).items() if k in base["style"]})
    try:
        base["area_sqft"] = float(req["area_sqft"]) if req.get("area_sqft") else None
    except (TypeError, ValueError):
        base["area_sqft"] = None
    return base


def extract_requirements(text, use_llm=True, llm_url=None, llm_model=None):
    """Returns (requirements dict, source string)."""
    if use_llm:
        try:
            return normalize(llm_extract(text, llm_url, llm_model), text), "llm"
        except Exception as e:  # unreachable server, timeout, malformed JSON ...
            return regex_extract(text), f"regex (LLM failed: {type(e).__name__}: {e})"
    return regex_extract(text), "regex"


def sd_prompt(req: dict) -> str:
    """Caption in the exact style of floor_plan_dataset/prompts_enriched, for the LoRA."""
    r = req["rooms"]
    names = []
    if r.get("master_bedroom"): names.append("master bedroom")
    if r.get("bedroom_count"): names.append("bedroom")
    for key, label in (("hall", "hall"), ("living_room", "living room"), ("kitchen", "kitchen"),
                       ("dining", "dining room"), ("toilet", "toilet"), ("bathroom_count", "bathroom"),
                       ("study", "study"), ("puja", "puja room"), ("balcony", "balcony"),
                       ("portico", "portico"), ("utility", "utility room"), ("corridor", "corridor")):
        if r.get(key): names.append(label)
    kind = f"{req['bhk']}BHK house" if req.get("bhk") else "house"
    return (f"CAD architectural floor plan of a {kind}, with rooms: {', '.join(names)}, top-down view black and "
            "white line drawing professional blueprint technical drawing room labels dimension annotations clean lines")

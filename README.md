# Text-to-Design v2

text -> **local LLM** -> requirements JSON (same schema as `floor_plan_dataset/prompts_json`) -> layout -> coloured plan PNG
(reference.png style) -> optional **LoRA concept sketch**.

```
pip install pillow matplotlib                      # core
python main.py "2BHK with balcony" --llm-model qwen2.5:7b          # Ollama on localhost:11434
python main.py "2BHK with balcony" --llm-url http://localhost:1234/v1 --llm-model <name>   # LM Studio / llama.cpp / vLLM
python main.py "2BHK with balcony" --no-llm        # regex parser, no LLM
python main.py "3BHK" --sd --seed 7                # + model/ LoRA concept (pip install torch diffusers transformers accelerate peft; GPU)
python -m unittest tests/test_pipeline.py
```
* If the LLM is unreachable or returns bad JSON the regex parser is used automatically.
* `layout.py`: 1/2/3BHK templates. Interior sizes are exact; exterior wall 1 ft, partitions 0.5 ft. Doors are only created
  on walls two rooms really share (or the exterior), and `validate()` checks overlap, minimum sizes, windows and that every
  room is reachable from the main entrance.
* Supported: bhk 1-3, balcony, dining (labels the foyer), `area_sqft` (scales the template 0.8x-1.35x).
  Study / puja / utility / portico are reported as "not placed".
* The LoRA was trained on black-and-white CAD plans (see `model/training_config.json`), so `--sd` gives a concept sketch in
  that style; exact dimensions always come from the geometry.

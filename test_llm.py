from llm_parser import parse_prompt_to_router_json
import json

prompt = "Block youtube.com on WecimsPC on weekdays from 19:00 to 21:00"
result = parse_prompt_to_router_json(prompt)
print(json.dumps(result, indent=2))
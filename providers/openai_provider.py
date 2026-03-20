import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def run_openai(prompt, model="gpt-4o-mini"):

    started_at = time.perf_counter()

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    latency_ms = (time.perf_counter() - started_at) * 1000

    text = response.choices[0].message.content or ""

    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", None) if usage else None
    output_tokens = getattr(usage, "completion_tokens", None) if usage else None

    parsed_output_json = {}
    parse_status = "parse_error"
    error_message = None

    try:
        parsed_candidate = json.loads(text)
        if isinstance(parsed_candidate, dict):
            parsed_output_json = parsed_candidate
            parse_status = "success"
        else:
            error_message = "Parsed JSON is not an object"
    except Exception as exc:
        error_message = str(exc)

    return {
        "provider": "openai",
        "model": model,
        "raw_response_text": text,
        "parsed_output_json": parsed_output_json,
        "parse_status": parse_status,
        "error_message": error_message,
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost": None,
    }

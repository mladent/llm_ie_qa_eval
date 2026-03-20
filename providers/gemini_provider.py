import os
import json
import time
from google import genai
from dotenv import load_dotenv

load_dotenv()

def run_gemini(
    prompt,
    model="gemini-1.5-pro",
    temperature=0.0,
    top_p=1.0,
    max_tokens=2048,
):

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    generate_config = genai.types.GenerateContentConfig(
        temperature=temperature,
        top_p=top_p,
        max_output_tokens=max_tokens,
    )

    started_at = time.perf_counter()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=generate_config,
    )
    latency_ms = (time.perf_counter() - started_at) * 1000

    text = getattr(response, "text", None) or ""

    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
    output_tokens = getattr(usage, "candidates_token_count", None) if usage else None

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
    except json.JSONDecodeError as exc:
        error_message = f"JSON decode error: {exc}"

    return {
        "provider": "gemini",
        "model": model,
        "raw_response_text": text,
        "parsed_output_json": parsed_output_json,
        "parse_status": parse_status,
        "error_message": error_message,
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost": None,
        "model_params_used": {
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        },
    }

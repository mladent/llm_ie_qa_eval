import os
import json
import time
from google import genai
from dotenv import load_dotenv

load_dotenv()

def run_gemini(prompt, model="gemini-1.5-pro"):

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    started_at = time.perf_counter()
    response = client.models.generate_content(model=model, contents=prompt)
    latency_ms = (time.perf_counter() - started_at) * 1000

    text = getattr(response, "text", None)
    if not text:
        text = ""

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
        "provider": "gemini",
        "model": model,
        "raw_response_text": text,
        "parsed_output_json": parsed_output_json,
        "parse_status": parse_status,
        "error_message": error_message,
        "latency_ms": latency_ms,
        "input_tokens": None,
        "output_tokens": None,
        "estimated_cost": None,
    }

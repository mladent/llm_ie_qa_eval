import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

def run_gemini(prompt, model="gemini-1.5-pro"):

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(model=model, contents=prompt)

    text = getattr(response, "text", None)
    if not text:
        text = json.dumps({"error": "Gemini response had no text"})

    try:
        return json.loads(text)
    except:
        return {"error": text}

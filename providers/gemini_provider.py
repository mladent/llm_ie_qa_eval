import os
import json
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def run_gemini(prompt, model="gemini-1.5-pro"):

    model = genai.GenerativeModel(model)

    response = model.generate_content(prompt)

    text = response.text

    try:
        return json.loads(text)
    except:
        return {"error": text}

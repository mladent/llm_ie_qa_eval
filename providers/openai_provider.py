import os
import json
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def run_openai(prompt, model="gpt-4o-mini"):
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    text = response.choices[0].message.content

    try:
        return json.loads(text)
    except:
        return {"error": text}

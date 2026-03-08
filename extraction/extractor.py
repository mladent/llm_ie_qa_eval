from providers.openai_provider import run_openai
from providers.gemini_provider import run_gemini

def run_extraction(provider, prompt):

    if provider == "openai":
        return run_openai(prompt)

    if provider == "gemini":
        return run_gemini(prompt)

    raise ValueError("Unknown provider")

from providers.openai_provider import run_openai
from providers.gemini_provider import run_gemini


def run_extraction(provider, prompt, model=None):

    if provider == "openai":
        return run_openai(prompt, model=model or "gpt-4o-mini")

    if provider == "gemini":
        return run_gemini(prompt, model=model or "gemini-1.5-pro")

    raise ValueError("Unknown provider")

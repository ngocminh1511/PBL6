"""Thin, provider-agnostic LLM wrapper used by query rewriting, reranking,
and answer generation. Reads provider/model/key from env vars so no
credentials are hard-coded:

  LLM_PROVIDER      "anthropic" (default), "openai", or "gemini"
  ANTHROPIC_API_KEY / ANTHROPIC_MODEL   (default model: claude-sonnet-4-5)
  OPENAI_API_KEY    / OPENAI_MODEL      (default model: gpt-4o-mini)
  GEMINI_API_KEY    / GEMINI_MODEL      (default model: gemini-3.6-flash,
                                         free-tier friendly on Google AI Studio)
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def complete(system: str, user: str, max_tokens: int = 1024) -> str:
    provider = os.environ.get("LLM_PROVIDER", "gemini")

    if provider == "gemini":
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Set GEMINI_API_KEY to use LLM_PROVIDER=gemini.")
        client = genai.Client(api_key=api_key)
        model = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
        resp = client.models.generate_content(
            model=model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
                # Thinking tokens count against max_output_tokens; without
                # disabling this, short-budget calls (rewrite/rerank) can be
                # truncated by MAX_TOKENS before any visible text is emitted.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        return resp.text

    if provider == "anthropic":
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Set ANTHROPIC_API_KEY (or LLM_PROVIDER=openai + OPENAI_API_KEY) "
                "to use the LLM-backed pipeline stages."
            )
        client = anthropic.Anthropic(api_key=api_key)
        model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")

    if provider == "openai":
        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Set OPENAI_API_KEY to use LLM_PROVIDER=openai.")
        client = OpenAI(api_key=api_key)
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content

    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}")

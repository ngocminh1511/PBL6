"""Provider field names shared by runtime configuration and scoped clients."""

CLOUD_API_PROVIDERS = frozenset({"openrouter", "groq", "qwen"})
DEFAULT_CLOUD_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    # Alibaba Cloud endpoints depend on the account's workspace and region.
    "qwen": "",
}


def model_field(provider):
    return "local_llm_model" if provider == "local" else provider + "_model"


def secret_field(provider):
    return "local_llm_api_key" if provider == "local" else provider + "_api_key"


def base_url_field(provider):
    if provider == "local":
        return "local_llm_base_url"
    if provider in CLOUD_API_PROVIDERS:
        return provider + "_base_url"
    return None

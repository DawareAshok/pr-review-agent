from pr_reviewer.providers.base import BaseLLMProvider
from pr_reviewer.providers.openai_provider import OpenAIProvider
from pr_reviewer.providers.gemini_provider import GeminiProvider
from pr_reviewer.providers.anthropic_provider import AnthropicProvider
from pr_reviewer.providers.mock_provider import MockLLMProvider


def get_provider(provider_name: str, model_name: str | None = None) -> BaseLLMProvider:
    """Factory to instantiate the appropriate LLM provider."""
    normalized = (provider_name or "openai").lower().strip()
    if normalized in ("openai", "gpt"):
        return OpenAIProvider(model_name=model_name)
    elif normalized in ("gemini", "google"):
        return GeminiProvider(model_name=model_name)
    elif normalized in ("anthropic", "claude"):
        return AnthropicProvider(model_name=model_name)
    elif normalized in ("mock", "test", "offline"):
        return MockLLMProvider(model_name=model_name)
    else:
        raise ValueError(
            f"Unsupported provider '{provider_name}'. Supported options are: 'openai', 'gemini', 'anthropic', 'mock'."
        )


__all__ = [
    "BaseLLMProvider",
    "OpenAIProvider",
    "GeminiProvider",
    "AnthropicProvider",
    "MockLLMProvider",
    "get_provider",
]

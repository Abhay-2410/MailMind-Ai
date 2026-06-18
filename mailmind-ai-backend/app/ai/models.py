from dataclasses import dataclass
from enum import Enum


class AIProviderName(str, Enum):
    OPENROUTER = "openrouter"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


@dataclass(frozen=True)
class AIModelDefinition:
    id: str
    name: str
    provider: AIProviderName
    description: str
    is_default: bool = False


DEFAULT_MODELS: list[AIModelDefinition] = [
    AIModelDefinition(
        id="deepseek/deepseek-chat",
        name="DeepSeek Chat",
        provider=AIProviderName.OPENROUTER,
        description="Fast, cost-effective general purpose model",
        is_default=True,
    ),
    AIModelDefinition(
        id="qwen/qwen-2.5-72b-instruct",
        name="Qwen 2.5 72B",
        provider=AIProviderName.OPENROUTER,
        description="Strong multilingual model for email understanding",
    ),
    AIModelDefinition(
        id="openai/gpt-4o-mini",
        name="GPT-4o Mini",
        provider=AIProviderName.OPENROUTER,
        description="OpenAI model via OpenRouter (future direct support)",
    ),
    AIModelDefinition(
        id="anthropic/claude-3.5-sonnet",
        name="Claude 3.5 Sonnet",
        provider=AIProviderName.OPENROUTER,
        description="Anthropic model via OpenRouter (future direct support)",
    ),
]


def get_default_model_id() -> str:
    for model in DEFAULT_MODELS:
        if model.is_default:
            return model.id
    return DEFAULT_MODELS[0].id


def get_model_by_id(model_id: str) -> AIModelDefinition | None:
    return next((model for model in DEFAULT_MODELS if model.id == model_id), None)


def list_available_models() -> list[AIModelDefinition]:
    return list(DEFAULT_MODELS)

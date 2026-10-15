from dataclasses import dataclass
from enum import Enum


class AIProviderName(str, Enum):
    GROQ = "groq"
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
        id="openai/gpt-oss-20b",
        name="GPT-OSS 20B (Groq)",
        provider=AIProviderName.GROQ,
        description="Fast Groq model — default for inbox assistant",
        is_default=True,
    ),
    AIModelDefinition(
        id="openai/gpt-oss-120b",
        name="GPT-OSS 120B (Groq)",
        provider=AIProviderName.GROQ,
        description="Higher-quality Groq model",
    ),
    AIModelDefinition(
        id="deepseek/deepseek-chat",
        name="DeepSeek Chat",
        provider=AIProviderName.OPENROUTER,
        description="Fast, cost-effective general purpose model via OpenRouter",
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
        description="OpenAI model via OpenRouter",
    ),
    AIModelDefinition(
        id="anthropic/claude-3.5-sonnet",
        name="Claude 3.5 Sonnet",
        provider=AIProviderName.OPENROUTER,
        description="Anthropic model via OpenRouter",
    ),
]


def get_default_model_id() -> str:
    for model in DEFAULT_MODELS:
        if model.is_default:
            return model.id
    return DEFAULT_MODELS[0].id


# Models Groq has decommissioned, mapped to their closest current replacement.
RETIRED_MODEL_REPLACEMENTS: dict[str, str] = {
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
}


def resolve_model_id(model_id: str) -> str:
    return RETIRED_MODEL_REPLACEMENTS.get(model_id, model_id)


def get_model_by_id(model_id: str) -> AIModelDefinition | None:
    model_id = resolve_model_id(model_id)
    return next((model for model in DEFAULT_MODELS if model.id == model_id), None)


def list_available_models() -> list[AIModelDefinition]:
    return list(DEFAULT_MODELS)

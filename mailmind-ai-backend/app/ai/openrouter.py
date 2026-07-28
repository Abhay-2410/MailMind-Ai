import asyncio
import logging
from typing import Any

import httpx

from app.ai.provider import AICompletionResult, AIProvider
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Transient upstream statuses worth retrying with backoff.
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
BASE_BACKOFF_SECONDS = 1.5


class OpenRouterProvider(AIProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def provider_name(self) -> str:
        return "openrouter"

    def _ensure_configured(self) -> None:
        if not self.settings.OPENROUTER_API_KEY:
            raise AppError("OpenRouter API key is not configured", status_code=503)

    async def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> AICompletionResult:
        payload = self._build_payload(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=False,
        )
        data = await self._post(payload)
        return self._parse_response(data, model)

    async def complete_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> AICompletionResult:
        payload = self._build_payload(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        data = await self._post(payload)
        return self._parse_response(data, model)

    def _build_payload(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_configured()
        headers = {
            "Authorization": f"Bearer {self.settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.FRONTEND_URL,
            "X-Title": self.settings.APP_NAME,
        }

        last_error = "AI provider request failed"

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        OPENROUTER_API_URL, headers=headers, json=payload
                    )
            except httpx.RequestError as exc:
                last_error = "Could not reach the AI provider"
                logger.warning("OpenRouter network error (attempt %s): %s", attempt, exc)
                if attempt < MAX_ATTEMPTS:
                    await asyncio.sleep(BASE_BACKOFF_SECONDS * attempt)
                    continue
                raise AppError(last_error, status_code=503) from exc

            if response.status_code == 200:
                return response.json()

            last_error = self._extract_error_message(response)

            if response.status_code in RETRYABLE_STATUS and attempt < MAX_ATTEMPTS:
                delay = self._retry_delay(response, attempt)
                logger.warning(
                    "OpenRouter %s (attempt %s/%s): %s — retrying in %.1fs",
                    response.status_code,
                    attempt,
                    MAX_ATTEMPTS,
                    last_error,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            status = 429 if response.status_code == 429 else 502
            raise AppError(last_error, status_code=status)

        raise AppError(last_error, status_code=502)

    @staticmethod
    def _sanitize_provider_message(message: str) -> str:
        lowered = message.lower()
        if "credit" in lowered or "afford" in lowered or "max_tokens" in lowered:
            return (
                "AI credits are too low for this request. "
                "Add credits at openrouter.ai or choose a cheaper model in Settings."
            )
        if "rate" in lowered and "limit" in lowered:
            return "The AI model is rate-limited right now. Please try again in a moment."
        if len(message) > 240:
            return "The AI provider could not complete this request. Please try again."
        return message

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            body = response.json()
            error = body.get("error", {})
            if isinstance(error, dict):
                message = error.get("message")
                metadata = error.get("metadata", {})
                raw = metadata.get("raw") if isinstance(metadata, dict) else None
                if raw:
                    return OpenRouterProvider._sanitize_provider_message(str(raw))
                if message:
                    return OpenRouterProvider._sanitize_provider_message(str(message))
        except (ValueError, AttributeError):
            pass
        if response.status_code == 429:
            return "The AI model is rate-limited right now. Please try again in a moment."
        return f"AI provider request failed ({response.status_code})"

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return min(float(retry_after), 10.0)
            except ValueError:
                pass
        return BASE_BACKOFF_SECONDS * attempt

    def _parse_response(self, data: dict[str, Any], model: str) -> AICompletionResult:
        try:
            choice = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
        except (KeyError, IndexError, TypeError) as exc:
            raise AppError("Invalid AI provider response", status_code=502) from exc

        return AICompletionResult(
            content=choice.strip(),
            model=model,
            provider=self.provider_name,
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
            total_tokens=int(usage.get("total_tokens", 0)),
        )


def get_provider(provider_name: str, settings: Settings | None = None) -> AIProvider:
    settings = settings or get_settings()
    if provider_name == "openrouter":
        return OpenRouterProvider(settings)
    if provider_name == "groq":
        from app.ai.groq import GroqProvider

        return GroqProvider(settings)
    raise AppError(f"Unsupported AI provider: {provider_name}", status_code=400)

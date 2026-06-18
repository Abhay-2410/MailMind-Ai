import json
import re
from typing import Any


def parse_ai_json(content: str) -> dict[str, Any]:
    """Parse JSON from an AI response, tolerating markdown fences and extra prose."""
    text = content.strip()
    if not text:
        raise ValueError("empty AI response")

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidate = text[start : end + 1]
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("no JSON object found in AI response")


def coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        lines = [line.strip(" -•\t") for line in value.split("\n") if line.strip()]
        return lines if lines else ([value.strip()] if value.strip() else [])
    return [str(value).strip()] if str(value).strip() else []


def normalize_summary_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    summary_text = str(
        parsed.get("summary_text") or parsed.get("summary") or parsed.get("overview") or ""
    ).strip()
    key_points = coerce_str_list(parsed.get("key_points"))
    action_items = coerce_str_list(parsed.get("action_items"))
    important_dates = coerce_str_list(parsed.get("important_dates"))

    if not summary_text and key_points:
        summary_text = ". ".join(key_points[:3])

    return {
        "summary_text": summary_text or "No summary available.",
        "key_points": key_points,
        "action_items": action_items,
        "important_dates": important_dates,
        "priority_level": str(parsed.get("priority_level", "medium")).lower(),
    }

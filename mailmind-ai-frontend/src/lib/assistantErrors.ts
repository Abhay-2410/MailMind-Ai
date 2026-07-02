import { ApiError } from "@/lib/api";

export const MIN_ASSISTANT_QUESTION_LENGTH = 3;

export function mapAssistantError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422) {
      return "Please enter at least 3 characters.";
    }
    if (error.status === 429) {
      return "AI is busy — wait a moment and try again.";
    }
    if (error.status === 503) {
      return "AI service is unavailable. Check your OpenRouter API key in Settings.";
    }
    const lowered = error.message.toLowerCase();
    if (
      lowered.includes("credit") ||
      lowered.includes("afford") ||
      lowered.includes("max_tokens") ||
      lowered.includes("openrouter.ai")
    ) {
      return "AI credits are too low. Add credits at openrouter.ai or pick a cheaper model in Settings.";
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

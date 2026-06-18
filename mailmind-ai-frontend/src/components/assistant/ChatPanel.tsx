import { Loader2, Send, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ChatMessage } from "@/components/assistant/ChatMessage";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAskAssistant } from "@/hooks/useAssistant";
import { cn } from "@/lib/utils";
import { useAssistantStore } from "@/stores/assistantStore";
import { ASSISTANT_SUGGESTIONS } from "@/types/ai";

function createMessageId(): string {
  return crypto.randomUUID();
}

export function ChatPanel() {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { messages, addMessage, clearMessages } = useAssistantStore();
  const askMutation = useAskAssistant();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, askMutation.isPending]);

  async function submitQuestion(question: string) {
    const trimmed = question.trim();
    if (!trimmed || askMutation.isPending) return;

    addMessage({
      id: createMessageId(),
      role: "user",
      content: trimmed,
      created_at: new Date().toISOString(),
    });
    setInput("");

    try {
      const response = await askMutation.mutateAsync(trimmed);
      addMessage({
        id: createMessageId(),
        role: "assistant",
        content: response.answer,
        model_used: response.model_used,
        created_at: new Date().toISOString(),
      });
    } catch (error) {
      addMessage({
        id: createMessageId(),
        role: "assistant",
        content: error instanceof Error ? error.message : "Something went wrong. Please try again.",
        created_at: new Date().toISOString(),
        is_error: true,
      });
    }
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    void submitQuestion(input);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitQuestion(input);
    }
  }

  return (
    <Card className="surface-card flex min-h-[560px] flex-col overflow-hidden">
      <CardHeader className="border-b border-border pb-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Sparkles className="h-5 w-5 text-brand-green" />
              Inbox Assistant
            </CardTitle>
            <CardDescription>
              Ask questions about your synced emails — summaries, priorities, and follow-ups.
            </CardDescription>
          </div>
          {messages.length > 0 ? (
            <Button type="button" variant="ghost" size="sm" onClick={clearMessages}>
              <Trash2 className="mr-2 h-4 w-4" />
              Clear
            </Button>
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col p-0">
        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-5 sm:px-6">
          {messages.length === 0 ? (
            <div className="flex h-full min-h-[280px] flex-col items-center justify-center text-center">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-green-soft">
                <Sparkles className="h-6 w-6 text-brand-green" />
              </div>
              <h3 className="text-lg font-semibold text-brand-text">Ask your inbox anything</h3>
              <p className="mt-2 max-w-md text-sm text-brand-muted">
                The assistant uses your 20 most recent synced emails as context.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {ASSISTANT_SUGGESTIONS.map((suggestion) => (
                  <Button
                    key={suggestion}
                    type="button"
                    variant="outline"
                    size="sm"
                    className="rounded-full bg-white"
                    onClick={() => void submitQuestion(suggestion)}
                    disabled={askMutation.isPending}
                  >
                    {suggestion}
                  </Button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}
              {askMutation.isPending ? (
                <div className="flex items-center gap-2 text-sm text-brand-muted">
                  <Loader2 className="h-4 w-4 animate-spin text-brand-green" />
                  Thinking…
                </div>
              ) : null}
            </>
          )}
          <div ref={bottomRef} />
        </div>

        <form
          onSubmit={handleSubmit}
          className="border-t border-border bg-white/80 p-4 backdrop-blur sm:px-6"
        >
          <div className="flex gap-3">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your inbox…"
              rows={2}
              disabled={askMutation.isPending}
              className={cn(
                "min-h-[44px] flex-1 resize-none rounded-xl border border-input bg-white px-3 py-2 text-sm shadow-sm",
                "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                "disabled:cursor-not-allowed disabled:opacity-50",
              )}
            />
            <Button type="submit" disabled={!input.trim() || askMutation.isPending} className="self-end">
              {askMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
          <p className="mt-2 text-xs text-brand-muted">Press Enter to send, Shift+Enter for a new line.</p>
        </form>
      </CardContent>
    </Card>
  );
}

import { Bot, User } from "lucide-react";
import { motion } from "framer-motion";

import { cn } from "@/lib/utils";
import type { ChatMessage as ChatMessageType } from "@/types/ai";

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}
    >
      <div
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
          isUser ? "bg-brand-green text-primary-foreground" : "bg-brand-green-soft text-brand-green",
          message.is_error && "bg-destructive/15 text-destructive",
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      <div className={cn("max-w-[85%] space-y-1", isUser ? "items-end text-right" : "items-start")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm",
            isUser
              ? "rounded-tr-md bg-brand-gradient text-primary-foreground"
              : message.is_error
                ? "rounded-tl-md border border-destructive/30 bg-destructive/10 text-destructive"
                : "rounded-tl-md border border-border bg-card text-foreground",
          )}
        >
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
        {!isUser && message.model_used && !message.is_error ? (
          <p className="text-xs text-brand-muted">via {message.model_used}</p>
        ) : null}
      </div>
    </motion.div>
  );
}

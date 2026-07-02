import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

interface AnimatedSuggestionProps {
  suggestions: readonly string[];
  intervalMs?: number;
}

export function AnimatedSuggestion({ suggestions, intervalMs = 3500 }: AnimatedSuggestionProps) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (suggestions.length <= 1) return;
    const timer = window.setInterval(() => {
      setIndex((i) => (i + 1) % suggestions.length);
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs, suggestions.length]);

  return (
    <div className="relative h-5 overflow-hidden">
      <AnimatePresence mode="wait">
        <motion.p
          key={suggestions[index]}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.35 }}
          className="text-sm font-medium text-brand-muted"
        >
          Try: &ldquo;{suggestions[index]}&rdquo;
        </motion.p>
      </AnimatePresence>
    </div>
  );
}

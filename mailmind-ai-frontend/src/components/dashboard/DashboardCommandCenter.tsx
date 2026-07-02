import { ArrowUp, Sparkles } from "lucide-react";

import { AnimatedSuggestion, GlassSurface } from "@/components/design-system";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCommandCenter } from "@/hooks/useCommandCenter";

export function DashboardCommandCenter() {
  const { query, setQuery, submit, suggestions } = useCommandCenter();

  return (
    <GlassSurface className="relative p-6 sm:p-8">
      <div className="pointer-events-none absolute -right-20 -top-20 h-56 w-56 rounded-full bg-indigo-400/20 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-16 -left-16 h-48 w-48 rounded-full bg-blue-400/15 blur-3xl" />
      <div className="relative space-y-5">
        <div className="flex items-center gap-3">
          <div className="brand-icon-surface flex h-10 w-10 items-center justify-center rounded-xl">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <p className="text-sm font-bold text-foreground">MailMind Command Center</p>
            <p className="text-xs font-medium text-muted-foreground">Ask anything about your inbox</p>
          </div>
        </div>

        <form
          className="flex flex-col gap-3 sm:flex-row sm:items-center"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask MailMind anything..."
            className="h-12 flex-1 rounded-2xl px-5 text-base font-medium"
          />
          <Button type="submit" size="lg" className="h-12 rounded-2xl px-6">
            <ArrowUp className="mr-2 h-4 w-4" />
            Ask
          </Button>
        </form>

        <AnimatedSuggestion suggestions={suggestions} />
      </div>
    </GlassSurface>
  );
}

import { Bot, Loader2, Save } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAIModels, useUpdateSettings } from "@/hooks/useSettings";
import type { SettingsResponse } from "@/types/settings";

interface AIModelSettingsProps {
  settings: SettingsResponse;
}

export function AIModelSettings({ settings }: AIModelSettingsProps) {
  const { data: models, isLoading } = useAIModels();
  const updateMutation = useUpdateSettings();
  const [selectedModel, setSelectedModel] = useState(settings.ai_model);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setSelectedModel(settings.ai_model);
  }, [settings.ai_model]);

  const selected = models?.find((model) => model.id === selectedModel);

  async function handleSave() {
    const model = models?.find((item) => item.id === selectedModel);
    if (!model) return;

    await updateMutation.mutateAsync({
      ai_model: model.id,
      ai_provider: model.provider,
    });
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2000);
  }

  return (
    <Card className="surface-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Bot className="h-5 w-5 text-brand-green" />
          AI model
        </CardTitle>
        <CardDescription>
          Choose the model used for summaries, replies, search, and assistant. OpenRouter models
          require OPENROUTER_API_KEY on the API; Groq models require GROQ_API_KEY.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <Skeleton className="h-10 w-full" />
        ) : (
          <label className="block space-y-2">
            <span className="text-sm font-medium text-brand-text">Default model</span>
            <select
              value={selectedModel}
              onChange={(event) => setSelectedModel(event.target.value)}
              className="select-surface h-10 w-full rounded-xl px-3 text-sm"
            >
              {(models ?? []).map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                  {model.is_default ? " (Default)" : ""}
                </option>
              ))}
            </select>
          </label>
        )}

        {selected ? (
          <div className="rounded-xl border border-border bg-accent/40 p-4">
            <p className="font-medium text-brand-text">{selected.name}</p>
            <p className="mt-1 text-sm text-brand-muted">{selected.description}</p>
            <p className="mt-2 text-xs text-brand-muted">
              Provider: {selected.provider} · ID: {selected.id}
            </p>
          </div>
        ) : null}

        <div className="flex items-center gap-3">
          <Button onClick={() => void handleSave()} disabled={updateMutation.isPending || isLoading}>
            {updateMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving…
              </>
            ) : (
              <>
                <Save className="mr-2 h-4 w-4" />
                Save model
              </>
            )}
          </Button>
          {saved ? <span className="text-sm text-brand-green">Saved</span> : null}
        </div>
      </CardContent>
    </Card>
  );
}

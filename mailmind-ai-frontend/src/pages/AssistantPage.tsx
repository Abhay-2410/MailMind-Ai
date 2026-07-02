import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";

import { ChatPanel } from "@/components/assistant/ChatPanel";

export function AssistantPage() {
  const [params, setParams] = useSearchParams();
  const initialQuery = params.get("q") ?? undefined;

  useEffect(() => {
    if (params.has("mode")) {
      setParams({}, { replace: true });
    }
  }, [params, setParams]);

  return (
    <div className="mx-auto max-w-4xl">
      <ChatPanel initialMessage={initialQuery} />
    </div>
  );
}

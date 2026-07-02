import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

import { COMMAND_SUGGESTIONS } from "@/lib/dashboard/commandSuggestions";
import { ROUTES } from "@/lib/constants";

export function useCommandCenter() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  const submit = useCallback(
    (value?: string) => {
      const text = (value ?? query).trim();
      if (!text) return;
      navigate(`${ROUTES.ASSISTANT}?q=${encodeURIComponent(text)}`);
    },
    [navigate, query],
  );

  return {
    query,
    setQuery,
    submit,
    suggestions: COMMAND_SUGGESTIONS,
  };
}

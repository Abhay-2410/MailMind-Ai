import { useSearchParams } from "react-router-dom";

import { INBOX_VIEW_META, resolveInboxView, type InboxPageView } from "@/lib/inboxViews";

export function useInboxView(): {
  view: InboxPageView;
  meta: (typeof INBOX_VIEW_META)[InboxPageView];
} {
  const [searchParams] = useSearchParams();
  const view = resolveInboxView(searchParams.get("view"));
  return { view, meta: INBOX_VIEW_META[view] };
}

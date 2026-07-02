export type InboxPageView = "inbox" | "summaries";

export function resolveInboxView(viewParam: string | null): InboxPageView {
  if (viewParam === "summaries") return "summaries";
  return "inbox";
}

export const INBOX_VIEW_META: Record<
  InboxPageView,
  { title: string; description: string; eyebrow: string }
> = {
  inbox: {
    eyebrow: "Mail",
    title: "Inbox",
    description: "All your emails in one place",
  },
  summaries: {
    eyebrow: "AI digest",
    title: "Summaries",
    description: "AI-generated overviews of your synced emails",
  },
};

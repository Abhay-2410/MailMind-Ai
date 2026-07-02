import { Outlet, useLocation, useSearchParams } from "react-router-dom";

import { Header } from "@/components/layout/Header";
import { MobileNav } from "@/components/layout/MobileNav";
import { PageContainer } from "@/components/layout/PageContainer";
import { Sidebar } from "@/components/layout/Sidebar";
import { useAutoSync } from "@/hooks/useAutoSync";
import { APP_NAME, ROUTE_META, ROUTES } from "@/lib/constants";
import { INBOX_VIEW_META, resolveInboxView } from "@/lib/inboxViews";

function resolveRouteMeta(pathname: string) {
  if (pathname.startsWith(`${ROUTES.EMAIL}/`)) {
    return ROUTE_META[ROUTES.EMAIL];
  }
  return ROUTE_META[pathname];
}

export function AppLayout() {
  const { pathname } = useLocation();
  const [searchParams] = useSearchParams();
  const meta = resolveRouteMeta(pathname);
  const { isSyncing, syncDetail } = useAutoSync();

  const isInsightsView =
    pathname === ROUTES.DASHBOARD && searchParams.get("section") === "insights";
  const inboxView =
    pathname === ROUTES.INBOX ? resolveInboxView(searchParams.get("view")) : null;
  const inboxMeta = inboxView ? INBOX_VIEW_META[inboxView] : null;

  const headerTitle = isInsightsView
    ? "Category Insights"
    : inboxMeta
      ? inboxMeta.title
      : (meta?.title ?? APP_NAME);
  const headerDescription = isSyncing
    ? syncDetail ?? "Syncing inbox…"
    : isInsightsView
      ? "Analyze inbox distribution and browse emails by category"
      : inboxMeta
        ? inboxMeta.description
        : (meta?.description ?? "");

  return (
    <div className="surface-page flex min-h-screen">
      <Sidebar />
      <div className="flex min-h-screen flex-1 flex-col pb-20 lg:pb-0">
        <Header title={headerTitle} description={headerDescription} />
        <main className="flex-1 px-4 py-6 sm:px-8 sm:py-10">
          <PageContainer size={pathname === ROUTES.DASHBOARD ? "wide" : "default"}>
            <Outlet />
          </PageContainer>
        </main>
      </div>
      <MobileNav />
    </div>
  );
}

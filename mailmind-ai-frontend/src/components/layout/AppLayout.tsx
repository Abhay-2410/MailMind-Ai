import { Outlet, useLocation } from "react-router-dom";

import { Header } from "@/components/layout/Header";
import { MobileNav } from "@/components/layout/MobileNav";
import { PageContainer } from "@/components/layout/PageContainer";
import { Sidebar } from "@/components/layout/Sidebar";
import { useAutoSync } from "@/hooks/useAutoSync";
import { APP_NAME, ROUTE_META, ROUTES } from "@/lib/constants";

function resolveRouteMeta(pathname: string) {
  if (pathname.startsWith(`${ROUTES.EMAIL}/`)) {
    return ROUTE_META[ROUTES.EMAIL];
  }
  return ROUTE_META[pathname];
}

export function AppLayout() {
  const { pathname } = useLocation();
  const meta = resolveRouteMeta(pathname);
  const { isSyncing } = useAutoSync();

  return (
    <div className="surface-page flex min-h-screen">
      <Sidebar />
      <div className="flex min-h-screen flex-1 flex-col pb-20 lg:pb-0">
        <Header
          title={meta?.title ?? APP_NAME}
          description={isSyncing ? "Syncing Gmail…" : (meta?.description ?? "")}
        />
        <main className="flex-1 px-4 py-6 sm:px-8 sm:py-8">
          <PageContainer>
            <Outlet />
          </PageContainer>
        </main>
      </div>
      <MobileNav />
    </div>
  );
}

import { ArrowLeft, Mail } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { AISummaryPanel } from "@/components/email/AISummaryPanel";
import { EmailReader } from "@/components/email/EmailReader";
import { ReplyGenerator } from "@/components/email/ReplyGenerator";
import { EmptyState } from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useEmail } from "@/hooks/useEmails";
import { ApiError } from "@/lib/api";
import { ROUTES } from "@/lib/constants";

export function EmailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: email, isLoading, isError, error, refetch } = useEmail(id);

  if (!id) {
    return (
      <EmptyState
        icon={Mail}
        title="Email not found"
        description="The email link is invalid."
        action={
          <Button asChild variant="outline">
            <Link to={ROUTES.INBOX}>Back to inbox</Link>
          </Button>
        }
      />
    );
  }

  if (isLoading) {
    return <EmailPageSkeleton />;
  }

  if (isError || !email) {
    const isGmailAuth =
      error instanceof ApiError &&
      (error.status === 401 || /session expired|sign in|gmail/i.test(error.message));
    return (
      <EmptyState
        icon={Mail}
        title="Unable to load email"
        className="min-h-[420px] w-full"
        description={
          isGmailAuth
            ? "Your Gmail connection expired. Sign out and sign in with Google again, then return to this email."
            : error instanceof Error
              ? error.message
              : "This email may have been removed or you may not have access."
        }
        action={
          <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:justify-center">
            <Button variant="outline" className="w-full sm:w-auto" onClick={() => void refetch()}>
              Try again
            </Button>
            <Button asChild className="w-full sm:w-auto">
              <Link to={ROUTES.INBOX}>Back to inbox</Link>
            </Button>
          </div>
        }
      />
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      <Button
        asChild
        variant="ghost"
        size="sm"
        className="-ml-2 w-fit text-brand-muted hover:text-brand-text"
      >
        <Link to={ROUTES.INBOX}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to inbox
        </Link>
      </Button>

      <div className="grid gap-4 sm:gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <EmailReader email={email} />
        <div className="space-y-6">
          <AISummaryPanel emailId={email.id} />
          <ReplyGenerator emailId={email.id} />
        </div>
      </div>
    </div>
  );
}

function EmailPageSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-9 w-32" />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Skeleton className="h-[480px] rounded-2xl" />
        <div className="space-y-6">
          <Skeleton className="h-64 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      </div>
    </div>
  );
}

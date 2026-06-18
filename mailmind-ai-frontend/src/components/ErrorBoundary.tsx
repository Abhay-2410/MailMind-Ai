import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("MailMind UI error:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-brand-bg p-6">
          <div className="max-w-md rounded-2xl border bg-white p-8 shadow-card">
            <h1 className="text-xl font-semibold text-brand-text">Something went wrong</h1>
            <p className="mt-2 text-sm text-brand-muted">{this.state.error.message}</p>
            <Button className="mt-6" onClick={() => window.location.assign("/login")}>
              Back to login
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

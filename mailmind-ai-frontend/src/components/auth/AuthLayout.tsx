import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { motion } from "framer-motion";

import { APP_NAME } from "@/lib/constants";

interface AuthLayoutProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
}

export function AuthLayout({
  children,
  title = APP_NAME,
  subtitle = "Your AI-powered Gmail copilot",
}: AuthLayoutProps) {
  return (
    <div className="surface-page flex min-h-screen items-center justify-center px-4 py-12">
      <motion.div
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
        className="w-full max-w-md"
      >
        <div className="surface-glass rounded-3xl p-8 sm:p-10">
          <div className="mb-8 text-center">
            <Link to="/" className="mb-6 inline-flex items-center justify-center gap-2">
              <div className="brand-icon-surface flex h-11 w-11 items-center justify-center rounded-2xl">
                <Sparkles className="h-5 w-5 text-brand-green" />
              </div>
            </Link>
            <h1 className="text-display-xs text-balance text-brand-text">{title}</h1>
            <p className="mt-2 text-body">{subtitle}</p>
          </div>
          {children}
        </div>
      </motion.div>
    </div>
  );
}

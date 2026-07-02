import { motion } from "framer-motion";

import { cn } from "@/lib/utils";
import { cardHover } from "@/lib/motion";

interface PremiumCardProps {
  children: React.ReactNode;
  className?: string;
  interactive?: boolean;
}

export function PremiumCard({ children, className, interactive = true }: PremiumCardProps) {
  const Component = interactive ? motion.div : "div";
  const motionProps = interactive
    ? {
        variants: cardHover,
        initial: "rest",
        whileHover: "hover",
        transition: { duration: 0.25, ease: [0.25, 0.1, 0.25, 1] },
      }
    : {};

  return (
    <Component
      {...motionProps}
      className={cn(
        "surface-card p-6",
        interactive && "transition-all duration-300",
        className,
      )}
    >
      {children}
    </Component>
  );
}

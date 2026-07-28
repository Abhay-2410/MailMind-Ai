import { cn } from "@/lib/utils";

interface MetricPillProps {
  label: string;
  value: string | number;
  className?: string;
}

export function MetricPill({ label, value, className }: MetricPillProps) {
  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-md border border-border bg-secondary/80 px-3 py-1.5",
        className,
      )}
    >
      <span className="text-lg font-bold tabular-nums text-primary">{value}</span>
      <span className="text-xs font-medium text-brand-muted">{label}</span>
    </div>
  );
}

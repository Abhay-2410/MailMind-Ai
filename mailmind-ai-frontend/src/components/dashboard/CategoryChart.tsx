import { motion } from "framer-motion";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CategoryStat } from "@/types/dashboard";

const CATEGORY_COLORS: Record<string, string> = {
  important: "bg-brand-green",
  work: "bg-brand-green-light",
  personal: "bg-emerald-400",
  finance: "bg-teal-500",
  promotions: "bg-slate-400",
  social: "bg-violet-400",
  updates: "bg-amber-400",
};

interface CategoryChartProps {
  categories: CategoryStat[];
}

export function CategoryChart({ categories }: CategoryChartProps) {
  const withData = categories.filter((c) => c.count > 0);
  const maxCount = Math.max(...withData.map((c) => c.count), 1);

  return (
    <Card className="surface-card h-full">
      <CardHeader>
        <CardTitle className="text-lg">Category Analytics</CardTitle>
        <CardDescription>How your emails are classified by AI</CardDescription>
      </CardHeader>
      <CardContent>
        {withData.length === 0 ? (
          <p className="py-8 text-center text-body">
            No categorized emails yet. Sync your inbox and run AI categorization.
          </p>
        ) : (
          <div className="space-y-4">
            {withData.map((item, index) => (
              <motion.div
                key={item.category}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <div className="mb-1.5 flex items-center justify-between text-sm">
                  <span className="font-medium text-brand-text">{item.label}</span>
                  <span className="text-brand-muted">
                    {item.count} · {item.percentage}%
                  </span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${CATEGORY_COLORS[item.category] ?? "bg-brand-green"}`}
                    style={{ width: `${(item.count / maxCount) * 100}%` }}
                  />
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

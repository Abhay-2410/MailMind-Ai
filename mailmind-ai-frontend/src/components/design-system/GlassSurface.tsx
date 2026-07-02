import { cn } from "@/lib/utils";

interface GlassSurfaceProps {
  children: React.ReactNode;
  className?: string;
  as?: "div" | "section";
}

export function GlassSurface({ children, className, as: Tag = "div" }: GlassSurfaceProps) {
  return (
    <Tag className={cn("surface-feature", className)}>
      {children}
    </Tag>
  );
}

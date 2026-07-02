interface SectionHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  align?: "left" | "center";
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  align = "left",
}: SectionHeaderProps) {
  return (
    <div className={align === "center" ? "text-center" : "text-left"}>
      {eyebrow ? <p className="eyebrow-pill">{eyebrow}</p> : null}
      <h1 className="text-balance text-3xl font-bold tracking-tight sm:text-4xl lg:text-[2.75rem] lg:leading-tight">
        <span className="text-gradient">{title}</span>
      </h1>
      {description ? (
        <p className="mt-4 max-w-2xl text-base font-medium leading-relaxed text-muted-foreground">
          {description}
        </p>
      ) : null}
    </div>
  );
}

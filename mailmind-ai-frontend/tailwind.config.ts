import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "system-ui", "sans-serif"],
      },
      fontSize: {
        "display-sm": ["2.25rem", { lineHeight: "2.5rem", letterSpacing: "-0.02em", fontWeight: "700" }],
        "display-xs": ["1.875rem", { lineHeight: "2.25rem", letterSpacing: "-0.02em", fontWeight: "700" }],
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        brand: {
          cream: "hsl(var(--brand-cream))",
          lime: "hsl(var(--brand-lime))",
          green: "hsl(var(--brand-green))",
          "green-light": "hsl(var(--brand-green-light))",
          "green-soft": "hsl(var(--brand-green-soft))",
          bg: "hsl(var(--brand-bg))",
          text: "hsl(var(--brand-text))",
          muted: "hsl(var(--brand-muted))",
        },
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #3b82f6 0%, #4f46e5 48%, #312e81 100%)",
        "brand-gradient-soft":
          "linear-gradient(135deg, #eef2ff 0%, #e0e7ff 38%, #dbeafe 72%, #c7d2fe 100%)",
        "brand-gradient-vertical": "linear-gradient(180deg, #3b82f6 0%, #312e81 100%)",
        "mesh-light":
          "radial-gradient(ellipse 80% 60% at 0% 0%, rgba(59,130,246,0.14), transparent 55%), radial-gradient(ellipse 60% 50% at 100% 0%, rgba(99,102,241,0.1), transparent 50%)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        xl: "calc(var(--radius) + 4px)",
        "2xl": "calc(var(--radius) + 8px)",
        "3xl": "1.5rem",
      },
      boxShadow: {
        soft: "0 4px 24px -4px rgba(59, 130, 246, 0.28)",
        card: "0 1px 2px rgba(15, 23, 42, 0.04), 0 4px 20px rgba(59, 130, 246, 0.06)",
        elevated: "0 12px 40px -8px rgba(49, 46, 129, 0.15)",
        glow: "0 0 0 1px rgba(99, 102, 241, 0.15), 0 8px 32px rgba(59, 130, 246, 0.22)",
        "dark-card": "0 0 0 1px rgba(255, 255, 255, 0.05), 0 12px 40px rgba(0, 0, 0, 0.5)",
        "dark-glow": "0 0 0 1px rgba(99, 102, 241, 0.25), 0 12px 36px rgba(59, 130, 246, 0.2)",
      },
      spacing: {
        18: "4.5rem",
        22: "5.5rem",
      },
      maxWidth: {
        content: "72rem",
      },
      transitionDuration: {
        250: "250ms",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(12px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.35s ease-out",
        shimmer: "shimmer 1.5s infinite",
      },
    },
  },
  plugins: [animate],
};

export default config;

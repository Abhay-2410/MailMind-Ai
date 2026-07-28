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
        "brand-gradient": "linear-gradient(135deg, #1e2928 0%, #2a3836 52%, #15201f 100%)",
        "brand-gradient-soft":
          "linear-gradient(135deg, #ebe7d6 0%, #e2decb 42%, #d9d4be 100%)",
        "brand-gradient-vertical": "linear-gradient(180deg, #1e2928 0%, #15201f 100%)",
        "mesh-light":
          "linear-gradient(rgba(30,41,40,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(30,41,40,0.05) 1px, transparent 1px)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
        xl: "calc(var(--radius) + 4px)",
        "2xl": "calc(var(--radius) + 8px)",
        "3xl": "1.25rem",
      },
      boxShadow: {
        soft: "0 4px 20px -4px rgba(30, 41, 40, 0.22)",
        card: "0 1px 2px rgba(30, 41, 40, 0.04), 0 4px 18px rgba(30, 41, 40, 0.06)",
        elevated: "0 12px 36px -8px rgba(30, 41, 40, 0.14)",
        glow: "0 0 0 1px rgba(30, 41, 40, 0.08), 0 8px 28px rgba(30, 41, 40, 0.12)",
        "dark-card": "0 0 0 1px rgba(255, 255, 255, 0.05), 0 12px 40px rgba(0, 0, 0, 0.5)",
        "dark-glow": "0 0 0 1px rgba(230, 226, 207, 0.1), 0 12px 36px rgba(0, 0, 0, 0.35)",
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

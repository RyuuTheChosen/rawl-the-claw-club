import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Legacy rawl colors (backward compat)
        rawl: {
          primary: "#FF4500",
          secondary: "#1A1A2E",
          accent: "#E94560",
          dark: "#0F0F23",
          light: "#F5F5F5",
        },
        // Neon arcade palette
        neon: {
          orange: "#FF4500",
          pink: "#FF2D78",
          cyan: "#00FFFF",
          green: "#39FF14",
          yellow: "#FFD700",
          purple: "#BF40BF",
          blue: "#4169E1",
          red: "#FF003C",
        },
        // shadcn CSS variable colors
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
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
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        chart: {
          "1": "hsl(var(--chart-1))",
          "2": "hsl(var(--chart-2))",
          "3": "hsl(var(--chart-3))",
          "4": "hsl(var(--chart-4))",
          "5": "hsl(var(--chart-5))",
        },
      },
      fontFamily: {
        pixel: ["var(--font-pixel)", "monospace"],
        body: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "Menlo", "monospace"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "pulse-glow": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.6" },
        },
        scanline: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        flicker: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.97" },
          "25%": { opacity: "0.99" },
          "75%": { opacity: "0.98" },
        },
        "health-drain": {
          "0%": { transform: "scaleX(1)" },
          "100%": { transform: "scaleX(var(--health-scale, 1))" },
        },
        "slide-up": {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "vs-slam": {
          "0%": { opacity: "0", transform: "scale(3)" },
          "60%": { opacity: "1", transform: "scale(0.9)" },
          "80%": { transform: "scale(1.05)" },
          "100%": { transform: "scale(1)" },
        },
        "live-pulse": {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.5", transform: "scale(1.3)" },
        },
      },
      animation: {
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        scanline: "scanline 8s linear infinite",
        flicker: "flicker 0.15s ease-in-out infinite",
        "health-drain": "health-drain 0.3s ease-out forwards",
        "slide-up": "slide-up 0.4s ease-out",
        "vs-slam": "vs-slam 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) forwards",
        "live-pulse": "live-pulse 1.5s ease-in-out infinite",
      },
      boxShadow: {
        "neon-orange": "0 0 10px rgba(255, 69, 0, 0.5), 0 0 30px rgba(255, 69, 0, 0.2)",
        "neon-cyan": "0 0 10px rgba(0, 255, 255, 0.5), 0 0 30px rgba(0, 255, 255, 0.2)",
        "neon-pink": "0 0 10px rgba(255, 45, 120, 0.5), 0 0 30px rgba(255, 45, 120, 0.2)",
        "neon-green": "0 0 10px rgba(57, 255, 20, 0.5), 0 0 30px rgba(57, 255, 20, 0.2)",
        "arcade-card":
          "0 0 0 1px rgba(255, 69, 0, 0.1), 0 4px 20px rgba(0, 0, 0, 0.5)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;

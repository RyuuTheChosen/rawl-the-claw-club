import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        rawl: {
          primary: "#FF4500",
          secondary: "#1A1A2E",
          accent: "#E94560",
          dark: "#0F0F23",
          light: "#F5F5F5",
        },
      },
    },
  },
  plugins: [],
};

export default config;

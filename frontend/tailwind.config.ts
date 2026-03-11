import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: 'class',
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          dark: "rgb(var(--primary-dark) / <alpha-value>)",
          DEFAULT: "rgb(var(--primary) / <alpha-value>)",
          light: "rgb(var(--primary-light) / <alpha-value>)",
          lighter: "rgb(var(--primary-lighter) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "rgb(var(--accent) / <alpha-value>)",
          light: "rgb(var(--accent-light) / <alpha-value>)",
        },
        background: {
          DEFAULT: "#FFFFFF",
          secondary: "#F5F5F5",
        },
        dark: {
          bg: "rgb(var(--dark-bg) / <alpha-value>)",
          surface: "rgb(var(--dark-surface) / <alpha-value>)",
          card: "rgb(var(--dark-card) / <alpha-value>)",
          text: "#ffffff",
          muted: "rgb(var(--dark-muted) / <alpha-value>)",
        }
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
export default config;

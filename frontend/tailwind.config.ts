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
          dark: "#00573D",
          DEFAULT: "#006837",
          light: "#008A47",
          lighter: "#A8E6CF",
        },
        background: {
          DEFAULT: "#FFFFFF",
          secondary: "#F5F5F5",
        },
        dark: {
          bg: "#1a3a2a",
          surface: "#245038",
          card: "#2d6345",
          text: "#ffffff",
          muted: "#b8c4bb",
        }
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
export default config;

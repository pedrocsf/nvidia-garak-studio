export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: {
          base: "#0D0D0D",
          panel: "#1A1A1A",
          elevated: "#242424",
        },
        line: "#2A2A2A",
        nvidia: "#76B900",
        "nvidia-dim": "#5c8f00",
        warn: "#F2B705",
        danger: "#E5484D",
        ink: {
          DEFAULT: "#F5F5F5",
          muted: "#A3A3A3",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        card: "10px",
      },
    },
  },
  plugins: [],
};

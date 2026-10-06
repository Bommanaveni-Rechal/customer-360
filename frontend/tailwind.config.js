/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1a2332",
        mute: "#5d6b7a",
        paper: "#f3efe7",
        card: "#fffdf9",
        line: "#e4dcd0",
        teal: "#0e6b64",
        deep: "#10262c",
        mist: "#e7f3f1",
        amber: "#8d5b12",
        cream: "#fbf6ec",
        rose: "#9d3144",
        blush: "#f8ecee",
        moss: "#1e6b45",
        sage: "#e7f3ec",
      },
      fontFamily: {
        sans: ["Outfit", "Segoe UI", "sans-serif"],
        serif: ["Newsreader", "Georgia", "serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(26, 35, 50, 0.04), 0 16px 40px rgba(26, 35, 50, 0.05)",
      },
    },
  },
  plugins: [],
}

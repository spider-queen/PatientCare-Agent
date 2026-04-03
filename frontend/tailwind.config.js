/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0F172A",
        mist: "#E2E8F0",
        cloud: "#F8FAFC",
        accent: "#0F766E",
        accentSoft: "#CCFBF1",
        panel: "#FFFFFF",
        peach: "#FED7AA"
      },
      boxShadow: {
        panel: "0 24px 60px rgba(15, 23, 42, 0.08)"
      },
      fontFamily: {
        sans: ["'Segoe UI'", "'PingFang SC'", "'Microsoft YaHei'", "sans-serif"]
      }
    }
  },
  plugins: []
};


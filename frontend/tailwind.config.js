import preset from "frappe-ui/src/tailwind/preset"

export default {
  presets: [preset],
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
    "./node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ground: "var(--fs-ground)",
        "ground-home": "var(--fs-ground-home)",
        // frappe-ui's preset already defines `colors.surface` as a nested
        // shade object (surface.white, surface.gray-1, ...) with no DEFAULT,
        // so a plain string here gets swallowed by the deep-merge and no
        // `.bg-surface` utility is ever generated. Giving it a DEFAULT key
        // merges alongside those shades instead of colliding with them.
        surface: { DEFAULT: "var(--fs-surface)" },
        "surface-2": "var(--fs-surface-2)",
        ink: "var(--fs-ink)",
        "ink-2": "var(--fs-ink-2)",
        "ink-3": "var(--fs-ink-3)",
        rule: "var(--fs-rule)",
        "rule-soft": "var(--fs-rule-soft)",
        accent: "var(--fs-accent)",
        "accent-soft": "var(--fs-accent-soft)",
        "accent-fg": "var(--fs-accent-fg)",
        "accent-ink": "var(--fs-accent-ink)",
        crit: "var(--fs-crit)",
        warn: "var(--fs-warn)",
        good: "var(--fs-good)",
        chart: "var(--fs-chart)",
        action2: "var(--fs-action2)",
        "action2-fg": "var(--fs-action2-fg)",
      },
      fontFamily: {
        sans: ["Poppins", "Segoe UI", "system-ui", "sans-serif"],
      },
    },
  },
}

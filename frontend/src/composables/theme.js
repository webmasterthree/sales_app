// The app is dark-only now (an explicit product decision, not a default -
// see Settings.vue, whose Appearance picker was removed along with this).
// applyTheme still exists as the one place that stamps documentElement, so
// nothing else has to know how the "dark" token is actually applied.
export const themeChoice = "dark"

export function applyTheme() {
  document.documentElement.dataset.theme = "dark"
}

export function initTheme() {
  applyTheme()
}

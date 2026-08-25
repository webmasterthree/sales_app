import { ref, watchEffect } from "vue"

const STORAGE_KEY = "field_sales:theme"

export const themeChoice = ref(localStorage.getItem(STORAGE_KEY) || "system")

export function applyTheme(choice) {
  const root = document.documentElement
  if (choice === "light") {
    root.dataset.theme = "light"
  } else if (choice === "dark") {
    root.dataset.theme = "dark"
  } else {
    delete root.dataset.theme
  }
}

export function setTheme(choice) {
  themeChoice.value = choice
  localStorage.setItem(STORAGE_KEY, choice)
  applyTheme(choice)
}

export function initTheme() {
  applyTheme(themeChoice.value)
}

watchEffect(() => applyTheme(themeChoice.value))

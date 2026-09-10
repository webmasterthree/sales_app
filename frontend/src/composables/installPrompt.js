import { computed, ref } from "vue"

// Module-level, not component state: `beforeinstallprompt` fires once,
// early, and only ever reaches a listener that was already registered when
// it happened - so this has to exist independent of whether the user has
// ever opened the Settings screen where the actual "Install" button lives.
// Imported once for its side effect in main.js.
const deferredPrompt = ref(null)
const justInstalled = ref(false)

function isIos() {
  return /iphone|ipad|ipod/.test(window.navigator.userAgent.toLowerCase())
}

function isStandalone() {
  return (
    window.matchMedia?.("(display-mode: standalone)").matches ||
    ("standalone" in window.navigator && window.navigator.standalone)
  )
}

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault()
  deferredPrompt.value = e
})

window.addEventListener("appinstalled", () => {
  deferredPrompt.value = null
  justInstalled.value = true
})

const canInstall = computed(() => !!deferredPrompt.value)
const alreadyInstalled = computed(() => isStandalone() || justInstalled.value)

async function promptInstall() {
  if (!deferredPrompt.value) return null
  deferredPrompt.value.prompt()
  const choice = await deferredPrompt.value.userChoice
  deferredPrompt.value = null
  return choice
}

export function useInstallPrompt() {
  return { isIos: isIos(), canInstall, alreadyInstalled, promptInstall }
}

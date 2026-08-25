<template>
  <!-- Android/desktop: native browser install prompt -->
  <div v-if="showDialog" class="fixed inset-0 z-50 flex items-end justify-center bg-black/40" @click.self="showDialog = false">
    <div class="w-full max-w-md bg-surface rounded-t-2xl p-6 pb-8 shadow-lg">
      <div class="w-10 h-10 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center mb-3">
        <Icon name="smartphone" :size="20" />
      </div>
      <h2 class="font-display font-semibold text-lg text-ink mb-1">Install Field Sales</h2>
      <p class="text-sm text-ink-2 mb-5">
        Add it to your home screen for one-tap access and a faster, app-like experience.
      </p>
      <div class="flex gap-3">
        <button
          type="button"
          class="flex-1 py-3 rounded-[10px] bg-surface-2 text-ink font-display font-medium active:opacity-80"
          @click="dismiss"
        >
          Not now
        </button>
        <button
          type="button"
          class="flex-1 py-3 rounded-[10px] bg-accent text-accent-fg font-display font-medium active:opacity-80"
          @click="install"
        >
          Install
        </button>
      </div>
    </div>
  </div>

  <!-- iOS: Safari has no install prompt event, so show manual instructions -->
  <div
    v-if="iosInstallMessage"
    class="fixed inset-x-3 bottom-3 z-50 rounded-2xl bg-surface border border-rule shadow-lg p-4"
  >
    <div class="flex items-start justify-between gap-3 mb-2">
      <span class="font-display font-semibold text-ink">Install Field Sales</span>
      <button type="button" class="text-ink-3 text-lg leading-none" aria-label="Dismiss" @click="dismissIos">
        ×
      </button>
    </div>
    <p class="text-sm text-ink-2">
      Tap <span class="font-medium text-ink">Share</span> then
      <span class="font-medium text-ink">"Add to Home Screen"</span>.
    </p>
  </div>
</template>

<script setup>
import { ref } from "vue"
import Icon from "@/components/Icon.vue"

const STORAGE_KEY = "fs:install-dismissed"

const deferredPrompt = ref(null)
const showDialog = ref(false)
const iosInstallMessage = ref(false)

function isIos() {
  return /iphone|ipad|ipod/.test(window.navigator.userAgent.toLowerCase())
}

function isStandalone() {
  return (
    window.matchMedia?.("(display-mode: standalone)").matches ||
    ("standalone" in window.navigator && window.navigator.standalone)
  )
}

function alreadyDismissed() {
  return localStorage.getItem(STORAGE_KEY) === "1"
}

if (isIos() && !isStandalone() && !alreadyDismissed()) {
  iosInstallMessage.value = true
}

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault()
  deferredPrompt.value = e
  if (!alreadyDismissed() && !isStandalone()) {
    showDialog.value = true
  }
})

window.addEventListener("appinstalled", () => {
  showDialog.value = false
  deferredPrompt.value = null
})

function dismiss() {
  showDialog.value = false
  localStorage.setItem(STORAGE_KEY, "1")
}

function dismissIos() {
  iosInstallMessage.value = false
  localStorage.setItem(STORAGE_KEY, "1")
}

async function install() {
  if (!deferredPrompt.value) return
  deferredPrompt.value.prompt()
  await deferredPrompt.value.userChoice
  showDialog.value = false
  deferredPrompt.value = null
}
</script>

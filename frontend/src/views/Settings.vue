<template>
  <div class="min-h-screen bg-ground pb-24">
    <header class="pt-safe px-4 pt-4 pb-2 max-w-2xl mx-auto">
      <h1 class="font-display text-xl font-bold">Settings</h1>
    </header>

    <div class="max-w-2xl mx-auto px-4 space-y-4">
      <LoadingSkeleton v-if="loading" :rows="1" />
      <ErrorState v-else-if="error" :message="error" @retry="load" />

      <template v-else>
        <div class="bg-surface rounded-2xl p-4">
          <div class="flex items-center justify-between gap-3">
            <div class="min-w-0">
              <p class="font-display font-semibold">Install App</p>
              <p class="text-xs text-ink-2 mt-0.5">{{ installHint }}</p>
            </div>
            <button
              v-if="!installAlready"
              type="button"
              class="px-4 py-2 rounded-[10px] bg-accent text-accent-fg font-display font-medium text-sm shrink-0 active:opacity-80"
              @click="handleInstallClick"
            >
              Install
            </button>
          </div>
          <div v-if="showInstructions" class="mt-3 text-sm text-ink-2 bg-surface-2 rounded-xl p-3">
            {{ instructions }}
          </div>
        </div>

        <div class="bg-surface rounded-2xl p-4">
          <div class="flex items-center justify-between gap-3">
            <div class="min-w-0">
              <p class="font-display font-semibold">Push Notifications</p>
              <p class="text-xs text-ink-2 mt-0.5">
                {{ pushDisabledReason || "Get notified on this device for approvals and updates." }}
              </p>
            </div>
            <button
              type="button"
              role="switch"
              :aria-checked="pushEnabled"
              :disabled="pushBusy || !!pushDisabledReason"
              class="relative w-12 h-7 rounded-full shrink-0 transition-colors disabled:opacity-50"
              :class="pushEnabled ? 'bg-accent' : 'bg-surface-2 border border-rule'"
              @click="togglePush"
            >
              <span
                class="absolute top-0.5 w-6 h-6 rounded-full bg-white shadow transition-all"
                :class="pushEnabled ? 'left-[22px]' : 'left-0.5'"
              />
            </button>
          </div>
          <p v-if="pushError" class="text-xs text-crit mt-2">{{ pushError }}</p>
        </div>

        <div class="bg-surface rounded-2xl p-4">
          <p class="font-display font-semibold mb-2">Support</p>
          <div v-if="support">
            <p v-if="support.phone" class="text-sm text-ink-2">Phone: {{ support.phone }}</p>
            <p v-if="support.email" class="text-sm text-ink-2">Email: {{ support.email }}</p>
            <p v-if="support.hours" class="text-sm text-ink-2">Hours: {{ support.hours }}</p>
            <p v-if="!support.phone && !support.email && !support.hours" class="text-sm text-ink-3">
              No support details have been configured yet.
            </p>
          </div>
        </div>

        <div class="bg-surface rounded-2xl p-4">
          <p class="font-display font-semibold mb-2">Legal</p>
          <div v-if="legal" class="space-y-3">
            <div v-if="legal.privacy_policy">
              <p class="text-xs font-display text-ink-2 mb-1">Privacy Policy</p>
              <p class="text-sm text-ink-3 whitespace-pre-line">{{ legal.privacy_policy }}</p>
            </div>
            <div v-if="legal.terms_of_use">
              <p class="text-xs font-display text-ink-2 mb-1">Terms of Use</p>
              <p class="text-sm text-ink-3 whitespace-pre-line">{{ legal.terms_of_use }}</p>
            </div>
          </div>
        </div>

        <button
          type="button"
          class="w-full py-3 rounded-[10px] bg-crit/10 text-crit font-display font-medium"
          @click="logout"
        >
          Sign out
        </button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { call } from "frappe-ui"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"
import { useInstallPrompt } from "@/composables/installPrompt"
import { session } from "@/data/session"

const loading = ref(true)
const error = ref("")
const support = ref(null)
const legal = ref(null)

// The browser's own install prompt (Android/desktop) is captured as soon as
// main.js loads, well before this screen might ever be opened - see
// composables/installPrompt.js for why that has to live at module scope
// rather than here.
const { isIos, canInstall, alreadyInstalled: installAlready, promptInstall } = useInstallPrompt()
const showInstructions = ref(false)

const installHint = computed(() => {
  if (installAlready.value) return "Already installed on this device."
  return "Add this app to your home screen for one-tap access and a faster experience."
})

// The button always shows (see the template) - which of these three actually
// happens on tap depends on what this browser supports, not on whether the
// button itself is visible.
const instructions = computed(() => {
  if (isIos) return 'Tap Share, then "Add to Home Screen".'
  return 'Open your browser\'s menu and look for "Install app" or "Add to Home Screen".'
})

function handleInstallClick() {
  // canInstall only ever becomes true after Chrome/Edge has actually fired
  // beforeinstallprompt for this page - which can lag well behind the
  // button existing (a fresh page load, an origin Chrome is still evaluating,
  // ...). Fall back to manual instructions instead of a tap that does nothing.
  if (!isIos && canInstall.value) {
    promptInstall()
    return
  }
  showInstructions.value = !showInstructions.value
}

// Disabled (not just unchecked) whenever the relay itself isn't configured
// on this site - matches the same guard HRMS's own settings screen uses,
// so the switch never sits there clickable-but-doomed-to-fail.
const pushDisabledReason = computed(() => {
  return window?.frappe?.boot?.push_relay_server_url ? "" : "Push notifications aren't set up on this site yet."
})
const pushEnabled = ref(!!window?.frappePushNotification?.isNotificationEnabled())
const pushBusy = ref(false)
const pushError = ref("")

async function togglePush(newValue) {
  pushError.value = ""
  pushBusy.value = true
  try {
    if (pushEnabled.value) {
      await window.frappePushNotification.disableNotification()
      pushEnabled.value = false
    } else {
      const result = await window.frappePushNotification.enableNotification()
      if (result?.permission_granted) {
        pushEnabled.value = true
      } else {
        pushError.value = "Notification permission was not granted."
      }
    }
  } catch (err) {
    pushError.value = err.message || "Could not update push notifications."
  } finally {
    pushBusy.value = false
  }
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    const [supportRes, legalRes] = await Promise.all([
      call("field_sales.api.support.support_info").catch(() => null),
      call("field_sales.api.support.legal_info").catch(() => null),
    ])
    support.value = supportRes
    legal.value = legalRes
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load settings."
  } finally {
    loading.value = false
  }
}

function logout() {
  session.logout.submit()
}

onMounted(load)
</script>

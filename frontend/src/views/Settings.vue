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
          <p class="font-display font-semibold mb-2">Appearance</p>
          <div class="inline-flex rounded-[10px] border border-rule overflow-hidden text-sm font-display">
            <button
              v-for="opt in ['light', 'dark', 'system']"
              :key="opt"
              type="button"
              class="px-3 py-1.5 capitalize"
              :class="themeChoice === opt ? 'bg-accent text-accent-fg' : 'bg-surface text-ink-2'"
              @click="setTheme(opt)"
            >
              {{ opt }}
            </button>
          </div>
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
import { onMounted, ref } from "vue"
import { call } from "frappe-ui"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"
import { themeChoice, setTheme } from "@/composables/theme"
import { session } from "@/data/session"

const loading = ref(true)
const error = ref("")
const support = ref(null)
const legal = ref(null)

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

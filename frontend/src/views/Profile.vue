<template>
  <div class="min-h-screen bg-ground pb-24">
    <header class="pt-safe px-4 pt-4 pb-2 max-w-2xl mx-auto">
      <h1 class="font-display text-xl font-bold">Profile</h1>
    </header>

    <div class="max-w-2xl mx-auto px-4 space-y-4">
      <LoadingSkeleton v-if="loading" :rows="1" />
      <ErrorState v-else-if="error" :message="error" @retry="load" />
      <div v-else-if="profile" class="bg-surface rounded-2xl p-4">
        <p class="font-display font-semibold text-lg">{{ profile.full_name }}</p>
        <p class="text-sm text-ink-2">{{ profile.user }}</p>
        <p v-if="profile.designation" class="text-sm text-ink-2 mt-1">{{ profile.designation }}</p>
        <p v-if="profile.territories?.length" class="text-xs text-ink-3 mt-2">
          Territories: {{ profile.territories.join(", ") }}
        </p>
        <p v-if="profile.roles?.length" class="text-xs text-ink-3 mt-1">
          Roles: {{ profile.roles.join(", ") }}
        </p>
      </div>

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

      <button
        type="button"
        class="w-full py-3 rounded-[10px] bg-crit/10 text-crit font-display font-medium"
        @click="logout"
      >
        Sign out
      </button>
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

const profile = ref(null)
const loading = ref(true)
const error = ref("")

async function load() {
  loading.value = true
  error.value = ""
  try {
    profile.value = await call("field_sales.api.auth.session")
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load your profile."
  } finally {
    loading.value = false
  }
}

function logout() {
  session.logout.submit()
}

onMounted(load)
</script>

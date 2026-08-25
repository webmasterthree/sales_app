<template>
  <div class="min-h-screen bg-ground flex flex-col justify-center px-6">
    <div class="max-w-sm mx-auto w-full">
      <h1 class="font-display text-2xl font-bold text-ink mb-1">Field Sales</h1>
      <p class="text-ink-2 text-sm mb-6">Sign in to log visits, orders and more.</p>

      <form class="space-y-3" @submit.prevent="submit">
        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Email</label>
          <input
            v-model="email"
            type="email"
            autocomplete="username"
            required
            class="w-full h-[52px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
          />
        </div>
        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Password</label>
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            required
            class="w-full h-[52px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
          />
        </div>
        <p v-if="error" class="text-sm text-crit">{{ error }}</p>
        <button
          type="submit"
          class="w-full h-[52px] rounded-[10px] bg-accent text-accent-fg font-display font-medium disabled:opacity-60"
          :disabled="loading"
        >
          {{ loading ? "Signing in…" : "Sign in" }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue"
import { session } from "@/data/session"

const email = ref("")
const password = ref("")
const error = ref("")
const loading = ref(false)

async function submit() {
  error.value = ""
  loading.value = true
  try {
    const res = await session.login(email.value, password.value)
    if (res?.message !== "Logged In") {
      error.value = "Could not sign in with those details."
    }
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not sign in with those details."
  } finally {
    loading.value = false
  }
}
</script>

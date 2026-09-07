<template>
  <div class="min-h-screen bg-ground flex flex-col justify-center px-6">
    <div class="max-w-sm mx-auto w-full">
      <h1 class="font-display text-2xl font-bold text-ink mb-1">Field Sales</h1>
      <p class="text-ink-2 text-sm mb-6">Sign in to log visits, orders and more.</p>

      <div class="inline-flex rounded-[10px] border border-rule overflow-hidden text-sm font-display mb-4">
        <button
          type="button"
          class="px-3 py-1.5"
          :class="mode === 'password' ? 'bg-accent text-accent-fg' : 'bg-surface text-ink-2'"
          @click="switchMode('password')"
        >
          Password
        </button>
        <button
          type="button"
          class="px-3 py-1.5"
          :class="mode === 'otp' ? 'bg-accent text-accent-fg' : 'bg-surface text-ink-2'"
          @click="switchMode('otp')"
        >
          Sign in with OTP
        </button>
      </div>

      <!-- Password sign-in -->
      <form v-if="mode === 'password'" class="space-y-3" @submit.prevent="submitPassword">
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
        <button
          type="button"
          class="w-full text-center text-sm text-ink-2 underline pt-1"
          @click="openForgotPassword"
        >
          Forgot password?
        </button>
      </form>

      <!-- OTP sign-in -->
      <form v-else class="space-y-3" @submit.prevent="otpSent ? submitOtp() : sendOtp()">
        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Email</label>
          <input
            v-model="email"
            type="email"
            autocomplete="username"
            required
            :disabled="otpSent"
            class="w-full h-[52px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent disabled:opacity-60"
          />
        </div>
        <div v-if="otpSent">
          <label class="block text-sm font-display text-ink-2 mb-1">One-time code</label>
          <input
            v-model="otp"
            type="text"
            inputmode="numeric"
            autocomplete="one-time-code"
            required
            class="w-full h-[52px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm tracking-widest focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
          />
          <p class="text-xs text-ink-3 mt-1">{{ otpInfo }}</p>
        </div>
        <p v-if="error" class="text-sm text-crit">{{ error }}</p>
        <p v-if="notice" class="text-sm text-ink-2">{{ notice }}</p>
        <button
          type="submit"
          class="w-full h-[52px] rounded-[10px] bg-accent text-accent-fg font-display font-medium disabled:opacity-60"
          :disabled="loading"
        >
          {{ loading ? "Please wait…" : otpSent ? "Verify code" : "Send code" }}
        </button>
        <button
          v-if="otpSent"
          type="button"
          class="w-full text-center text-sm text-ink-2 underline pt-1"
          @click="resetOtp"
        >
          Use a different email
        </button>
      </form>

      <!-- Forgot password -->
      <div v-if="showForgot" class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 px-4">
        <div class="bg-surface rounded-2xl p-4 max-w-sm w-full">
          <p class="font-display font-semibold mb-2">Reset your password</p>
          <p v-if="!forgotSent" class="text-sm text-ink-2 mb-3">
            We'll email a reset link if this address has an account.
          </p>
          <div v-if="!forgotSent" class="space-y-3">
            <input
              v-model="forgotEmail"
              type="email"
              placeholder="Email"
              class="w-full h-[48px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
            />
            <p v-if="forgotError" class="text-sm text-crit">{{ forgotError }}</p>
            <div class="flex gap-2">
              <button
                type="button"
                class="flex-1 h-[44px] rounded-[10px] border border-rule text-ink-2 font-display"
                @click="showForgot = false"
              >
                Cancel
              </button>
              <button
                type="button"
                class="flex-1 h-[44px] rounded-[10px] bg-accent text-accent-fg font-display font-medium disabled:opacity-60"
                :disabled="forgotLoading"
                @click="submitForgotPassword"
              >
                {{ forgotLoading ? "Sending…" : "Send link" }}
              </button>
            </div>
          </div>
          <div v-else class="space-y-3">
            <p class="text-sm text-ink-2">
              If {{ forgotEmail }} has an account, a reset link is on its way. Check your inbox.
            </p>
            <button
              type="button"
              class="w-full h-[44px] rounded-[10px] bg-accent text-accent-fg font-display font-medium"
              @click="showForgot = false"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue"
import { session } from "@/data/session"

const mode = ref("password")
const email = ref("")
const password = ref("")
const otp = ref("")
const otpSent = ref(false)
const otpInfo = ref("")
const error = ref("")
const notice = ref("")
const loading = ref(false)

function switchMode(next) {
  mode.value = next
  error.value = ""
  notice.value = ""
  resetOtp()
}

function resetOtp() {
  otpSent.value = false
  otp.value = ""
  otpInfo.value = ""
}

async function submitPassword() {
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

async function sendOtp() {
  error.value = ""
  notice.value = ""
  loading.value = true
  try {
    const res = await session.requestOtp(email.value)
    otpSent.value = true
    otpInfo.value = res?.message || "If that address has an account, a code is on its way."
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not send a code. Please try again."
  } finally {
    loading.value = false
  }
}

async function submitOtp() {
  error.value = ""
  loading.value = true
  try {
    const res = await session.loginWithOtp(email.value, otp.value)
    if (!res?.user) {
      error.value = "That code is not valid."
    }
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "That code is not valid."
  } finally {
    loading.value = false
  }
}

// ---------------------------------------------------------------- forgot password

const showForgot = ref(false)
const forgotEmail = ref("")
const forgotSent = ref(false)
const forgotError = ref("")
const forgotLoading = ref(false)

function openForgotPassword() {
  forgotEmail.value = email.value
  forgotSent.value = false
  forgotError.value = ""
  showForgot.value = true
}

async function submitForgotPassword() {
  forgotError.value = ""
  if (!forgotEmail.value) {
    forgotError.value = "Enter your email address."
    return
  }
  forgotLoading.value = true
  try {
    await session.forgotPassword(forgotEmail.value)
    forgotSent.value = true
  } catch (err) {
    // Frappe replies with the same generic message on success or failure to
    // avoid leaking whether an address has an account - only a genuine
    // request error (network, rate limit) should land here.
    forgotError.value = err.messages?.[0] || err.message || "Could not send a reset link right now."
  } finally {
    forgotLoading.value = false
  }
}
</script>

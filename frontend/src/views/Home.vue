<template>
  <div class="min-h-screen bg-ground-home pb-28">
    <!-- domed brand header -->
    <div class="relative bg-accent rounded-b-[36px] pt-safe px-4 pb-16">
      <div class="flex items-center justify-between max-w-2xl mx-auto pt-3">
        <span class="w-10 h-10" aria-hidden="true" />
        <h1 class="font-display text-lg font-semibold text-accent-fg">Home</h1>
        <RouterLink
          :to="{ name: 'Notifications' }"
          class="relative w-10 h-10 flex items-center justify-center rounded-full active:bg-black/10"
          aria-label="Notifications"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--fs-accent-fg)" stroke-width="2" aria-hidden="true">
            <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
          </svg>
          <span
            v-if="unread > 0"
            class="absolute top-1.5 right-1.5 w-2.5 h-2.5 rounded-full bg-crit border-2 border-accent"
          />
        </RouterLink>
      </div>
    </div>

    <LoadingSkeleton v-if="loading && !data" :rows="3" class="max-w-2xl mx-auto px-4 -mt-10 relative z-10" />
    <ErrorState v-else-if="error" :message="error" @retry="load" class="max-w-2xl mx-auto px-4 -mt-10 relative z-10 bg-surface rounded-2xl" />

    <div v-else class="max-w-2xl mx-auto px-4 -mt-14 relative z-10 space-y-5">
      <!-- floating greeting card, overlapping the header -->
      <div class="bg-surface rounded-2xl shadow-lg border border-rule p-4">
        <div class="flex items-start justify-between gap-2 mb-1">
          <p class="font-display font-semibold text-ink">Hey, {{ data?.user?.full_name || "…" }}</p>
          <div class="flex items-center gap-1 shrink-0">
            <SyncStatus />
            <StatusPill :status="checkedIn ? 'Checked in' : 'Checked out'" :tone="checkedIn ? 'good' : 'muted'" />
          </div>
        </div>
        <p class="text-xs text-ink-2 mb-3">
          <template v-if="data?.attendance?.last_time">
            Last {{ data.attendance.last_type === 'IN' ? 'check-in' : 'check-out' }} was at {{ formatTime(data.attendance.last_time) }}
          </template>
          <template v-else>{{ greeting }}, ready for the day?</template>
        </p>

        <div v-if="geoDenied" class="bg-warn/10 text-warn text-sm rounded-[10px] px-3 py-2 mb-3">
          Location access was denied, so we can't confirm where you're punching in from.
          You can still punch in without a location, or
          <button type="button" class="underline" @click="requestLocationAgain">try enabling location again</button>.
        </div>

        <button
          type="button"
          class="w-full h-[52px] rounded-[10px] font-display font-medium bg-action2 text-action2-fg disabled:opacity-60"
          :disabled="punching"
          @click="punch"
        >
          {{ checkedIn ? "Check-out" : "Check-in" }}
        </button>
      </div>

      <!-- score dashboard -->
      <div v-if="data?.scoreboard?.length">
        <p class="font-display font-semibold text-ink mb-2">Score Dashboard</p>
        <div class="grid grid-cols-3 gap-3">
          <div v-for="s in data.scoreboard" :key="s.name" class="bg-surface rounded-2xl border border-rule p-3 flex flex-col gap-2">
            <span class="w-8 h-8 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center" aria-hidden="true">
              <Icon :name="scoreIcon(s.label)" :size="16" />
            </span>
            <div>
              <p class="text-xs text-ink-2">{{ s.label }}</p>
              <p class="text-lg font-display font-bold text-ink">{{ s.count }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- monthly sales target, from ERPNext's own Sales Person / Target
           Detail records - only rendered when a real target exists, never
           a fabricated percentage against nothing. -->
      <div v-if="target?.has_target" class="bg-surface rounded-2xl border border-rule p-4">
        <div class="flex items-center gap-4">
          <svg width="64" height="64" viewBox="0 0 64 64" class="shrink-0">
            <circle cx="32" cy="32" r="27" fill="none" stroke="var(--fs-rule)" stroke-width="6" />
            <circle
              cx="32" cy="32" r="27" fill="none" stroke="var(--fs-accent)" stroke-width="6"
              stroke-linecap="round" transform="rotate(-90 32 32)"
              :stroke-dasharray="169.6"
              :stroke-dashoffset="169.6 * (1 - Math.min(target.percent, 100) / 100)"
            />
            <text x="32" y="37" text-anchor="middle" font-size="15" font-weight="700" fill="var(--fs-ink)" font-family="Poppins">{{ target.percent }}%</text>
          </svg>
          <div class="min-w-0">
            <p class="font-display font-semibold text-sm text-ink">{{ target.month }}&rsquo;s sales target</p>
            <p class="text-xs text-ink-2">₹{{ formatAmount(target.achieved_amount) }} of ₹{{ formatAmount(target.target_amount) }}</p>
          </div>
        </div>
      </div>

      <!-- needs your action: what's actually waiting on this person, not a
           static link - a draft visit to resume, or (for a manager) a real
           pending-approval count. Only renders when there is something. -->
      <div v-if="draftVisit || pendingApprovals > 0" class="space-y-2">
        <p class="font-display font-semibold text-ink text-sm">Needs your action</p>

        <RouterLink
          v-if="draftVisit"
          :to="{ name: 'VisitDetail', params: { name: draftVisit.name } }"
          class="flex items-center justify-between gap-3 bg-surface rounded-2xl border border-rule p-3 active:opacity-80"
        >
          <div class="flex items-center gap-3 min-w-0">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-accent-ink shrink-0" aria-hidden="true">
              <path d="M12 20V10M12 10l-4 4M12 10l4 4"/><path d="M20 21H4"/>
            </svg>
            <div class="min-w-0">
              <p class="font-display font-medium text-sm text-ink truncate">Resume draft visit</p>
              <p class="text-xs text-ink-2 truncate">{{ draftVisit.customer_name || draftVisit.prospect_name || draftVisit.outlet_name || draftVisit.name }}</p>
            </div>
          </div>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-ink-3 shrink-0" aria-hidden="true"><path d="M9 18l6-6-6-6"/></svg>
        </RouterLink>

        <RouterLink
          v-if="pendingApprovals > 0"
          :to="{ name: 'ApprovalQueue' }"
          class="flex items-center justify-between gap-3 bg-surface rounded-2xl border border-rule p-3 active:opacity-80"
        >
          <div class="flex items-center gap-3 min-w-0">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-warn shrink-0" aria-hidden="true">
              <circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>
            </svg>
            <p class="font-display font-medium text-sm text-ink">
              {{ pendingApprovals }} {{ pendingApprovals === 1 ? "request" : "requests" }} awaiting your approval
            </p>
          </div>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-ink-3 shrink-0" aria-hidden="true"><path d="M9 18l6-6-6-6"/></svg>
        </RouterLink>
      </div>

      <!-- module grid -->
      <div>
        <p class="font-display font-semibold text-ink mb-2">Modules</p>
        <EmptyState
          v-if="!data?.modules?.length"
          icon="square"
          title="No modules available"
          description="Nothing has been enabled for your account yet. Ask your administrator to check the Field Sales Module setup."
        />
        <div v-else class="grid grid-cols-2 gap-3">
          <template v-for="tile in data.modules" :key="tile.name">
            <RouterLink
              :to="tile.route"
              class="bg-surface rounded-2xl border border-rule p-3 flex items-center gap-3 active:opacity-80"
            >
              <span class="w-9 h-9 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center shrink-0" aria-hidden="true">
                <Icon :name="iconFor(tile.icon)" :size="18" />
              </span>
              <span class="text-sm text-ink font-display font-medium leading-tight">{{ tile.label }}</span>
            </RouterLink>
          </template>
        </div>
      </div>
    </div>
  </div>

  <LocationConfirmModal :model-value="locationConfirm" @confirm="onLocationConfirm" @cancel="onLocationCancel" />
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { call } from "frappe-ui"
import SyncStatus from "@/components/SyncStatus.vue"
import StatusPill from "@/components/StatusPill.vue"
import EmptyState from "@/components/EmptyState.vue"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"
import Icon from "@/components/Icon.vue"
import LocationConfirmModal from "@/components/LocationConfirmModal.vue"
import { iconFor } from "@/data/modules"
import { queueWrite } from "@/composables/offlineQueue"
import { unreadCount } from "@/data/notifications"
import { buildLocationConfirm } from "@/utils/locationConfirm"

const unread = unreadCount
const data = ref(null)
const draftVisit = ref(null)
const pendingApprovals = ref(0)
const target = ref(null)

// Presentation-only lookup so the score tiles get a matching glyph instead of
// a bare dot; falls back gracefully for any label the server sends that we
// don't recognise yet (same pattern as data/modules.js iconFor).
function scoreIcon(label) {
  const l = (label || "").toLowerCase()
  if (l.includes("visit")) return iconFor("visit")
  if (l.includes("order")) return iconFor("order")
  if (l.includes("demo")) return iconFor("demo")
  if (l.includes("trial") || l.includes("sample")) return iconFor("sample")
  if (l.includes("customer")) return iconFor("customer")
  return "square"
}
const loading = ref(true)
const error = ref("")
const punching = ref(false)
const geoDenied = ref(false)
const locationConfirm = ref(null)

const checkedIn = computed(() => !!data.value?.attendance?.checked_in)

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return "Good morning"
  if (h < 17) return "Good afternoon"
  return "Good evening"
})

function formatTime(v) {
  try {
    return new Date(v.replace(" ", "T")).toLocaleString()
  } catch {
    return v
  }
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    data.value = await call("field_sales.api.home.home")
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load the home screen."
  } finally {
    loading.value = false
  }
  loadActionItems()
}

// "Needs your action" is a secondary panel - it must never block or fail the
// main screen, so its own errors are swallowed rather than surfaced via `error`.
async function loadActionItems() {
  try {
    const visits = await call("field_sales.api.field_visit.visit_list", {
      tab: "draft",
      is_self: 1,
      limit: 1,
    })
    draftVisit.value = visits?.records?.[0] || null
  } catch {
    draftVisit.value = null
  }

  if (data.value?.user?.territories?.length) {
    try {
      const pending = await call("field_sales.api.onboarding.onboarding_list", {
        tab: "pending",
        limit: 1,
      })
      pendingApprovals.value = pending?.total_count || 0
    } catch {
      pendingApprovals.value = 0
    }
  }

  try {
    target.value = await call("field_sales.api.home.sales_target")
  } catch {
    target.value = null
  }
}

function formatAmount(v) {
  return Math.round(v || 0).toLocaleString("en-IN")
}

// A recent cached fix (up to a minute old) resolves almost instantly in the
// common case; a slower dedicated GPS request only runs as a fallback.
function requestPosition(options) {
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
      (err) => {
        if (err.code === err.PERMISSION_DENIED) geoDenied.value = true
        resolve(null)
      },
      options
    )
  })
}

async function getPosition() {
  if (!navigator.geolocation) return null
  const quick = await requestPosition({ enableHighAccuracy: false, timeout: 5000, maximumAge: 60000 })
  if (quick) return quick
  return requestPosition({ enableHighAccuracy: true, timeout: 15000, maximumAge: 0 })
}

function requestLocationAgain() {
  geoDenied.value = false
  getPosition()
}

// The map popup is the final confirmation step, not a receipt: the actual
// punch only fires once the rep taps Confirm.
let confirmResolve = null

function askLocationConfirm(label, confirmLabel, pos) {
  locationConfirm.value = { ...buildLocationConfirm(label, pos), confirmLabel }
  return new Promise((resolve) => {
    confirmResolve = resolve
  })
}

function onLocationConfirm() {
  locationConfirm.value = null
  confirmResolve?.(true)
  confirmResolve = null
}

function onLocationCancel() {
  locationConfirm.value = null
  confirmResolve?.(false)
  confirmResolve = null
}

async function punch() {
  punching.value = true
  try {
    const pos = await getPosition()
    const logType = checkedIn.value ? "OUT" : "IN"
    if (pos) {
      const proceed = await askLocationConfirm(
        logType === "IN" ? "Check in here?" : "Check out here?",
        logType === "IN" ? "Confirm Check-in" : "Confirm Check-out",
        pos
      )
      if (!proceed) return
    }
    const result = await queueWrite({
      method: "field_sales.api.home.punch",
      args: { log_type: logType, latitude: pos?.latitude, longitude: pos?.longitude },
      label: `Attendance ${logType}`,
    })
    if (result?.queued) {
      // optimistic local flip so the UI reflects intent while offline
      data.value.attendance.checked_in = logType === "IN"
      data.value.attendance.last_type = logType
    } else {
      data.value.attendance = result
    }
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not record attendance."
  } finally {
    punching.value = false
  }
}

onMounted(load)
</script>

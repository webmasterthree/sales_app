<template>
  <div class="min-h-screen bg-ground pb-24">
    <AppBar title="Onboarding Funnel" fallback="/reports" />

    <div class="max-w-2xl mx-auto px-4 pt-3">
      <LoadingSkeleton v-if="loading" :rows="4" />
      <ErrorState v-else-if="error" :message="error" @retry="load" />
      <EmptyState
        v-else-if="totalCount === 0"
        icon="customer"
        title="No onboarding requests yet"
        description="Nothing has been filed for a new customer in your territory yet."
      />
      <div v-else class="space-y-4">
        <div class="grid grid-cols-2 gap-3">
          <div class="bg-surface rounded-2xl border border-rule p-4">
            <p class="font-display text-2xl font-bold text-warn">{{ data.pending_count }}</p>
            <p class="text-xs text-ink-2 mt-1">Pending decision</p>
          </div>
          <div class="bg-surface rounded-2xl border border-rule p-4">
            <p class="font-display text-2xl font-bold text-good">{{ data.approved_count }}</p>
            <p class="text-xs text-ink-2 mt-1">Approved (new wins)</p>
          </div>
          <div class="bg-surface rounded-2xl border border-rule p-4">
            <p class="font-display text-2xl font-bold text-crit">{{ data.rejected_count }}</p>
            <p class="text-xs text-ink-2 mt-1">Rejected</p>
          </div>
          <div class="bg-surface rounded-2xl border border-rule p-4">
            <p class="font-display text-2xl font-bold text-ink-2">{{ data.draft_count }}</p>
            <p class="text-xs text-ink-2 mt-1">Still draft</p>
          </div>
        </div>

        <div v-if="data.avg_decision_days != null" class="bg-surface rounded-2xl border border-rule p-4">
          <p class="text-sm text-ink-2">Average time to a decision</p>
          <p class="font-display text-xl font-bold text-ink mt-1">{{ data.avg_decision_days }} days</p>
        </div>

        <div v-if="data.pending.length" class="space-y-2">
          <p class="text-sm font-display font-semibold text-ink px-1">Waiting on a decision</p>
          <div
            v-for="row in data.pending"
            :key="row.name"
            class="bg-surface rounded-2xl border border-rule p-3 flex items-center justify-between gap-3"
          >
            <div class="min-w-0">
              <p class="font-display font-medium text-ink truncate">{{ row.customer_name || row.name }}</p>
              <p class="text-xs text-ink-2">{{ row.territory }}</p>
            </div>
            <StatusPill
              :status="row.waiting_days != null ? `${row.waiting_days}d waiting` : 'Pending'"
              :tone="row.waiting_days != null && row.waiting_days >= 7 ? 'crit' : 'warn'"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { call } from "frappe-ui"
import AppBar from "@/components/AppBar.vue"
import EmptyState from "@/components/EmptyState.vue"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"
import StatusPill from "@/components/StatusPill.vue"

const data = ref({
  draft_count: 0, pending_count: 0, approved_count: 0, rejected_count: 0,
  avg_decision_days: null, pending: [],
})
const loading = ref(true)
const error = ref("")

const totalCount = computed(() =>
  data.value.draft_count + data.value.pending_count + data.value.approved_count + data.value.rejected_count
)

async function load() {
  loading.value = true
  error.value = ""
  try {
    data.value = await call("field_sales.api.onboarding.onboarding_funnel_report")
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load the onboarding funnel."
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="min-h-screen bg-ground pb-24">
    <AppBar title="Sales Target" fallback="/reports" />

    <div class="max-w-2xl mx-auto px-4 pt-3">
      <LoadingSkeleton v-if="loading" />
      <ErrorState v-else-if="error" :message="error" @retry="load" />
      <EmptyState
        v-else-if="!data.has_target"
        icon="report"
        title="No target set"
        description="Your Sales Person record has no target for this period, so there is nothing to measure against."
      />
      <div v-else class="space-y-4">
        <div class="bg-surface rounded-2xl border border-rule p-4">
          <p class="text-xs text-ink-2">{{ data.month }}</p>
          <p class="font-display text-3xl font-bold text-accent-ink mt-1">
            {{ formatCurrency(data.achieved_amount) }}
          </p>
          <p class="text-sm text-ink-2 mt-1">
            of {{ formatCurrency(data.target_amount) }} target · {{ data.percent }}%
          </p>
        </div>

        <div class="bg-surface rounded-2xl border border-rule p-4">
          <div class="h-3 rounded-full bg-surface-2 overflow-hidden">
            <div
              class="h-full bg-accent rounded-full"
              :style="{ width: Math.min(data.percent, 100) + '%' }"
            />
          </div>
          <p class="text-xs text-ink-3 mt-2">
            {{ data.percent >= 100 ? "Target met for this month." : `${100 - data.percent}% left to reach this month's target.` }}
          </p>
        </div>

        <!-- Trend: the single snapshot above can't say whether this rep is
             improving. A 6-month view can - each bar is that month's own
             percent-of-target, same figure the snapshot card shows for the
             current month, just repeated over time. -->
        <div class="bg-surface rounded-2xl border border-rule p-4">
          <p class="text-sm font-display font-semibold text-ink mb-3">Last 6 months</p>

          <LoadingSkeleton v-if="historyLoading" />
          <p v-else-if="historyError" class="text-xs text-warn">{{ historyError }}</p>
          <div v-else-if="history.length" class="flex items-end justify-between gap-2 h-36">
            <div
              v-for="m in history"
              :key="m.label"
              class="flex-1 flex flex-col items-center justify-end h-full"
            >
              <span
                v-if="m.percent > 100"
                class="text-[10px] font-display font-semibold text-accent-ink mb-1"
              >{{ m.percent }}%</span>
              <div class="w-full flex-1 flex items-end">
                <div
                  class="w-full rounded-t-md transition-[height]"
                  :class="barClass(m)"
                  :style="{ height: barHeight(m) + '%' }"
                  :title="`${m.label}: ${formatCurrency(m.achieved_amount)} of ${formatCurrency(m.target_amount)} (${m.percent}%)`"
                />
              </div>
              <span class="text-[10px] text-ink-3 mt-1.5">{{ m.label.split(' ')[0] }}</span>
            </div>
          </div>
          <p v-else class="text-xs text-ink-3">No history to show yet.</p>

          <div class="flex items-center gap-3 mt-3 pt-3 border-t border-rule-soft text-[10px] text-ink-3">
            <span class="inline-flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-accent inline-block" /> Met target</span>
            <span class="inline-flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-accent-soft inline-block" /> Below target</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue"
import { call } from "frappe-ui"
import AppBar from "@/components/AppBar.vue"
import EmptyState from "@/components/EmptyState.vue"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"

const data = ref({ has_target: false, target_amount: 0, achieved_amount: 0, percent: 0, month: null })
const loading = ref(true)
const error = ref("")

const history = ref([])
const historyLoading = ref(true)
const historyError = ref("")

async function load() {
  loading.value = true
  error.value = ""
  try {
    data.value = await call("field_sales.api.home.sales_target")
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load your sales target."
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  historyError.value = ""
  try {
    const result = await call("field_sales.api.home.sales_target_history", { months: 6 })
    history.value = result.months || []
  } catch (err) {
    historyError.value = err.messages?.[0] || err.message || "Could not load the trend."
  } finally {
    historyLoading.value = false
  }
}

// Bar height is scaled to the highest achievement in the window (capped at
// a 100%-of-target reference line), not to each month's own percent, so a
// 475%-of-target month doesn't flatten every ordinary month into a sliver
// next to it. A month with no target data at all still draws a token-height
// bar rather than nothing, so a genuinely-zero month stays visible.
const MIN_BAR_PERCENT = 4
function barHeight(m) {
  const reference = Math.max(100, ...history.value.map((h) => h.percent))
  return Math.max(MIN_BAR_PERCENT, Math.min(100, (m.percent / reference) * 100))
}
function barClass(m) {
  return m.percent >= 100 ? "bg-accent" : "bg-accent-soft"
}

function formatCurrency(value) {
  return `₹${Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`
}

onMounted(() => {
  load()
  loadHistory()
})
</script>

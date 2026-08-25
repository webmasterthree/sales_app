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

function formatCurrency(value) {
  return `₹${Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`
}

onMounted(load)
</script>

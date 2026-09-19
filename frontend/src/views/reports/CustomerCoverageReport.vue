<template>
  <div class="min-h-screen bg-ground pb-24">
    <AppBar title="Customer Coverage" fallback="/reports" />

    <div class="max-w-2xl mx-auto px-4 pt-3">
      <LoadingSkeleton v-if="loading" :rows="4" />
      <ErrorState v-else-if="error" :message="error" @retry="load" />
      <EmptyState
        v-else-if="!data.records.length"
        icon="customer"
        title="No customers in your territory"
        description="There is nothing to check coverage against yet."
      />
      <div v-else class="space-y-4">
        <div class="bg-surface rounded-2xl border border-rule p-4">
          <p class="font-display text-3xl font-bold text-warn">{{ data.overdue_count }}</p>
          <p class="text-sm text-ink-2 mt-1">
            of {{ data.total_count }} customers not visited in the last {{ data.min_days }} days
          </p>
        </div>

        <div class="flex gap-2">
          <button
            v-for="opt in windowOptions"
            :key="opt"
            type="button"
            class="flex-1 h-9 rounded-xl text-sm font-display font-medium border"
            :class="opt === minDays ? 'bg-accent-soft text-accent-ink border-accent' : 'bg-surface text-ink-2 border-rule'"
            @click="minDays = opt; load()"
          >
            {{ opt }}d
          </button>
        </div>

        <div class="space-y-2">
          <div
            v-for="row in data.records"
            :key="row.name"
            class="bg-surface rounded-2xl border border-rule p-3 flex items-center justify-between gap-3"
          >
            <div class="min-w-0">
              <p class="font-display font-medium text-ink truncate">{{ row.customer_name || row.name }}</p>
              <p class="text-xs text-ink-2">
                {{ row.customer_level }} · {{ row.territory }}
                <template v-if="row.last_visit_date"> · last visit {{ formatDate(row.last_visit_date) }}</template>
              </p>
            </div>
            <StatusPill :status="pillLabel(row)" :tone="pillTone(row)" />
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
import StatusPill from "@/components/StatusPill.vue"

const data = ref({ records: [], overdue_count: 0, min_days: 30, total_count: 0 })
const loading = ref(true)
const error = ref("")
const minDays = ref(30)
const windowOptions = [30, 60, 90]

async function load() {
  loading.value = true
  error.value = ""
  try {
    data.value = await call("field_sales.api.customers.coverage_report", { min_days: minDays.value })
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load coverage."
  } finally {
    loading.value = false
  }
}

// Never-visited reads as the worst case (crit), then a three-way split
// against whichever window is currently selected - good well inside it,
// warn once past the halfway point, crit once past it entirely, matching
// how StatusPill's tone vocabulary is used elsewhere in the app.
function pillLabel(row) {
  if (row.days_since == null) return "Never visited"
  return `${row.days_since}d ago`
}
function pillTone(row) {
  if (row.days_since == null) return "crit"
  if (row.days_since >= minDays.value) return "crit"
  if (row.days_since >= minDays.value / 2) return "warn"
  return "good"
}

function formatDate(value) {
  return new Date(value).toLocaleDateString("en-IN", { day: "numeric", month: "short" })
}

onMounted(load)
</script>

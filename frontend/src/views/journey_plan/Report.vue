<template>
  <div class="min-h-screen bg-ground pb-24">
    <AppBar title="Visit Report" fallback="/reports" />

    <div class="max-w-2xl mx-auto px-4 pt-3">
      <input
        v-model="date"
        type="date"
        class="w-full h-[44px] rounded-[10px] border border-rule bg-surface px-3 text-sm"
      />
    </div>

    <div class="max-w-2xl mx-auto px-4 pt-3">
      <LoadingSkeleton v-if="loading" :rows="3" />
      <ErrorState v-else-if="error" :message="error" @retry="load" />
      <EmptyState
        v-else-if="!rows.length"
        icon="journey"
        title="Nothing for this date"
        description="No journey plans or field visits found in your territory for this date."
      />

      <div v-else class="space-y-3">
        <div v-for="row in rows" :key="row.name || row.sales_person" class="bg-surface rounded-2xl border border-rule p-4">
          <div class="flex items-center justify-between gap-2">
            <div class="min-w-0">
              <p class="font-display font-semibold text-ink truncate">{{ row.sales_person_name || row.sales_person }}</p>
              <p class="text-xs text-ink-2">
                <template v-if="row.name">{{ row.name }} · {{ row.territory }} · {{ row.nature_of_travel }}</template>
                <template v-else>No journey plan filed for this date</template>
              </p>
            </div>
            <StatusPill :status="row.visits.length ? 'Visited' : 'No visit'" :tone="row.visits.length ? 'good' : 'crit'" />
          </div>

          <p v-if="!row.visits.length" class="text-xs text-ink-3 mt-3">
            No field visit recorded against this plan yet.
          </p>

          <div v-else class="mt-3 space-y-3">
            <div v-for="visit in row.visits" :key="visit.name" class="border-t border-rule-soft pt-3">
              <div class="flex items-center justify-between gap-2">
                <p class="text-sm font-display text-ink">{{ visit.customer_name || visit.prospect_name || visit.name }}</p>
                <StatusPill :status="visit.geofence_status || 'Not Checked'" />
              </div>
              <p class="text-xs text-ink-2 mt-0.5">
                Check-in {{ formatTime(visit.check_in) }}<template v-if="visit.check_out"> · Check-out {{ formatTime(visit.check_out) }}</template>
              </p>
              <p v-if="visit.captured_address" class="text-xs text-ink-3 mt-0.5">{{ visit.captured_address }}</p>

              <ReadOnlyMap
                v-if="visit.check_in_latitude && visit.check_in_longitude"
                :lat="visit.check_in_latitude"
                :lng="visit.check_in_longitude"
                class="mt-2"
              />
              <p v-else class="text-xs text-ink-3 mt-2">No geolocation captured for this visit.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from "vue"
import { call } from "frappe-ui"
import AppBar from "@/components/AppBar.vue"
import StatusPill from "@/components/StatusPill.vue"
import ReadOnlyMap from "@/components/ReadOnlyMap.vue"
import EmptyState from "@/components/EmptyState.vue"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"

const date = ref(new Date().toISOString().slice(0, 10))
const rows = ref([])
const loading = ref(true)
const error = ref("")

function formatTime(dt) {
  if (!dt) return "—"
  const d = new Date(dt.replace(" ", "T"))
  return isNaN(d) ? dt : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    rows.value = (await call("field_sales.api.journey_plan.journey_plan_visit_report", { date: date.value })) || []
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load the visit report."
  } finally {
    loading.value = false
  }
}

watch(date, load)
onMounted(load)
</script>

<template>
  <div class="min-h-screen bg-ground pb-24">
    <header class="pt-safe px-4 pt-4 pb-2 max-w-2xl mx-auto">
      <h1 class="font-display text-xl font-bold">Performance</h1>
      <p class="text-sm text-ink-2">This month, ranked by visits filed then orders.</p>
    </header>

    <div class="max-w-2xl mx-auto px-4">
      <LoadingSkeleton v-if="loading" />
      <ErrorState v-else-if="error" :message="error" @retry="load" />
      <EmptyState
        v-else-if="!rows.length"
        icon="bar-chart"
        title="Nothing to rank yet"
        description="No submitted visits or orders in your territory this month."
      />
      <div v-else class="space-y-2">
        <div
          v-for="row in rows"
          :key="row.sales_person"
          class="bg-surface rounded-2xl p-3 flex items-center gap-3"
        >
          <span class="w-7 h-7 rounded-full bg-accent-soft text-accent-ink font-display font-bold flex items-center justify-center text-sm shrink-0">
            {{ row.rank }}
          </span>
          <div class="min-w-0 flex-1">
            <p class="font-display font-medium truncate">{{ row.sales_person_name || row.sales_person }}</p>
            <p class="text-xs text-ink-2">{{ row.visits }} visits · {{ row.orders }} orders</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue"
import { call } from "frappe-ui"
import EmptyState from "@/components/EmptyState.vue"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"

const rows = ref([])
const loading = ref(true)
const error = ref("")

async function load() {
  loading.value = true
  error.value = ""
  try {
    rows.value = await call("field_sales.api.home.leaderboard")
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load the leaderboard."
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

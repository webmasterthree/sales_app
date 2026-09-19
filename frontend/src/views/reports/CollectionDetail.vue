<template>
  <div class="min-h-screen bg-ground pb-24">
    <AppBar title="Collection" fallback="/reports/collections" />

    <div class="max-w-2xl mx-auto px-4 pt-3">
      <LoadingSkeleton v-if="loading" :rows="4" />
      <ErrorState v-else-if="error" :message="error" @retry="load" />

      <div v-else class="space-y-4">
        <div class="bg-surface rounded-2xl border border-rule p-3.5">
          <p class="text-xs text-ink-3 mb-0.5">{{ detail.name }}</p>
          <p class="font-display font-semibold text-ink">{{ detail.customer_name || detail.customer }}</p>
          <p class="font-display text-3xl font-bold text-ink mt-1">+{{ formatCurrency(detail.paid_amount) }}</p>
        </div>

        <div class="grid grid-cols-2 gap-2.5">
          <div class="bg-surface rounded-xl border border-rule p-2.5">
            <p class="text-[10px] text-ink-3 mb-0.5">Mode</p>
            <p class="text-sm font-display font-medium text-ink">{{ detail.mode_of_payment }}</p>
          </div>
          <div class="bg-surface rounded-xl border border-rule p-2.5">
            <p class="text-[10px] text-ink-3 mb-0.5">Date</p>
            <p class="text-sm font-display font-medium text-ink">{{ detail.posting_date }}</p>
          </div>
          <div class="bg-surface rounded-xl border border-rule p-2.5">
            <p class="text-[10px] text-ink-3 mb-0.5">Reference</p>
            <p class="text-sm font-display font-medium text-ink truncate">{{ detail.reference_no || '—' }}</p>
          </div>
          <div class="bg-surface rounded-xl border border-rule p-2.5">
            <p class="text-[10px] text-ink-3 mb-0.5">Collected by</p>
            <p class="text-sm font-display font-medium text-ink truncate">{{ detail.collected_by }}</p>
          </div>
        </div>

        <div class="space-y-2.5">
          <div class="flex items-center gap-2 pb-1.5 border-b border-rule-soft">
            <span class="w-5 h-5 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center shrink-0"><Icon name="order" :size="11" /></span>
            <p class="text-[11px] font-display font-semibold uppercase tracking-wide text-ink-2">Applied against</p>
          </div>
          <div
            v-for="ref in detail.references"
            :key="ref.invoice"
            class="bg-surface rounded-xl border border-rule p-3 flex items-center justify-between gap-3"
          >
            <div class="min-w-0">
              <p class="text-sm font-display font-medium text-ink truncate">{{ ref.invoice }}</p>
              <p class="text-xs text-ink-3">
                {{ ref.outstanding_amount > 0 ? `${formatCurrency(ref.outstanding_amount)} still outstanding` : "Fully settled" }}
              </p>
            </div>
            <span class="text-sm font-display text-ink tabular-nums shrink-0">{{ formatCurrency(ref.allocated_amount) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue"
import { call } from "frappe-ui"
import { useRoute } from "vue-router"
import AppBar from "@/components/AppBar.vue"
import ErrorState from "@/components/ErrorState.vue"
import Icon from "@/components/Icon.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"

const route = useRoute()
const name = route.params.name

const loading = ref(true)
const error = ref("")
const detail = ref({ references: [] })

async function load() {
  loading.value = true
  error.value = ""
  try {
    detail.value = await call("field_sales.api.customers.collection_detail", { name })
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load this collection."
  } finally {
    loading.value = false
  }
}

function formatCurrency(value) {
  return `₹${Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`
}

onMounted(load)
</script>

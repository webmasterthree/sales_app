<template>
  <div class="min-h-screen bg-ground pb-24">
    <AppBar title="Ledger History" :subtitle="doc?.customer_name" fallback="/customers" />

    <div class="max-w-2xl mx-auto px-4 pt-3 space-y-3">
      <LoadingSkeleton v-if="loading" :rows="3" />
      <ErrorState v-else-if="error" :message="error" @retry="load" />

      <template v-else-if="ledger">
        <div class="flex gap-3">
          <div class="flex-1 bg-surface-2 rounded-2xl p-3">
            <p class="text-[11px] font-display font-bold uppercase tracking-wide text-ink-2">Outstanding balance</p>
            <p class="text-lg font-display font-extrabold text-ink" style="font-variant-numeric: tabular-nums">
              ₹{{ flt2(ledger.total_outstanding) }}
            </p>
          </div>
          <div class="flex-1 bg-surface-2 rounded-2xl p-3">
            <p class="text-[11px] font-display font-bold uppercase tracking-wide text-ink-2">Overdue invoices</p>
            <p class="text-lg font-display font-extrabold text-ink" style="font-variant-numeric: tabular-nums">
              {{ ledger.overdue_count }}
            </p>
          </div>
        </div>

        <EmptyState
          v-if="!ledger.invoices.length"
          icon="price"
          title="No invoices yet"
          description="Nothing has been billed to this customer."
        />
        <div v-else class="border border-rule rounded-2xl overflow-hidden">
          <div class="grid grid-cols-[64px_1fr_74px_74px] gap-1.5 bg-accent px-3 py-2 text-[10px] font-display font-extrabold text-accent-fg">
            <span>Date</span><span>Invoice</span><span class="text-right">Amount</span><span class="text-right">Balance</span>
          </div>
          <div
            v-for="row in ledger.invoices"
            :key="row.name"
            class="grid grid-cols-[64px_1fr_74px_74px] gap-1.5 px-3 py-2 text-xs border-b border-rule-soft last:border-0"
          >
            <span class="text-ink-2">{{ formatDate(row.posting_date) }}</span>
            <span class="text-ink truncate">{{ row.name }}</span>
            <span class="text-right text-ink" style="font-variant-numeric: tabular-nums">₹{{ flt2(row.grand_total) }}</span>
            <span
              class="text-right font-display font-semibold"
              :class="row.outstanding_amount > 0 ? 'text-crit' : 'text-good'"
              style="font-variant-numeric: tabular-nums"
            >₹{{ flt2(row.outstanding_amount) }}</span>
          </div>
        </div>
      </template>
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

const props = defineProps({ name: { type: String, required: true } })

const doc = ref(null)
const ledger = ref(null)
const loading = ref(true)
const error = ref("")

function flt2(v) {
  return (v || 0).toFixed(2)
}

function formatDate(v) {
  if (!v) return "—"
  const d = new Date(v)
  return `${d.getDate()} ${d.toLocaleDateString("en-US", { month: "short" })}`
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    const [customerRes, ledgerRes] = await Promise.all([
      call("field_sales.api.customers.customer", { name: props.name }),
      call("field_sales.api.customers.customer_ledger", { customer: props.name }),
    ])
    doc.value = customerRes
    ledger.value = ledgerRes
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load the ledger."
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

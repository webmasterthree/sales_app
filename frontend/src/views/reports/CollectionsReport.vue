<template>
  <div class="min-h-screen bg-ground pb-24">
    <AppBar title="Collections" fallback="/reports" />

    <div class="max-w-2xl mx-auto px-4 pt-3">
      <div class="flex bg-surface border border-rule rounded-full p-1 mb-4">
        <button
          type="button"
          class="flex-1 h-[32px] rounded-full text-xs font-display font-semibold transition-colors"
          :class="tab === 'outstanding' ? 'bg-accent text-accent-fg' : 'text-ink-2'"
          @click="tab = 'outstanding'"
        >
          Outstanding
        </button>
        <button
          type="button"
          class="flex-1 h-[32px] rounded-full text-xs font-display font-semibold transition-colors"
          :class="tab === 'history' ? 'bg-accent text-accent-fg' : 'text-ink-2'"
          @click="onHistoryTab"
        >
          History
        </button>
      </div>

      <template v-if="tab === 'outstanding'">
        <LoadingSkeleton v-if="loading" :rows="4" />
        <ErrorState v-else-if="error" :message="error" @retry="load" />
        <EmptyState
          v-else-if="!data.records.length"
          icon="report"
          title="Nothing outstanding"
          description="No customer in your territory has an unpaid invoice right now."
        />
        <div v-else class="space-y-4">
          <div class="bg-gradient-to-br from-accent-soft to-transparent rounded-2xl border border-accent/30 p-4">
            <p class="text-xs text-ink-2 mb-1">Outstanding</p>
            <p class="font-display text-3xl font-bold text-warn tabular-nums">{{ formatCurrency(data.total_outstanding) }}</p>
            <p class="text-sm text-ink-2 mt-1">
              {{ data.total_count }} customer{{ data.total_count === 1 ? '' : 's' }} · {{ data.total_overdue_count }} overdue invoice{{ data.total_overdue_count === 1 ? '' : 's' }}
            </p>
          </div>

          <div class="space-y-2">
            <p class="text-[11px] font-display font-semibold uppercase tracking-wide text-ink-3 px-0.5">Customers</p>
            <div
              v-for="row in data.records"
              :key="row.name"
              class="bg-surface rounded-2xl border border-rule p-3 flex items-center gap-3"
            >
              <div
                class="w-9 h-9 rounded-full flex items-center justify-center shrink-0 text-xs font-display font-semibold"
                :class="row.overdue_count ? 'bg-crit/15 text-crit' : 'bg-accent-soft text-accent-ink'"
              >
                {{ initials(row.customer_name || row.name) }}
              </div>
              <div class="min-w-0 flex-1">
                <p class="font-display font-medium text-ink truncate">{{ row.customer_name || row.name }}</p>
                <p class="text-xs text-ink-3">
                  {{ row.customer_level }} · {{ row.invoice_count }} invoice{{ row.invoice_count === 1 ? '' : 's' }}
                  <template v-if="row.overdue_count">
                    · <span class="text-crit">{{ row.overdue_count }} overdue</span>
                  </template>
                </p>
              </div>
              <div class="text-right shrink-0 space-y-1.5">
                <p class="font-display font-semibold text-ink tabular-nums">{{ formatCurrency(row.outstanding) }}</p>
                <button
                  type="button"
                  class="block ml-auto h-[26px] px-3 rounded-full bg-accent text-accent-fg text-[11px] font-display font-semibold"
                  @click="collect(row)"
                >
                  Collect
                </button>
              </div>
            </div>
          </div>
        </div>
      </template>

      <template v-else>
        <LoadingSkeleton v-if="historyLoading" :rows="4" />
        <ErrorState v-else-if="historyError" :message="historyError" @retry="loadHistory" />
        <EmptyState
          v-else-if="!history.length"
          icon="report"
          title="No collections yet"
          description="Payments recorded from this app will show up here."
        />
        <div v-else class="space-y-2">
          <button
            v-for="row in history"
            :key="row.name"
            type="button"
            class="w-full text-left bg-surface rounded-2xl border border-rule p-3 flex items-center gap-3"
            @click="openCollection(row)"
          >
            <div class="w-8 h-8 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center shrink-0">
              <Icon name="check-circle" :size="15" />
            </div>
            <div class="min-w-0 flex-1">
              <p class="font-display font-medium text-ink truncate">{{ row.customer_name || row.customer }}</p>
              <p class="text-xs text-ink-3 truncate mt-0.5">
                {{ row.mode_of_payment }}<template v-if="row.reference_no"> · {{ row.reference_no }}</template>
                · by {{ row.collected_by }}
              </p>
            </div>
            <div class="text-right shrink-0">
              <p class="font-display font-semibold text-accent-ink tabular-nums">+{{ formatCurrency(row.paid_amount) }}</p>
              <p class="text-[10px] text-ink-3 mt-0.5">{{ row.posting_date }}</p>
            </div>
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue"
import { call } from "frappe-ui"
import { useRouter } from "vue-router"
import AppBar from "@/components/AppBar.vue"
import EmptyState from "@/components/EmptyState.vue"
import ErrorState from "@/components/ErrorState.vue"
import Icon from "@/components/Icon.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"

const router = useRouter()
const tab = ref("outstanding")

const data = ref({ records: [], total_outstanding: 0, total_overdue_count: 0, total_count: 0 })
const loading = ref(true)
const error = ref("")

const history = ref([])
const historyLoading = ref(true)
const historyLoaded = ref(false)
const historyError = ref("")

function collect(row) {
  router.push({ name: "CollectPayment", params: { customer: row.name } })
}

function openCollection(row) {
  router.push({ name: "CollectionDetail", params: { name: row.name } })
}

function onHistoryTab() {
  tab.value = "history"
  if (!historyLoaded.value) loadHistory()
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    data.value = await call("field_sales.api.customers.collections_report")
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load collections."
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  historyError.value = ""
  try {
    history.value = await call("field_sales.api.customers.collections_history")
    historyLoaded.value = true
  } catch (err) {
    historyError.value = err.messages?.[0] || err.message || "Could not load collection history."
  } finally {
    historyLoading.value = false
  }
}

function initials(name) {
  const parts = (name || "").trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return "?"
  return (parts[0][0] + (parts[1]?.[0] || "")).toUpperCase()
}

function formatCurrency(value) {
  return `₹${Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`
}

onMounted(load)
</script>

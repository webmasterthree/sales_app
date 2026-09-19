<template>
  <div class="min-h-screen bg-ground pb-28">
    <AppBar title="Collect payment" fallback="/reports/collections" />

    <div class="max-w-2xl mx-auto px-4 pt-3">
      <LoadingSkeleton v-if="loading" :rows="4" />
      <ErrorState v-else-if="loadError" :message="loadError" @retry="load" />

      <div v-else class="space-y-4">
        <div class="bg-surface rounded-2xl border border-rule p-3.5">
          <p class="font-display font-semibold text-ink">{{ ledger.customer_name || customer }}</p>
          <p class="text-xs text-ink-2 mt-0.5">
            {{ formatCurrency(ledger.total_outstanding) }} outstanding across {{ ledger.invoices.length }}
            invoice{{ ledger.invoices.length === 1 ? '' : 's' }}
          </p>
        </div>

        <EmptyState
          v-if="!ledger.invoices.length"
          icon="report"
          title="Nothing outstanding"
          description="This customer has no unpaid invoices right now."
        />

        <template v-else>
          <div class="space-y-2.5">
            <div class="flex items-center justify-between gap-2 pb-1.5 border-b border-rule-soft">
              <div class="flex items-center gap-2">
                <span class="w-5 h-5 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center shrink-0"><Icon name="order" :size="11" /></span>
                <p class="text-[11px] font-display font-semibold uppercase tracking-wide text-ink-2">Apply against invoices</p>
              </div>
              <button
                type="button"
                class="text-[11px] font-display font-semibold text-accent-ink shrink-0"
                @click="toggleAll"
              >
                {{ allSelected ? "Unselect all" : "Select all" }}
              </button>
            </div>
            <label
              v-for="inv in ledger.invoices"
              :key="inv.name"
              class="flex items-center gap-2.5 rounded-xl border px-3 py-2.5"
              :class="selected[inv.name] ? 'border-accent bg-accent-soft/40' : 'border-rule bg-surface'"
            >
              <input
                type="checkbox"
                class="w-4 h-4 shrink-0"
                :checked="!!selected[inv.name]"
                @change="toggleInvoice(inv)"
              />
              <div class="flex-1 min-w-0">
                <p class="text-sm font-display font-medium text-ink truncate">{{ inv.name }}</p>
                <p class="text-xs" :class="isOverdue(inv) ? 'text-crit' : 'text-ink-3'">
                  <template v-if="isOverdue(inv)">Overdue · due {{ inv.due_date }}</template>
                  <template v-else-if="inv.due_date">due {{ inv.due_date }}</template>
                </p>
              </div>
              <span class="text-sm font-display text-ink tabular-nums shrink-0">{{ formatCurrency(inv.outstanding_amount) }}</span>
            </label>
          </div>

          <div class="bg-surface rounded-2xl border border-rule p-3.5 space-y-3.5">
            <div>
              <label class="block text-sm font-display text-ink-2 mb-1">Amount collected</label>
              <input
                v-model.number="amount"
                type="number"
                inputmode="decimal"
                min="0"
                :max="selectedTotal"
                step="0.01"
                class="w-full h-[46px] rounded-[10px] border border-rule bg-surface px-3 text-sm"
              />
              <p v-if="amountError" class="text-xs text-crit mt-1">{{ amountError }}</p>
            </div>

            <div>
              <label class="block text-sm font-display text-ink-2 mb-1">Mode of payment</label>
              <select v-model="modeOfPayment" class="w-full h-[46px] rounded-[10px] border border-rule bg-surface px-3 text-sm">
                <option value="" disabled>Select…</option>
                <option v-for="m in modesOfPayment" :key="m.name" :value="m.name">{{ m.name }}</option>
              </select>
            </div>

            <div>
              <label class="block text-sm font-display text-ink-2 mb-1">
                Reference no{{ referenceRequired ? "" : " (optional)" }}
              </label>
              <input
                v-model="referenceNo"
                type="text"
                placeholder="Cheque or UTR number"
                class="w-full h-[46px] rounded-[10px] border border-rule bg-surface px-3 text-sm"
              />
              <p v-if="referenceError" class="text-xs text-crit mt-1">{{ referenceError }}</p>
            </div>
          </div>

          <p v-if="submitError" class="text-xs text-crit text-center">{{ submitError }}</p>

          <button
            type="button"
            class="w-full h-[48px] rounded-xl bg-accent text-accent-fg font-display font-semibold text-sm disabled:opacity-50"
            :disabled="submitting || !canSubmit"
            @click="submit"
          >
            {{ submitting ? "Recording…" : `Record collection · ${formatCurrency(amount || 0)}` }}
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue"
import { call } from "frappe-ui"
import { useRoute, useRouter } from "vue-router"
import AppBar from "@/components/AppBar.vue"
import EmptyState from "@/components/EmptyState.vue"
import ErrorState from "@/components/ErrorState.vue"
import Icon from "@/components/Icon.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"

const route = useRoute()
const router = useRouter()
const customer = route.params.customer

const loading = ref(true)
const loadError = ref("")
const ledger = ref({ customer_name: "", invoices: [], total_outstanding: 0 })
const selected = ref({})
const amount = ref(0)
const modeOfPayment = ref("")
const modesOfPayment = ref([])

const referenceRequired = computed(() => {
  const mode = modesOfPayment.value.find((m) => m.name === modeOfPayment.value)
  return !!mode && mode.type !== "Cash"
})

const referenceError = computed(() => {
  if (referenceRequired.value && !referenceNo.value.trim()) {
    return `Enter a reference number for ${modeOfPayment.value}.`
  }
  return ""
})
const referenceNo = ref("")
const submitting = ref(false)
const submitError = ref("")

const today = new Date().toISOString().slice(0, 10)

function isOverdue(inv) {
  return inv.due_date && inv.due_date < today
}

const selectedTotal = computed(() =>
  ledger.value.invoices
    .filter((inv) => selected.value[inv.name])
    .reduce((sum, inv) => sum + Number(inv.outstanding_amount || 0), 0)
)

const amountError = computed(() => {
  if (amount.value === "" || amount.value === null) return ""
  if (Number(amount.value) <= 0) return "Enter an amount greater than zero."
  if (Number(amount.value) > selectedTotal.value + 0.01) return "Amount can't exceed the selected invoices' total."
  return ""
})

const canSubmit = computed(() =>
  Object.values(selected.value).some(Boolean) &&
  Number(amount.value) > 0 &&
  !amountError.value &&
  !!modeOfPayment.value &&
  !referenceError.value
)

function toggleInvoice(inv) {
  if (selected.value[inv.name]) {
    delete selected.value[inv.name]
  } else {
    selected.value[inv.name] = true
  }
  selected.value = { ...selected.value }
  amount.value = Number(selectedTotal.value.toFixed(2))
}

const allSelected = computed(
  () => ledger.value.invoices.length > 0 && ledger.value.invoices.every((inv) => selected.value[inv.name])
)

function toggleAll() {
  if (allSelected.value) {
    selected.value = {}
  } else {
    const sel = {}
    for (const inv of ledger.value.invoices) sel[inv.name] = true
    selected.value = sel
  }
  amount.value = Number(selectedTotal.value.toFixed(2))
}

async function load() {
  loading.value = true
  loadError.value = ""
  try {
    const [ledgerData, modes] = await Promise.all([
      call("field_sales.api.customers.customer_ledger", { customer }),
      call("field_sales.api.customers.mode_of_payment_list"),
    ])
    ledger.value = ledgerData
    modesOfPayment.value = modes
    const sel = {}
    for (const inv of ledgerData.invoices) sel[inv.name] = true
    selected.value = sel
    amount.value = Number(selectedTotal.value.toFixed(2))
  } catch (err) {
    loadError.value = err.messages?.[0] || err.message || "Could not load this customer's ledger."
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!canSubmit.value || submitting.value) return
  submitting.value = true
  submitError.value = ""
  try {
    await call("field_sales.api.customers.record_collection", {
      customer,
      amount: amount.value,
      mode_of_payment: modeOfPayment.value,
      invoices: Object.keys(selected.value).filter((name) => selected.value[name]),
      reference_no: referenceNo.value || undefined,
    })
    router.replace("/reports/collections")
  } catch (err) {
    submitError.value = err.messages?.[0] || err.message || "Could not record this collection."
  } finally {
    submitting.value = false
  }
}

function formatCurrency(value) {
  return `₹${Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`
}

onMounted(load)
</script>

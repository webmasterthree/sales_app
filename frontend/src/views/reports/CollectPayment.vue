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
            <div
              v-for="inv in ledger.invoices"
              :key="inv.name"
              class="rounded-xl border px-3 py-2.5"
              :class="isSelected(inv) ? 'border-accent bg-accent-soft/40' : 'border-rule bg-surface'"
            >
              <label class="flex items-center gap-2.5">
                <input
                  type="checkbox"
                  class="w-4 h-4 shrink-0"
                  :checked="isSelected(inv)"
                  @change="toggleInvoice(inv)"
                />
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-display font-medium text-ink truncate">{{ inv.name }}</p>
                  <p class="text-xs" :class="isOverdue(inv) ? 'text-crit' : 'text-ink-3'">
                    <template v-if="isOverdue(inv)">Overdue · due {{ inv.due_date }} · </template>
                    <template v-else-if="inv.due_date">due {{ inv.due_date }} · </template>
                    outstanding {{ formatCurrency(inv.outstanding_amount) }}
                  </p>
                </div>
              </label>
              <div v-if="isSelected(inv)" class="flex items-start gap-2 mt-2 pl-[26px]">
                <div class="flex-1 min-w-0">
                  <span class="block text-[10px] text-ink-3 mb-0.5">Amount</span>
                  <input
                    v-model.number="invoiceAmounts[inv.name]"
                    type="number"
                    inputmode="decimal"
                    min="0"
                    :max="inv.outstanding_amount"
                    step="0.01"
                    class="w-full h-[36px] rounded-[8px] border bg-surface px-2 text-sm tabular-nums"
                    :class="invoiceAmountError(inv) ? 'border-crit' : 'border-rule'"
                  />
                </div>
                <div class="flex-1 min-w-0">
                  <span class="block text-[10px] text-ink-3 mb-0.5">
                    Reference no{{ referenceRequired ? "" : " (optional)" }}
                  </span>
                  <input
                    v-model="invoiceReferences[inv.name]"
                    type="text"
                    placeholder="Cheque or UTR"
                    class="w-full h-[36px] rounded-[8px] border bg-surface px-2 text-sm"
                    :class="invoiceReferenceError(inv) ? 'border-crit' : 'border-rule'"
                  />
                </div>
              </div>
              <p v-if="isSelected(inv) && invoiceAmountError(inv)" class="text-xs text-crit mt-1 pl-[26px]">
                {{ invoiceAmountError(inv) }}
              </p>
              <p
                v-else-if="isSelected(inv) && Number(invoiceAmounts[inv.name]) < Number(inv.outstanding_amount)"
                class="text-xs text-ink-3 mt-1 pl-[26px]"
              >
                Partial · {{ formatCurrency(inv.outstanding_amount - invoiceAmounts[inv.name]) }} will remain outstanding
              </p>
              <p v-if="isSelected(inv) && invoiceReferenceError(inv)" class="text-xs text-crit mt-1 pl-[26px]">
                {{ invoiceReferenceError(inv) }}
              </p>
            </div>
          </div>

          <div class="bg-surface rounded-2xl border border-rule p-3.5 space-y-3.5">
            <div class="flex items-baseline justify-between pb-3 border-b border-rule-soft">
              <span class="text-xs text-ink-2">Total collected</span>
              <span class="text-lg font-display font-semibold text-ink tabular-nums">{{ formatCurrency(selectedTotal) }}</span>
            </div>

            <div>
              <label class="block text-sm font-display text-ink-2 mb-1">Mode of payment</label>
              <select v-model="modeOfPayment" class="w-full h-[46px] rounded-[10px] border border-rule bg-surface px-3 text-sm">
                <option value="" disabled>Select…</option>
                <option v-for="m in modesOfPayment" :key="m.name" :value="m.name">{{ m.name }}</option>
              </select>
            </div>

            <p v-if="differentReferencesUsed" class="text-xs text-ink-3">
              Different references were used - this will create {{ referenceGroupCount }} separate payment entries.
            </p>
          </div>

          <p v-if="submitError" class="text-xs text-crit text-center">{{ submitError }}</p>

          <button
            type="button"
            class="w-full h-[48px] rounded-xl bg-accent text-accent-fg font-display font-semibold text-sm disabled:opacity-50"
            :disabled="submitting || !canSubmit"
            @click="submit"
          >
            {{ submitting ? "Recording…" : `Record collection · ${formatCurrency(selectedTotal)}` }}
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
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

// One entry per selected invoice: invoiceAmounts[name] = amount to collect
// against it. Absence of a key means the invoice isn't selected - the
// checkbox state and the per-row amount field share this single source of
// truth instead of a separate selected-map.
const invoiceAmounts = ref({})
// Per-invoice reference (cheque/UTR number) - a rep collecting against
// several invoices in one visit may have a different one for each. Kept
// separate from invoiceAmounts since an invoice can be selected with no
// reference yet typed (only required once a non-cash mode is picked).
const invoiceReferences = ref({})

const modeOfPayment = ref("")
const modesOfPayment = ref([])
const submitting = ref(false)
const submitError = ref("")

const today = new Date().toISOString().slice(0, 10)

function isOverdue(inv) {
  return inv.due_date && inv.due_date < today
}

function isSelected(inv) {
  return Object.prototype.hasOwnProperty.call(invoiceAmounts.value, inv.name)
}

function invoiceAmountError(inv) {
  const value = invoiceAmounts.value[inv.name]
  if (value === "" || value === null || value === undefined) return "Enter an amount."
  if (Number(value) <= 0) return "Enter an amount greater than zero."
  if (Number(value) > Number(inv.outstanding_amount) + 0.01) return "Can't exceed this invoice's outstanding amount."
  return ""
}

function invoiceReferenceError(inv) {
  if (referenceRequired.value && !(invoiceReferences.value[inv.name] || "").trim()) {
    return "Enter a reference number."
  }
  return ""
}

const selectedTotal = computed(() =>
  Object.values(invoiceAmounts.value).reduce((sum, v) => sum + (Number(v) || 0), 0)
)

const referenceRequired = computed(() => {
  const mode = modesOfPayment.value.find((m) => m.name === modeOfPayment.value)
  return !!mode && mode.type !== "Cash"
})

const usedReferences = computed(() => {
  const set = new Set()
  for (const inv of ledger.value.invoices) {
    if (!isSelected(inv)) continue
    set.add((invoiceReferences.value[inv.name] || "").trim())
  }
  return set
})

const referenceGroupCount = computed(() => usedReferences.value.size)
const differentReferencesUsed = computed(() => referenceGroupCount.value > 1)

const canSubmit = computed(() =>
  ledger.value.invoices.some(isSelected) &&
  ledger.value.invoices.every(
    (inv) => !isSelected(inv) || (!invoiceAmountError(inv) && !invoiceReferenceError(inv))
  ) &&
  selectedTotal.value > 0 &&
  !!modeOfPayment.value
)

function toggleInvoice(inv) {
  if (isSelected(inv)) {
    const nextAmounts = { ...invoiceAmounts.value }
    const nextRefs = { ...invoiceReferences.value }
    delete nextAmounts[inv.name]
    delete nextRefs[inv.name]
    invoiceAmounts.value = nextAmounts
    invoiceReferences.value = nextRefs
  } else {
    invoiceAmounts.value = { ...invoiceAmounts.value, [inv.name]: Number(inv.outstanding_amount) }
    invoiceReferences.value = { ...invoiceReferences.value, [inv.name]: "" }
  }
}

const allSelected = computed(
  () => ledger.value.invoices.length > 0 && ledger.value.invoices.every(isSelected)
)

function toggleAll() {
  if (allSelected.value) {
    invoiceAmounts.value = {}
    invoiceReferences.value = {}
  } else {
    const nextAmounts = {}
    const nextRefs = {}
    for (const inv of ledger.value.invoices) {
      nextAmounts[inv.name] = Number(inv.outstanding_amount)
      nextRefs[inv.name] = invoiceReferences.value[inv.name] || ""
    }
    invoiceAmounts.value = nextAmounts
    invoiceReferences.value = nextRefs
  }
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
    const nextAmounts = {}
    const nextRefs = {}
    for (const inv of ledgerData.invoices) {
      nextAmounts[inv.name] = Number(inv.outstanding_amount)
      nextRefs[inv.name] = ""
    }
    invoiceAmounts.value = nextAmounts
    invoiceReferences.value = nextRefs
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
    const references = {}
    for (const [name, ref] of Object.entries(invoiceReferences.value)) {
      if (Object.prototype.hasOwnProperty.call(invoiceAmounts.value, name) && ref && ref.trim()) {
        references[name] = ref.trim()
      }
    }
    await call("field_sales.api.customers.record_collection", {
      customer,
      invoice_amounts: invoiceAmounts.value,
      invoice_references: references,
      mode_of_payment: modeOfPayment.value,
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

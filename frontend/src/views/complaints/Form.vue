<template>
  <FormView
    title="Raise a complaint"
    fallback="/complaints"
    :steps="steps"
    :initial-data="initialData"
    submit-label="Submit complaint"
    :on-submit="raiseComplaint"
    @saved="onSaved"
  >
    <template #step-0="{ data, errors }">
      <div class="bg-surface rounded-2xl p-4 space-y-4">
        <div>
          <CustomerPicker
            label="Customer *"
            :multiple="false"
            :model-value="data.customer"
            @update:model-value="onCustomerPicked(data, $event)"
          />
          <p v-if="errors.customer" class="text-xs text-crit mt-1">{{ errors.customer }}</p>
        </div>

        <div>
          <!-- Mirrors the Flutter form's Transit/Quality radio, extended with
               the richer Service/Other options this app's own fs_claim_type
               already supports server side (see field_sales.api.complaints,
               which maps Transit/Quality onto Issue's legacy claim_type). -->
          <label class="block text-sm font-display text-ink-2 mb-1">Claim Type <span class="text-crit">*</span></label>
          <select v-model="data.fs_claim_type" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm">
            <option value="Transit">Transit</option>
            <option value="Quality">Quality</option>
            <option value="Service">Service</option>
            <option value="Other">Other</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Priority</label>
          <select v-model="data.priority" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm">
            <option value="Low">Low</option>
            <option value="Medium">Medium</option>
            <option value="High">High</option>
            <option value="Urgent">Urgent</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Invoice no (optional)</label>

          <div v-if="data.fs_sales_invoice" class="flex items-center justify-between rounded-xl border border-rule bg-surface px-3 py-2 text-sm">
            <span>{{ invoiceLabel(data.fs_sales_invoice) }}</span>
            <button type="button" class="text-xs text-accent-ink font-display font-medium" @click="onInvoiceChanged(data, '')">Change</button>
          </div>
          <p v-if="data.fs_sales_invoice" class="text-xs text-ink-3 mt-1">
            Claimed items below are pre-filled from this invoice - review, adjust quantities, or remove any that don't apply.
          </p>
          <div v-else-if="!data.customer" class="rounded-xl border border-dashed border-rule bg-ground px-3 py-2 text-sm text-ink-3">
            Select a customer first.
          </div>
          <!-- customerInvoices is already fully loaded per customer (loadCustomerInvoices,
               below) - a customer's invoice history isn't large enough server-side pagination
               makes sense for, so this filters the loaded list client-side rather than
               debouncing a new API call per keystroke like CustomerPicker/ItemPicker do. -->
          <div v-else class="relative">
            <input
              v-model="invoiceQuery"
              type="text"
              placeholder="Search invoice no…"
              class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
            />
            <div v-if="filteredInvoices.length" class="absolute z-10 mt-1 w-full max-h-48 overflow-y-auto rounded-xl border border-rule bg-surface shadow-lg">
              <button
                v-for="inv in filteredInvoices"
                :key="inv.name"
                type="button"
                class="block w-full text-left px-3 py-2 text-sm hover:bg-ground"
                @click="pickInvoice(data, inv)"
              >
                {{ inv.name }} · {{ inv.posting_date }}
              </button>
            </div>
            <p v-else-if="!customerInvoices.length" class="text-xs text-ink-3 mt-1">No invoices on file for this customer.</p>
          </div>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Subject <span class="text-crit">*</span></label>
          <input
            v-model="data.subject"
            class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
            :class="errors.subject ? 'border-crit' : ''"
          />
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Description <span class="text-crit">*</span></label>
          <textarea
            v-model="data.description"
            rows="3"
            class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
            :class="errors.description ? 'border-crit' : ''"
          />
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Photo (optional)</label>
          <FileUpload
            v-model="data.fs_photo"
            doctype="Issue"
            label="Photograph the affected goods"
            @uploading-change="photoUploading = $event"
          />
        </div>
      </div>
    </template>

    <!-- Reason for complaint: multi-select with a remark per selected
         reason - mirrors the Flutter form's checkbox list + per-row
         "Remarks" field (add_complaint_screen.dart). The reason values
         themselves come from the legacy Reason master's for_complaints=1
         rows, not invented. -->
    <template #step-1="{ data }">
      <div class="bg-surface rounded-2xl p-4 space-y-3">
        <label class="block text-sm font-display text-ink-2 mb-1">Reason for complaint <span class="text-crit">*</span></label>
        <label
          v-for="reason in reasonOptions"
          :key="reason"
          class="flex items-center gap-2 text-sm py-1"
        >
          <input
            type="checkbox"
            :checked="isReasonSelected(data, reason)"
            @change="toggleReason(data, reason)"
          />
          {{ reason }}
        </label>

        <div v-for="row in data.fs_complaint_reasons" :key="row.reason" class="bg-surface-2 rounded-xl p-3 space-y-1">
          <p class="text-sm font-display font-medium text-ink">{{ row.reason }}</p>
          <input
            v-model="row.remarks"
            class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
            placeholder="Remarks (optional)"
          />
        </div>
      </div>
    </template>

    <!-- Per-item claim table: item, qty, value of goods, batch no, MFD,
         expiry - mirrors the Flutter form's item claim rows. -->
    <template #step-2="{ data }">
      <div class="space-y-3">
        <div v-for="(row, i) in data.fs_complaint_items" :key="i" class="bg-surface rounded-2xl border border-rule p-4 space-y-3">
          <div class="flex items-center justify-between pb-1 border-b border-rule-soft">
            <span class="inline-flex items-center gap-2 text-sm font-display font-semibold text-ink">
              <span class="w-6 h-6 rounded-full bg-accent-soft text-accent-ink text-xs font-bold flex items-center justify-center shrink-0">{{ i + 1 }}</span>
              Claimed item
            </span>
            <button
              type="button"
              class="w-8 h-8 rounded-full flex items-center justify-center text-ink-3 active:bg-surface-2"
              aria-label="Remove claimed item"
              @click="data.fs_complaint_items.splice(i, 1)"
            >
              <Icon name="close" :size="14" />
            </button>
          </div>
          <div class="space-y-2">
              <ItemPicker
                label="Item"
                :model-value="row.item_code"
                :display="row.item_code ? (row.item_name || row.item_code) : ''"
                @update:model-value="row.item_code = $event"
                @picked="(item) => { row.item_code = item?.item_code || ''; row.item_name = item?.item_name || '' }"
              />
              <div class="flex gap-2">
                <input
                  v-model.number="row.qty"
                  type="number"
                  min="0"
                  step="0.01"
                  class="w-1/2 rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
                  placeholder="Qty"
                />
                <input
                  v-model.number="row.value_of_goods"
                  type="number"
                  min="0"
                  step="0.01"
                  class="w-1/2 rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
                  placeholder="Value of goods"
                />
              </div>
              <input
                v-model="row.batch_no"
                class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
                placeholder="Batch no."
              />
              <div class="flex gap-2">
                <div class="w-1/2">
                  <label class="block text-xs text-ink-3 mb-1">MFD</label>
                  <input v-model="row.mfd" type="date" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm" />
                </div>
                <div class="w-1/2">
                  <label class="block text-xs text-ink-3 mb-1">Expiry</label>
                  <input v-model="row.expiry_date" type="date" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm" />
                </div>
              </div>
          </div>
        </div>

        <button
          type="button"
          class="w-full py-2.5 rounded-xl border border-dashed border-rule text-sm font-display text-ink-2"
          @click="data.fs_complaint_items.push({ item_code: '', item_name: '', qty: 1, value_of_goods: 0, batch_no: '', mfd: '', expiry_date: '' })"
        >
          + Add claimed item
        </button>
      </div>
    </template>
  </FormView>
</template>

<script setup>
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"
import FormView from "@/components/FormView.vue"
import FileUpload from "@/components/FileUpload.vue"
import CustomerPicker from "@/components/CustomerPicker.vue"
import ItemPicker from "@/components/ItemPicker.vue"
import Icon from "@/components/Icon.vue"
import { queueWrite } from "@/composables/offlineQueue"

const router = useRouter()
const photoUploading = ref(false)

const initialData = {
  subject: "",
  customer: "",
  priority: "Medium",
  fs_claim_type: "Quality",
  fs_sales_invoice: "",
  description: "",
  fs_photo: "",
  fs_complaint_reasons: [],
  fs_complaint_items: [],
}

// The real reason list, sourced from the legacy Reason master's
// for_complaints=1 rows (mohan_impex, shared site) rather than invented -
// see field_sales/field_sales/doctype/complaint_reason for the child
// doctype this feeds.
const reasonOptions = ["Damaged in transit", "Product quality issue"]

const customerInvoices = ref([])
const invoiceQuery = ref("")

const filteredInvoices = computed(() => {
  const text = invoiceQuery.value.trim().toLowerCase()
  if (!text) return customerInvoices.value
  return customerInvoices.value.filter((inv) => inv.name.toLowerCase().includes(text))
})

function invoiceLabel(name) {
  const inv = customerInvoices.value.find((i) => i.name === name)
  return inv ? `${inv.name} · ${inv.posting_date}` : name
}

async function pickInvoice(data, inv) {
  data.fs_sales_invoice = inv.name
  invoiceQuery.value = ""
  try {
    const rows = await call("field_sales.api.customers.invoice_items", { invoice: inv.name })
    data.fs_complaint_items = (rows || []).map((r) => ({
      item_code: r.item_code, item_name: r.item_name, qty: r.qty || 1,
      value_of_goods: r.amount || 0, batch_no: r.batch_no || "", mfd: "", expiry_date: "",
    }))
  } catch {
    // The invoice link itself already saved; the rep can still add claimed
    // items manually on the next step if this best-effort prefill fails.
  }
}

// Switching (or clearing) the invoice drops any items that were prefilled
// from the previous one - stale rows from a different invoice would
// otherwise linger and read as claimed against the wrong bill.
function onInvoiceChanged(data, invoiceName) {
  data.fs_sales_invoice = invoiceName
  data.fs_complaint_items = []
}

function onCustomerPicked(data, customerName) {
  data.customer = customerName
  loadCustomerInvoices(data)
}

function isReasonSelected(data, reason) {
  return (data.fs_complaint_reasons || []).some((r) => r.reason === reason)
}

function toggleReason(data, reason) {
  const existing = data.fs_complaint_reasons.find((r) => r.reason === reason)
  if (existing) {
    data.fs_complaint_reasons.splice(data.fs_complaint_reasons.indexOf(existing), 1)
  } else {
    data.fs_complaint_reasons.push({ reason, remarks: "" })
  }
}

async function loadCustomerInvoices(data) {
  data.fs_sales_invoice = ""
  customerInvoices.value = []
  invoiceQuery.value = ""
  if (!data.customer) return
  try {
    const ledger = await call("field_sales.api.customers.customer_ledger", { customer: data.customer })
    customerInvoices.value = ledger?.invoices || []
  } catch {
    customerInvoices.value = []
  }
}

const steps = [
  {
    title: "Details",
    fields: [
      { key: "customer", required: true },
      { key: "subject", required: true },
      { key: "description", required: true },
    ],
  },
  {
    title: "Reason for complaint",
    fields: [],
    validate: (d) => {
      if (!(d.fs_complaint_reasons || []).length) return "Select at least one reason for the complaint."
      return ""
    },
  },
  {
    title: "Claimed items",
    fields: [],
    validate: () => {
      if (photoUploading.value) return "The photo is still uploading - wait a moment before submitting."
      return ""
    },
  },
]

async function raiseComplaint(data) {
  const args = {
    ...data,
    fs_sales_invoice: data.fs_sales_invoice || undefined,
    fs_complaint_reasons: (data.fs_complaint_reasons || []).filter((r) => r.reason),
    fs_complaint_items: (data.fs_complaint_items || []).filter((r) => r.item_code),
  }
  return queueWrite({
    method: "field_sales.api.complaints.raise_complaint",
    args,
    label: "New complaint",
  })
}

function onSaved(result) {
  if (result?.name) router.push({ name: "ComplaintDetail", params: { name: result.name } })
  else router.push({ name: "ComplaintList" })
}
</script>

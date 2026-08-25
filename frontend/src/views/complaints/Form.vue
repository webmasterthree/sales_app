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
          <label class="block text-sm font-display text-ink-2 mb-1">Customer <span class="text-crit">*</span></label>
          <select
            v-model="data.customer"
            class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
            :class="errors.customer ? 'border-crit' : ''"
            @change="loadCustomerInvoices(data)"
          >
            <option value="">Select customer</option>
            <option v-for="customer in customers" :key="customer.name" :value="customer.name">
              {{ customer.customer_name || customer.name }}
            </option>
          </select>
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
          <select
            v-model="data.fs_sales_invoice"
            class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
            :disabled="!data.customer"
          >
            <option value="">{{ data.customer ? "Not linked to an invoice" : "Select a customer first" }}</option>
            <option v-for="inv in customerInvoices" :key="inv.name" :value="inv.name">
              {{ inv.name }} · {{ inv.posting_date }}
            </option>
          </select>
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
          <FileUpload v-model="data.fs_photo" doctype="Issue" label="Photograph the affected goods" />
        </div>
      </div>
    </template>
  </FormView>
</template>

<script setup>
import { onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"
import FormView from "@/components/FormView.vue"
import FileUpload from "@/components/FileUpload.vue"
import { queueWrite } from "@/composables/offlineQueue"

const router = useRouter()

const initialData = {
  subject: "",
  customer: "",
  priority: "Medium",
  fs_claim_type: "Quality",
  fs_sales_invoice: "",
  description: "",
  fs_photo: "",
}

const customers = ref([])
const customerInvoices = ref([])

onMounted(async () => {
  try {
    const customerPage = await call("field_sales.api.customers.customer_list", { limit: 500, current_page: 1, disabled: 0 })
    customers.value = customerPage?.records || []
  } catch {
    customers.value = []
  }
})

// Reason for complaint (multi-select with per-reason remarks) and the
// per-item claim table (item, qty, value of goods, batch no, MFD, expiry)
// that the Flutter form collects have no home on the server yet - Issue's
// WRITABLE allow-list (field_sales/api/complaints.py) only takes subject,
// description, customer, priority, fs_claim_type, fs_field_visit and
// fs_sales_invoice. Adding that structured data would mean new child
// doctypes on Issue, which is a bigger call than this pass should make
// unilaterally - flagged in the audit report rather than improvised here.
// Photo/video attachment is in the same position: FormView has no upload
// field type anywhere in this app yet, so it isn't a complaints-only gap.
async function loadCustomerInvoices(data) {
  data.fs_sales_invoice = ""
  customerInvoices.value = []
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
]

async function raiseComplaint(data) {
  return queueWrite({
    method: "field_sales.api.complaints.raise_complaint",
    args: { ...data, fs_sales_invoice: data.fs_sales_invoice || undefined },
    label: "New complaint",
  })
}

function onSaved(result) {
  if (result?.name) router.push({ name: "ComplaintDetail", params: { name: result.name } })
  else router.push({ name: "ComplaintList" })
}
</script>

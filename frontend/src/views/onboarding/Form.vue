<template>
  <FormView
    title="New customer KYC"
    fallback="/onboarding"
    :steps="steps"
    :initial-data="initialData"
    allow-draft
    submit-label="Submit for approval"
    :on-submit="submit"
    @saved="onSaved"
  >
    <!-- Documents - GST certificate, PAN, licenses etc., each with its own
         photo/scan. Mirrors Flutter's declaration/license capture; the
         backend's `documents` child table already had document_type,
         attachment, number, remarks fields with no UI ever populating them. -->
    <template #step-3="{ data }">
      <div class="space-y-3">
        <div v-for="(row, i) in data.documents" :key="i" class="bg-surface rounded-2xl p-4 space-y-3">
          <div class="flex items-start justify-between gap-2">
            <select v-model="row.document_type" class="flex-1 rounded-xl border border-rule bg-surface px-3 py-2 text-sm">
              <option value="">Select document type</option>
              <option v-for="opt in documentTypes" :key="opt" :value="opt">{{ opt }}</option>
            </select>
            <button type="button" class="text-crit text-sm font-display px-2 py-1 shrink-0" @click="data.documents.splice(i, 1)">
              Remove
            </button>
          </div>
          <input
            v-model="row.number"
            class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
            placeholder="Document number (optional)"
          />
          <FileUpload
            v-model="row.attachment"
            doctype="Customer Onboarding"
            accept="image/*,.pdf"
            label="Photograph or scan the document"
            @uploading-change="uploadingByIndex[i] = $event"
          />
        </div>

        <button
          type="button"
          class="w-full py-2.5 rounded-xl border border-dashed border-rule text-sm font-display text-ink-2"
          @click="data.documents.push({ document_type: '', attachment: '', number: '', remarks: '' })"
        >
          + Add document
        </button>
      </div>
    </template>
  </FormView>
</template>

<script setup>
import { reactive } from "vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"
import FormView from "@/components/FormView.vue"
import FileUpload from "@/components/FileUpload.vue"
import { queueWrite } from "@/composables/offlineQueue"

const documentTypes = ["GST Certificate", "PAN Card", "Shop License", "FSSAI Registration", "Trade License", "Bank Proof", "Other"]

const router = useRouter()

// Keyed by document row index - the "Documents" step can submit is only
// safe once every row's own upload (if any) has actually finished. See
// FileUpload.vue's uploading-change comment for why this matters.
const uploadingByIndex = reactive({})

const initialData = {
  customer_name: "",
  business_type: "Registered",
  gst_category: "",
  gstin: "",
  pan: "",
  market_segment: "",
  customer_group: "",
  location: "",
  address_line1: "",
  address_line2: "",
  city: "",
  district: "",
  state: "",
  pincode: "",
  contact_person: "",
  contact_number: "",
  territory: "",
  proposed_credit: "Advance",
  credit_days: "",
  credit_limit: "",
  documents: [],
}

const steps = [
  {
    title: "Business",
    fields: [
      { key: "customer_name", label: "Customer / business name", type: "text", required: true },
      { key: "business_type", label: "Business type", type: "select", options: ["Registered", "Unregistered"], required: true },
      { key: "gst_category", label: "GST category", type: "select", options: [
        "Registered Regular", "Registered Composition", "Unregistered", "SEZ", "Overseas", "Deemed Export", "UIN Holders", "Composition",
      ] },
      { key: "gstin", label: "GSTIN", type: "text" },
      { key: "pan", label: "PAN", type: "text" },
      { key: "market_segment", label: "Market segment", type: "text" },
      { key: "customer_group", label: "Customer group", type: "text" },
    ],
  },
  {
    title: "Address & contact",
    fields: [
      { key: "location", label: "Existing address (Address record name, optional)", type: "text" },
      { key: "address_line1", label: "Address line 1 (required unless an existing address is picked above)", type: "text" },
      { key: "address_line2", label: "Address line 2", type: "text" },
      { key: "city", label: "City (required unless an existing address is picked above)", type: "text" },
      { key: "district", label: "District", type: "text" },
      { key: "state", label: "State (required unless an existing address is picked above)", type: "text" },
      { key: "pincode", label: "Pincode (required unless an existing address is picked above)", type: "text" },
      { key: "contact_person", label: "Contact person", type: "text" },
      { key: "contact_number", label: "Contact number", type: "text", required: true },
      { key: "territory", label: "Territory", type: "text", required: true },
    ],
    validate: (d) => {
      if (d.location) return ""
      if (!(d.address_line1 && d.city && d.state && d.pincode)) {
        return "Give the outlet's address: either pick an existing Address, or fill in address line 1, city, state and pincode."
      }
      return ""
    },
  },
  {
    title: "Credit terms",
    fields: [
      { key: "proposed_credit", label: "Proposed terms", type: "select", options: ["Advance", "Credit"] },
      { key: "credit_days", label: "Credit days", type: "number" },
      { key: "credit_limit", label: "Credit limit", type: "number" },
    ],
  },
  {
    title: "Documents",
    fields: [],
    validate: () => {
      if (Object.values(uploadingByIndex).some(Boolean)) {
        return "A document photo is still uploading - wait a moment before submitting."
      }
      return ""
    },
  },
]

async function submit(data, mode) {
  const args = { ...data, documents: (data.documents || []).filter((r) => r.document_type || r.attachment) }
  const created = await queueWrite({
    method: "field_sales.api.onboarding.create_onboarding",
    args,
    label: "New onboarding request",
  })
  if (mode === "submit" && !created.queued && created?.name) {
    await call("field_sales.api.onboarding.submit_onboarding", { name: created.name })
  }
  return created
}

function onSaved(result) {
  if (result?.name) router.push({ name: "OnboardingDetail", params: { name: result.name } })
  else router.push({ name: "OnboardingList" })
}
</script>

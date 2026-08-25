<template>
  <DetailView :name="name" :config="config">
    <template #extra="{ doc }">
      <details v-if="doc.documents?.length" class="bg-surface rounded-2xl border border-rule overflow-hidden">
        <summary class="px-4 py-3 font-display font-semibold cursor-pointer select-none">Documents</summary>
        <div class="px-4 pb-4 space-y-3">
          <div v-for="row in doc.documents" :key="row.name" class="space-y-1">
            <p class="text-sm font-display font-medium text-ink">{{ row.document_type }}<span v-if="row.number" class="text-ink-2 font-normal"> · {{ row.number }}</span></p>
            <a v-if="row.attachment" :href="row.attachment" target="_blank" rel="noopener" class="block">
              <img :src="row.attachment" class="w-full max-h-40 object-cover rounded-xl border border-rule" :alt="row.document_type" />
            </a>
          </div>
        </div>
      </details>
    </template>
  </DetailView>
</template>

<script setup>
import DetailView from "@/components/DetailView.vue"

defineProps({ name: { type: String, required: true } })

const config = {
  title: (doc) => doc?.customer_name || doc?.name || "Onboarding",
  method: "field_sales.api.onboarding.onboarding",
  fallback: "/onboarding",
  statusField: "status",
  sections: [
    {
      title: "Business details",
      fields: [
        { key: "business_type", label: "Business type" },
        { key: "gst_category", label: "GST category" },
        { key: "gstin", label: "GSTIN" },
        { key: "pan", label: "PAN" },
        { key: "market_segment", label: "Market segment" },
        { key: "customer_group", label: "Customer group" },
      ],
    },
    {
      title: "Contact & territory",
      fields: [
        { key: "location", label: "Address" },
        { key: "contact_person", label: "Contact person" },
        { key: "contact_number", label: "Contact number" },
        { key: "territory", label: "Territory" },
        { key: "sales_person_name", label: "Filed by" },
      ],
    },
    {
      title: "Credit terms",
      fields: [
        { key: "proposed_credit", label: "Proposed terms" },
        { key: "credit_days", label: "Credit days" },
        { key: "credit_limit", label: "Credit limit" },
      ],
    },
    {
      title: "Decision",
      fields: [
        { key: "decided_on", label: "Decided on" },
        { key: "decision_remarks", label: "Remarks" },
        { key: "customer", label: "Linked customer" },
      ],
    },
  ],
  actions: [
    {
      label: "Submit for approval",
      visible: (doc) => doc.docstatus === 0,
      confirm: "Submit this onboarding request for approval?",
      method: "field_sales.api.onboarding.submit_onboarding",
    },
    {
      label: "Approve",
      visible: (doc) => doc.docstatus === 1 && doc.status === "Pending",
      confirm: "Approve this onboarding request? A customer record will be created.",
      method: "field_sales.field_sales.doctype.customer_onboarding.customer_onboarding.approve_onboarding",
    },
    {
      label: "Reject",
      tone: "crit",
      visible: (doc) => doc.docstatus === 1 && doc.status === "Pending",
      handler: async (doc, reload) => {
        const remarks = window.prompt("Reason for rejecting this request:")
        if (!remarks) return
        const { call } = await import("frappe-ui")
        await call("field_sales.field_sales.doctype.customer_onboarding.customer_onboarding.reject_onboarding", {
          name: doc.name, remarks,
        })
        await reload()
      },
    },
  ],
}
</script>

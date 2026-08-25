<template>
  <DetailView :name="name" :config="config">
    <template #extra="{ doc }">
      <div v-if="doc.fs_photo" class="rounded-2xl overflow-hidden border border-rule">
        <img :src="doc.fs_photo" alt="Complaint photo" class="w-full h-48 object-cover block" />
      </div>
    </template>
  </DetailView>
</template>

<script setup>
import DetailView from "@/components/DetailView.vue"

defineProps({ name: { type: String, required: true } })

const config = {
  title: (doc) => doc?.subject || doc?.name || "Complaint",
  method: "field_sales.api.complaints.complaint",
  fallback: "/complaints",
  statusField: "status",
  sections: [
    {
      title: "Summary",
      fields: [
        { key: "customer", label: "Customer" },
        { key: "priority", label: "Priority" },
        { key: "opening_date", label: "Opened" },
        { key: "fs_claim_type", label: "Claim type" },
        { key: "fs_sales_invoice", label: "Invoice no" },
        { key: "description", label: "Description" },
      ],
    },
    {
      title: "Resolution",
      fields: [
        { key: "fs_resolved_on", label: "Resolved on" },
        { key: "resolution_details", label: "Resolution notes" },
      ],
    },
  ],
  actions: [
    {
      label: "Mark resolved",
      confirm: "Mark this complaint resolved?",
      visible: (doc) => !["Resolved", "Closed"].includes(doc.status),
      method: "field_sales.api.complaints.resolve_complaint",
    },
  ],
}
</script>

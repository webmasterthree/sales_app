<template>
  <DetailView :name="name" :config="config">
    <template #extra="{ doc }">
      <div v-if="doc.fs_photo" class="rounded-2xl overflow-hidden border border-rule">
        <img :src="doc.fs_photo" alt="Complaint photo" class="w-full h-48 object-cover block" />
      </div>

      <div v-if="doc.fs_complaint_reasons?.length" class="bg-surface rounded-2xl border border-rule p-4 space-y-3">
        <p class="text-sm font-display font-semibold text-ink">Reason for complaint</p>
        <div
          v-for="(row, i) in doc.fs_complaint_reasons"
          :key="row.name"
          class="text-sm pb-2 border-b border-rule-soft last:border-0 last:pb-0"
        >
          <p class="inline-flex items-center gap-2 font-display font-medium text-ink">
            <span class="w-5 h-5 rounded-full bg-accent-soft text-accent-ink text-[11px] font-bold flex items-center justify-center shrink-0">{{ i + 1 }}</span>
            {{ row.reason }}
          </p>
          <p v-if="row.remarks" class="text-ink-2 mt-0.5 ml-7">{{ row.remarks }}</p>
        </div>
      </div>

      <div v-if="doc.fs_complaint_items?.length" class="bg-surface rounded-2xl border border-rule p-4 space-y-3">
        <p class="text-sm font-display font-semibold text-ink">Claimed items</p>
        <div
          v-for="(row, i) in doc.fs_complaint_items"
          :key="row.name"
          class="text-sm pb-2 border-b border-rule-soft last:border-0 last:pb-0"
        >
          <div class="flex justify-between items-start gap-2">
            <span class="inline-flex items-center gap-2 font-display font-medium text-ink">
              <span class="w-5 h-5 rounded-full bg-accent-soft text-accent-ink text-[11px] font-bold flex items-center justify-center shrink-0">{{ i + 1 }}</span>
              {{ row.item_name || row.item_code }} × {{ row.qty }}
            </span>
            <span class="text-ink-2 font-display font-medium shrink-0">₹{{ row.value_of_goods }}</span>
          </div>
          <p class="text-xs text-ink-3 mt-0.5 ml-7">
            Batch {{ row.batch_no || "—" }} · MFD {{ row.mfd || "—" }} · Expiry {{ row.expiry_date || "—" }}
          </p>
        </div>
      </div>

      <CommentThread doctype="Issue" :docname="doc.name" />
    </template>
  </DetailView>
</template>

<script setup>
import DetailView from "@/components/DetailView.vue"
import CommentThread from "@/components/CommentThread.vue"

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
        { key: "priority", label: "Priority", pill: true },
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

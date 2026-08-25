<template>
  <DetailView :name="name" :config="config">
    <template #extra="{ doc }">
      <div v-if="doc.items?.length" class="bg-surface rounded-2xl border border-rule p-4 space-y-2">
        <p class="font-display font-semibold text-sm">Items</p>
        <div v-for="row in doc.items" :key="row.name" class="flex justify-between text-sm">
          <span class="text-ink-2">{{ row.description || row.collateral }}</span>
          <span class="font-display">{{ row.qty }}</span>
        </div>
      </div>
      <div v-if="doc.purpose" class="bg-surface rounded-2xl border border-rule p-4">
        <p class="text-xs text-ink-2 mb-1">Remarks</p>
        <p class="text-sm">{{ doc.purpose }}</p>
      </div>
    </template>
  </DetailView>
</template>

<script setup>
import DetailView from "@/components/DetailView.vue"

defineProps({ name: { type: String, required: true } })

const config = {
  title: (doc) => doc?.customer_name || doc?.prospect_name || doc?.name || "Collateral Request",
  method: "field_sales.api.requests.collateral_request",
  fallback: "/requisitions/collateral",
  statusField: "status",
  sections: [
    {
      title: "Request",
      fields: [
        { key: "customer_name", label: "Customer" },
        { key: "prospect_name", label: "Prospect" },
        { key: "sales_person_name", label: "Requested by" },
        { key: "territory", label: "Territory" },
        { key: "request_date", label: "Request date" },
        { key: "required_by", label: "Required by" },
        { key: "field_visit", label: "Linked visit" },
      ],
    },
  ],
}
</script>

<template>
  <ListView :config="config" />
</template>

<script setup>
import ListView from "@/components/ListView.vue"

const config = {
  title: "Trial Plan",
  fallback: "/",
  method: "field_sales.api.trial_plan.trial_plan_list",
  searchable: true,
  mineToggle: true,
  mineLabel: "trials",
  statusField: "status",
  tabs: [
    { key: "scheduled", label: "Scheduled" },
    { key: "completed", label: "Completed" },
  ],
  defaultTab: "scheduled",
  filters: [
    { key: "visit_type", label: "Customer Type", options: ["Primary", "Secondary"] },
  ],
  cardTitle: (row) => row.item_name || row.name,
  cardSubtitle: (row) => [row.customer_name, row.delivery_date].filter(Boolean).join(" · "),
  cardMeta: (row) => (row.sales_person_name ? `Rep: ${row.sales_person_name}` : ""),
  createRouteName: "TrialPlanNew",
  detailRouteName: "TrialPlanDetail",
  emptyIcon: "sample",
  emptyTitle: "No trial plans yet",
  emptyDescription: "Start your first product trial with the + button.",
}
</script>

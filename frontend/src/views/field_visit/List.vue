<template>
  <ListView :config="config" />
</template>

<script setup>
import ListView from "@/components/ListView.vue"

const config = {
  title: "Customer Visits",
  method: "field_sales.api.field_visit.visit_list",
  searchable: true,
  mineToggle: true,
  mineLabel: "visits",
  statusField: "order_status",
  tabs: [
    { key: "draft", label: "Draft" },
    { key: "submitted", label: "Submitted" },
  ],
  defaultTab: "draft",
  filters: [
    { key: "party_type", label: "Party", options: ["Customer", "Prospect"] },
    { key: "order_status", label: "Outcome", options: ["With Order", "Without Order"] },
  ],
  cardTitle: (row) => row.customer_name || row.prospect_name || row.outlet_name || row.name,
  cardSubtitle: (row) => [row.visit_date, row.city].filter(Boolean).join(" · "),
  cardMeta: (row) => (row.sales_person_name ? `Rep: ${row.sales_person_name}` : ""),
  createRouteName: "VisitNew",
  detailRouteName: "VisitDetail",
  emptyIcon: "visit",
  emptyTitle: "No visits yet",
  emptyDescription: "Start your first customer visit with the + button.",
}
</script>

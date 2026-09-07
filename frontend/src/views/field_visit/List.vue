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
    { key: "submitted", label: "Submitted" },
    { key: "draft", label: "Draft" },
  ],
  // Unlike the other modules' tabs (open/pending - ongoing work that stays
  // visible), "Draft" here empties out as soon as a rep submits, which is
  // normally within the same session. Defaulting to it made a visit a rep
  // had already filed and submitted look like it hadn't saved at all.
  defaultTab: "submitted",
  filters: [
    { key: "party_type", label: "Party", options: ["Customer", "Prospect"] },
    { key: "order_status", label: "Outcome", options: ["With Order", "Without Order"] },
  ],
  cardImage: (row) => row.shop_photo,
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

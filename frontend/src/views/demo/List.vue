<template>
  <ListView :config="config" />
</template>

<script setup>
import ListView from "@/components/ListView.vue"

const config = {
  title: "Product Demos",
  method: "field_sales.api.demo.demo_list",
  searchable: true,
  mineToggle: true,
  mineLabel: "demos",
  statusField: "status",
  tabs: [
    { key: "pending", label: "Pending" },
    { key: "approved", label: "Approved" },
    { key: "completed", label: "Completed" },
    { key: "rejected", label: "Rejected" },
  ],
  defaultTab: "pending",
  cardTitle: (row) => row.customer_name || row.prospect_name || row.outlet_name || row.name,
  cardSubtitle: (row) => row.demo_date || "",
  fallback: "/requisitions",
  createRouteName: "DemoNew",
  detailRouteName: "DemoDetail",
  emptyIcon: "demo",
  emptyTitle: "No product demos",
  emptyDescription: "Nothing has been scheduled yet.",
}
</script>

<template>
  <ListView :config="config" />
</template>

<script setup>
import ListView from "@/components/ListView.vue"

const config = {
  title: "Sample Requests",
  method: "field_sales.api.requests.sample_request_list",
  searchable: true,
  mineToggle: true,
  mineLabel: "requests",
  statusField: "status",
  tabs: [
    { key: "pending", label: "Pending" },
    { key: "approved", label: "Approved" },
    { key: "rejected", label: "Rejected" },
  ],
  defaultTab: "pending",
  cardTitle: (row) => row.customer_name || row.prospect_name || row.name,
  cardSubtitle: (row) => row.request_date || "",
  fallback: "/requisitions",
  createRouteName: "SampleRequestNew",
  detailRouteName: "SampleRequestDetail",
  emptyIcon: "sample",
  emptyTitle: "No sample requests",
  emptyDescription: "Nothing has been requested yet.",
}
</script>

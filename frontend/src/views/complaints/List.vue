<template>
  <ListView :config="config" />
</template>

<script setup>
import ListView from "@/components/ListView.vue"

const config = {
  title: "Complaints & Claims",
  method: "field_sales.api.complaints.complaint_list",
  searchable: true,
  mineToggle: true,
  mineLabel: "complaints",
  statusField: "status",
  tabs: [
    { key: "open", label: "Open" },
    { key: "resolved", label: "Resolved" },
  ],
  defaultTab: "open",
  filters: [
    { key: "priority", label: "Priority", options: ["Low", "Medium", "High", "Urgent"] },
  ],
  cardTitle: (row) => row.subject || row.name,
  cardSubtitle: (row) => row.customer || "",
  cardBadge: (row) => (row.priority ? { status: row.priority } : null),
  cardMeta: (row) => row.opening_date,
  createRouteName: "ComplaintNew",
  detailRouteName: "ComplaintDetail",
  emptyIcon: "complaint",
  emptyTitle: "No complaints logged",
  emptyDescription: "Raise a complaint or claim with the + button.",
}
</script>

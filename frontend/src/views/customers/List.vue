<template>
  <ListView :config="config" />
</template>

<script setup>
import ListView from "@/components/ListView.vue"

const config = {
  title: "My Customers",
  method: "field_sales.api.customers.customer_list",
  searchable: true,
  fallback: "/",
  // Primary (a distributor/direct account) vs Secondary (an outlet reached
  // through a channel partner) - a real distinction already on the org's
  // own Customer master (customer_level), not something this screen invents.
  tabs: [
    { key: "primary", label: "Primary" },
    { key: "secondary", label: "Secondary" },
  ],
  defaultTab: "primary",
  statusField: "customer_level",
  cardTitle: (row) => row.customer_name || row.name,
  cardSubtitle: (row) =>
    row.customer_level === "Secondary"
      ? [row.cp_name && `via ${row.cp_name}`, row.territory].filter(Boolean).join(" · ")
      : [row.customer_group, row.territory].filter(Boolean).join(" · "),
  cardMeta: (row) => row.mobile_no || "",
  detailRouteName: "CustomerDetail",
  emptyIcon: "customer",
  emptyTitle: "No customers in scope",
  emptyDescription: "No customers are visible for your territory yet.",
}
</script>

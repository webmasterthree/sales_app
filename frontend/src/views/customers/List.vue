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
  cardTitle: (row) => row.customer_name || row.name,
  cardSubtitle: (row) => [row.customer_group, row.territory].filter(Boolean).join(" · "),
  cardMeta: (row) => row.mobile_no || "",
  detailRouteName: "CustomerDetail",
  emptyIcon: "customer",
  emptyTitle: "No customers in scope",
  emptyDescription: "No customers are visible for your territory yet.",
}
</script>

<template>
  <ListView :config="config" />
</template>

<script setup>
import ListView from "@/components/ListView.vue"

const config = {
  title: "Customer Onboarding",
  method: "field_sales.api.onboarding.onboarding_list",
  searchable: true,
  mineToggle: true,
  mineLabel: "requests",
  statusField: "status",
  tabs: [
    { key: "draft", label: "Draft" },
    { key: "pending", label: "Pending" },
    { key: "approved", label: "Approved" },
    { key: "rejected", label: "Rejected" },
  ],
  defaultTab: "pending",
  filters: [
    { key: "business_type", label: "Type", options: ["Registered", "UnRegistered"] },
  ],
  cardTitle: (row) => row.customer_name || row.name,
  cardSubtitle: (row) => row.business_type || "",
  cardMeta: (row) => row.request_date,
  createRouteName: "OnboardingNew",
  detailRouteName: "OnboardingDetail",
  emptyIcon: "kyc",
  emptyTitle: "No onboarding requests",
  emptyDescription: "Start a new customer KYC with the + button.",
}
</script>

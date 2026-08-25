<template>
  <ListView :config="config" />
</template>

<script setup>
import ListView from "@/components/ListView.vue"

// A manager's approval queue - onboarding requests waiting on a decision.
// Sample/collateral/demo requests also carry a "Pending" status in the
// backend but expose no approve/reject endpoint yet, so this queue only
// covers what a manager can actually act on end-to-end today.
const config = {
  title: "Approval queue",
  method: "field_sales.api.onboarding.onboarding_list",
  defaultTab: "pending",
  tabs: [{ key: "pending", label: "Pending" }],
  statusField: "status",
  cardTitle: (row) => row.customer_name || row.name,
  cardSubtitle: (row) => row.business_type || "",
  cardMeta: (row) => row.request_date,
  fallback: "/",
  detailRouteName: "OnboardingDetail",
  emptyIcon: "check-circle",
  emptyTitle: "Nothing waiting on you",
  emptyDescription: "No onboarding requests are pending a decision right now.",
}
</script>

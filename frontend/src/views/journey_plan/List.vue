<template>
  <ListView :config="config" />
</template>

<script setup>
import ListView from "@/components/ListView.vue"

const config = {
  title: "Trip Plan",
  fallback: "/journey-plan",
  method: "field_sales.api.journey_plan.journey_plan_list",
  searchable: true,
  mineToggle: true,
  mineLabel: "plans",
  // The real ASM -> NSM approval state, not nature_of_travel (still shown
  // separately in cardSubtitle) - a plan can sit at docstatus 0 through
  // "Pending" and "ASM Approved" both, so the card's own status has to
  // come from workflow_state to mean anything.
  statusField: "workflow_state",
  tabs: [
    { key: "pending", label: "Pending" },
    { key: "approved", label: "Approved" },
    { key: "rejected", label: "Rejected" },
  ],
  defaultTab: "pending",
  filters: [
    { key: "nature_of_travel", label: "Nature", options: ["HQ", "EX-HQ", "NT", "NO"] },
  ],
  cardTitle: (row) => row.visit_date || row.name,
  cardSubtitle: (row) => [row.nature_of_travel, row.territory].filter(Boolean).join(" · "),
  cardMeta: (row) => (row.sales_person_name ? `Rep: ${row.sales_person_name}` : ""),
  createRouteName: "JourneyPlanNew",
  detailRouteName: "JourneyPlanDetail",
  emptyIcon: "journey",
  emptyTitle: "No journey plans yet",
  emptyDescription: "Plan your first travel route with the + button.",
}
</script>

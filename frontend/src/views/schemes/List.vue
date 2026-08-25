<template>
  <ListView :config="config" />
</template>

<script setup>
import { onMounted, reactive } from "vue"
import { call } from "frappe-ui"
import ListView from "@/components/ListView.vue"

// Schemes are read-only: native Pricing Rules with rate_or_discount =
// "Discount Percentage" (see field_sales.api.schemes). There is no create
// route here on purpose.
const config = reactive({
  title: "Schemes",
  method: "field_sales.api.schemes.scheme_list",
  searchable: true,
  cardTitle: (row) => row.title || row.name,
  cardSubtitle: (row) =>
    row.valid_upto ? `Valid till ${row.valid_upto}` : "No expiry",
  cardMeta: (row) =>
    row.discount_percentage != null ? `${row.discount_percentage}% off` : "",
  fallback: "/",
  detailRouteName: "SchemeDetail",
  emptyIcon: "scheme",
  emptyTitle: "No schemes running",
  emptyDescription: "No discount schemes are active right now.",
  // Populated on mount below - the Flutter screen offers a scheme-category
  // filter (e.g. "Spot Scheme"); scheme_type is a Link to Scheme Type, so
  // the options are read from that doctype rather than hardcoded.
  filters: [],
})

onMounted(async () => {
  try {
    const types = await call("frappe.client.get_list", {
      doctype: "Scheme Type",
      fields: ["name"],
      limit_page_length: 0,
    })
    if (types?.length) {
      config.filters = [{ key: "scheme_type", label: "Category", options: types.map((t) => t.name) }]
    }
  } catch {
    // the filter is a nice-to-have - a failure here shouldn't block the list
  }
})
</script>

<template>
  <DetailView :name="name" :config="config" />
</template>

<script setup>
import DetailView from "@/components/DetailView.vue"

defineProps({ name: { type: String, required: true } })

const config = {
  title: (doc) => doc?.title || doc?.name || "Scheme",
  method: "field_sales.api.schemes.scheme",
  fallback: "/schemes",
  sections: [
    {
      title: "Scheme",
      fields: [
        { key: "description", label: "Description" },
        { key: "discount_percentage", label: "Discount", format: (v) => (v != null ? `${v}%` : "—") },
        { key: "min_qty", label: "Min qty" },
        { key: "max_qty", label: "Max qty" },
        { key: "valid_from", label: "Valid from" },
        { key: "valid_upto", label: "Valid until" },
        { key: "terms_and_conditions", label: "Terms & conditions", html: true },
      ],
    },
  ],
}
</script>

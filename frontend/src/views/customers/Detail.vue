<template>
  <DetailView :name="name" :config="config">
    <template #extra="{ doc }">
      <div v-if="doc.addresses?.length" class="bg-surface rounded-2xl p-4">
        <p class="font-display font-semibold mb-2">Addresses</p>
        <div v-for="a in doc.addresses" :key="a.name" class="text-sm py-1 border-b border-rule-soft last:border-0">
          <p>{{ [a.address_line1, a.address_line2, a.city, a.state, a.pincode].filter(Boolean).join(", ") }}</p>
          <p class="text-xs text-ink-3">{{ a.address_type }}</p>
        </div>
      </div>
      <div v-if="doc.contacts?.length" class="bg-surface rounded-2xl p-4">
        <p class="font-display font-semibold mb-2">Contacts</p>
        <div v-for="c in doc.contacts" :key="c.name" class="text-sm py-1 border-b border-rule-soft last:border-0">
          <p>{{ [c.first_name, c.last_name].filter(Boolean).join(" ") }}</p>
          <p class="text-xs text-ink-3">{{ c.mobile_no }} {{ c.email_id }}</p>
        </div>
      </div>

      <div v-if="doc.credit_limits?.length" class="bg-surface rounded-2xl p-4">
        <p class="font-display font-semibold mb-2">Credit information</p>
        <div v-for="c in doc.credit_limits" :key="c.name" class="flex justify-between text-sm py-1 border-b border-rule-soft last:border-0">
          <span class="text-ink-2">{{ c.company }}</span>
          <span class="text-ink">₹{{ c.credit_limit }}</span>
        </div>
      </div>

      <div v-if="doc.customer_consumption_info?.length" class="bg-surface rounded-2xl p-4">
        <p class="font-display font-semibold mb-2">Customer segment</p>
        <div v-for="s in doc.customer_consumption_info" :key="s.name" class="text-sm py-1 border-b border-rule-soft last:border-0">
          <div class="flex justify-between">
            <span class="text-ink">{{ s.product_name }}</span>
            <span class="text-ink-2">{{ s.consumption_qty }} {{ s.uom }}</span>
          </div>
          <p class="text-xs text-ink-3">{{ [s.segment, s.category_type].filter(Boolean).join(" · ") }}</p>
        </div>
      </div>
    </template>
  </DetailView>
</template>

<script setup>
import { call } from "frappe-ui"
import DetailView from "@/components/DetailView.vue"

const props = defineProps({ name: { type: String, required: true } })

const config = {
  title: (doc) => doc?.customer_name || doc?.name || "Customer",
  method: "field_sales.api.customers.customer",
  fallback: "/customers",
  sections: [
    {
      title: "Overview",
      fields: [
        { key: "customer_name", label: "Customer name" },
        { key: "customer_level", label: "Customer type" },
        { key: "custom_channel_partner", label: "Distributor" },
        { key: "customer_group", label: "Group" },
        { key: "territory", label: "Territory" },
        { key: "mobile_no", label: "Mobile" },
        { key: "email_id", label: "Email" },
        { key: "business_type", label: "Business type" },
        { key: "gstin", label: "GST No." },
        { key: "proposed_credit", label: "Proposed credit" },
        { key: "payment_terms", label: "Payment term" },
        { key: "disabled", label: "Disabled", format: (v) => (v ? "Yes" : "No") },
      ],
    },
  ],
  actions: [
    {
      label: "Request a change",
      tone: "muted",
      handler: async (doc) => {
        const requested_change = window.prompt("What needs correcting on this customer record?")
        if (!requested_change) return
        await call("field_sales.api.customers.request_customer_change", {
          customer: doc.name, requested_change,
        })
        window.alert("Change request submitted.")
      },
    },
  ],
}
</script>

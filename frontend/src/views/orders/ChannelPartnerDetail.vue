<!--
  Detail for a Secondary Sales Order (fmcg_cp) - the Channel Partner flow's
  own doctype, kept genuinely separate from the native Sales Order Detail.vue.
-->
<template>
  <OrdersTheme>
  <DetailView :name="name" :config="config">
    <template #extra="{ doc }">
      <div v-if="doc.items?.length" class="bg-surface rounded-2xl border border-rule overflow-hidden">
        <p class="px-4 py-3 font-display font-semibold">Items</p>
        <div class="px-4 pb-4 space-y-2">
          <div v-for="row in doc.items" :key="row.name" class="flex justify-between text-sm py-1 border-b border-rule-soft last:border-0">
            <span class="text-ink">
              {{ row.item_name || row.item_code }} × {{ row.qty }} {{ row.uom || "" }}
              <span class="text-ink-3 text-xs">(₹{{ row.rate }}/{{ row.uom || "unit" }})</span>
            </span>
            <span class="text-ink-2">₹{{ row.amount }}</span>
          </div>
        </div>
        <div class="px-4 py-3 border-t border-rule-soft flex justify-between">
          <span class="font-display font-bold text-ink">Total</span>
          <span class="font-display font-bold text-accent-ink">₹{{ doc.grand_total }}</span>
        </div>
      </div>
    </template>
  </DetailView>
  </OrdersTheme>
</template>

<script setup>
import DetailView from "@/components/DetailView.vue"
import OrdersTheme from "@/views/orders/OrdersTheme.vue"

defineProps({ name: { type: String, required: true } })

const config = {
  title: (doc) => (doc ? `CP Order · ${doc.customer_name || doc.customer || doc.name}` : "Loading…"),
  method: "field_sales.api.secondary_sales_order.secondary_sales_order",
  fallback: "/orders",
  sections: [
    {
      title: "Channel partner",
      fields: [
        { key: "customer_name", label: "Customer" },
        { key: "cp_name", label: "Channel Partner", format: (v, doc) => v || doc.custom_channel_partner },
        { key: "set_warehouse", label: "Warehouse" },
        { key: "territory", label: "Territory" },
        { key: "transaction_date", label: "Date" },
        { key: "delivery_date", label: "Delivery Date" },
        { key: "created_by_name", label: "Recorded by" },
        { key: "remarks", label: "Remarks" },
      ],
    },
  ],
  actions: [
    {
      label: "Submit order",
      visible: (doc) => doc.docstatus === 0,
      confirm: "Submit this channel partner order? It cannot be edited afterwards.",
      method: "field_sales.api.secondary_sales_order.submit_secondary_sales_order",
    },
    {
      label: "Cancel order",
      tone: "crit",
      visible: (doc) => doc.docstatus === 1,
      confirm: "Cancel this channel partner order?",
      method: "field_sales.api.secondary_sales_order.cancel_secondary_sales_order",
    },
  ],
}
</script>

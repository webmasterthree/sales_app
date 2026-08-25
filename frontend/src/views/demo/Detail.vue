<template>
  <DetailView :name="name" :config="config">
    <template #extra="{ doc }">
      <div v-if="doc.items?.length" class="bg-surface rounded-2xl p-4">
        <p class="font-display font-semibold mb-2">Items demoed</p>
        <div class="space-y-2">
          <div v-for="row in doc.items" :key="row.name" class="flex items-center justify-between gap-2 py-1 border-b border-rule-soft last:border-0">
            <div class="min-w-0">
              <p class="text-sm font-display truncate">{{ row.item_code }} × {{ row.qty || 0 }}</p>
              <p v-if="row.evaluation" class="text-xs text-good">Evaluated ({{ row.evaluation }})</p>
              <p v-else class="text-xs text-ink-3">Not evaluated yet</p>
            </div>
            <RouterLink
              v-if="!row.evaluation && doc.docstatus === 0"
              :to="{ name: 'DemoEvaluate', params: { name: doc.name, item_code: row.item_code } }"
              class="shrink-0 px-3 py-1.5 rounded-[10px] bg-accent text-accent-fg text-xs font-display"
            >
              Evaluate
            </RouterLink>
          </div>
        </div>
      </div>

      <div v-if="doc.summary && doc.summary.evaluated" class="bg-surface rounded-2xl p-4">
        <p class="font-display font-semibold mb-2">Scorecard summary</p>
        <div class="grid grid-cols-3 gap-2 text-center">
          <div>
            <p class="text-xl font-display font-bold text-accent-ink">{{ doc.summary.evaluated }}</p>
            <p class="text-xs text-ink-2">Evaluated</p>
          </div>
          <div>
            <p class="text-xl font-display font-bold text-accent-ink">{{ doc.summary.orders }}</p>
            <p class="text-xs text-ink-2">Orders</p>
          </div>
          <div>
            <p class="text-xl font-display font-bold text-accent-ink">{{ doc.summary.success_rate }}%</p>
            <p class="text-xs text-ink-2">Success rate</p>
          </div>
        </div>
      </div>
    </template>
  </DetailView>
</template>

<script setup>
import DetailView from "@/components/DetailView.vue"

defineProps({ name: { type: String, required: true } })

const config = {
  title: (doc) => doc?.customer_name || doc?.prospect_name || doc?.outlet_name || doc?.name || "Product Demo",
  method: "field_sales.api.demo.demo",
  fallback: "/requisitions/demos",
  statusField: "status",
  sections: [
    {
      title: "Demo",
      fields: [
        { key: "demo_date", label: "Date" },
        { key: "demo_time", label: "Time" },
        { key: "demo_location", label: "Location" },
        { key: "conducted_by", label: "Conducted by" },
        { key: "specialist", label: "Specialist" },
        { key: "duration", label: "Duration" },
      ],
    },
    {
      title: "Party",
      fields: [
        { key: "customer_name", label: "Customer" },
        { key: "prospect_name", label: "Prospect" },
        { key: "outlet_name", label: "Outlet" },
        { key: "territory", label: "Territory" },
        { key: "sales_person_name", label: "Rep" },
      ],
    },
  ],
  actions: [
    {
      label: "Submit demo",
      tone: "accent",
      visible: (doc) => doc.docstatus === 0,
      confirm: "Submit this demo? It cannot be edited afterwards.",
      method: "field_sales.api.demo.submit_demo",
    },
  ],
}
</script>

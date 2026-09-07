<!--
  Bespoke (not the generic ListView) to match the reference design's flat,
  divider-row list rather than our usual boxed cards - kept only for Orders,
  scoped via OrdersTheme. Real backend tabs (draft/submitted/to_deliver/
  completed) are preserved; only the visual shape changed.

  Direct Customer / Channel Partner is a top-level toggle here (matching
  Flutter's single "Sales Order History" screen covering both order types),
  but the two are kept as genuinely separate queries against separate
  doctypes rather than merged into one blended list: they have different
  status models (docstatus + delivery status vs Draft/Confirmed/Cancelled)
  and a rep without channel-partner access simply won't see that tab do
  anything. Forcing them into one interleaved list would hide that real
  difference rather than represent it honestly.
-->
<template>
  <OrdersTheme>
  <div class="min-h-screen bg-ground pb-28">
    <header class="sticky top-0 z-30 bg-surface border-b border-rule pt-safe">
      <div class="flex items-center gap-2 px-4 py-3 max-w-2xl mx-auto">
        <h1 class="flex-1 font-display font-extrabold text-base text-ink">Sales Order History</h1>
        <RouterLink
          :to="{ name: 'OrderNew' }"
          class="orders-fab w-10 h-10 rounded-full flex items-center justify-center shrink-0"
          aria-label="New sales order"
        >
          <Icon name="plus" :size="20" />
        </RouterLink>
      </div>

      <div class="px-4 pb-3 max-w-2xl mx-auto">
        <div class="flex gap-2">
          <button
            v-for="f in flows"
            :key="f.key"
            type="button"
            class="flex-1 h-9 rounded-lg text-xs font-display font-bold border"
            :class="flow === f.key ? 'bg-ink text-white border-ink' : 'bg-surface border-rule text-ink-2'"
            @click="setFlow(f.key)"
          >
            {{ f.label }}
          </button>
        </div>
      </div>

      <!-- mine / team toggle - same labelled segmented control as the
           shared ListView.vue uses for every other list (Field Visit,
           Journey Plan, ...), hand-built here since Orders uses its own
           bespoke layout rather than that shared component. -->
      <div class="px-4 pb-3 max-w-2xl mx-auto">
        <div class="inline-flex rounded-lg border border-rule overflow-hidden text-xs font-display font-bold">
          <button
            type="button"
            class="px-3 h-9"
            :class="isSelf === 1 ? 'bg-accent text-accent-fg' : 'bg-surface-2 text-ink-2'"
            @click="setIsSelf(1)"
          >
            My orders
          </button>
          <button
            type="button"
            class="px-3 h-9 border-l border-rule"
            :class="isSelf === 0 ? 'bg-accent text-accent-fg' : 'bg-surface-2 text-ink-2'"
            @click="setIsSelf(0)"
          >
            Team's orders
          </button>
        </div>
      </div>

      <div class="px-4 pb-3 max-w-2xl mx-auto">
        <div class="relative">
          <span class="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3">
            <Icon name="search" :size="16" />
          </span>
          <input
            v-model="search"
            type="search"
            placeholder="Search by name, phone, etc"
            class="w-full h-10 rounded-xl border border-rule bg-surface pl-9 pr-3 text-sm text-ink placeholder:text-ink-3 focus:outline-none focus:border-ink"
          />
        </div>
      </div>
      <div class="px-4 pb-3 max-w-2xl mx-auto">
        <div class="flex gap-2">
          <button
            v-for="t in tabs"
            :key="t.key"
            type="button"
            class="flex-1 h-9 rounded-lg text-xs font-display font-bold"
            :class="tab === t.key ? 'bg-accent text-accent-fg' : 'bg-surface-2 text-ink-2'"
            @click="tab = t.key"
          >
            {{ t.label }}
          </button>
        </div>
      </div>
    </header>

    <LoadingSkeleton v-if="loading && !records.length" :rows="4" />
    <ErrorState v-else-if="error" :message="error" @retry="load" />
    <EmptyState
      v-else-if="!records.length"
      icon="order"
      title="No orders"
      :description="flow === 'direct' ? 'No sales orders match this filter yet.' : 'No channel partner orders match this filter yet.'"
    />

    <div v-else class="max-w-2xl mx-auto bg-surface">
      <RouterLink
        v-for="row in filtered"
        :key="row.name"
        :to="flow === 'direct' ? { name: 'OrderDetail', params: { name: row.name } } : { name: 'ChannelPartnerOrderDetail', params: { name: row.name } }"
        class="flex items-center justify-between gap-3 px-4 py-3 border-b border-rule-soft last:border-0 active:bg-surface-2"
      >
        <div class="min-w-0">
          <p class="font-display font-extrabold text-[15px] text-ink truncate">
            {{ row.customer_name || row.customer || row.name }}
          </p>
          <p v-if="flow === 'direct'" class="text-xs text-ink-2 mt-0.5">
            Contact: {{ row.contact_mobile || "—" }} · ₹{{ row.grand_total ?? 0 }}
          </p>
          <p v-else class="text-xs text-ink-2 mt-0.5">
            via {{ row.cp_name || row.custom_channel_partner || "—" }} · {{ row.transaction_date || "—" }}
          </p>
        </div>
        <StatusPill v-if="flow === 'direct'" :status="row.status" />
        <StatusPill v-else :status="row.docstatus === 1 ? 'Submitted' : 'Draft'" />
      </RouterLink>
    </div>
  </div>
  </OrdersTheme>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue"
import { call } from "frappe-ui"
import OrdersTheme from "@/views/orders/OrdersTheme.vue"
import StatusPill from "@/components/StatusPill.vue"
import EmptyState from "@/components/EmptyState.vue"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"
import Icon from "@/components/Icon.vue"

const flows = [
  { key: "direct", label: "Direct Customer" },
  { key: "channel_partner", label: "Channel Partner" },
]

const TABS_BY_FLOW = {
  direct: [
    { key: "draft", label: "Draft" },
    { key: "submitted", label: "Submitted" },
    { key: "to_deliver", label: "To Deliver" },
    { key: "completed", label: "Completed" },
  ],
  channel_partner: [
    { key: "draft", label: "Draft" },
    { key: "submitted", label: "Submitted" },
  ],
}

const flow = ref("direct")
const tabs = computed(() => TABS_BY_FLOW[flow.value])
const tab = ref("submitted")
const search = ref("")
const records = ref([])
const loading = ref(true)
const error = ref("")
const isSelf = ref(null) // null = everyone in scope, 1 = mine, 0 = my team's

function setFlow(key) {
  if (flow.value === key) return
  flow.value = key
  tab.value = flow.value === "direct" ? "submitted" : "draft"
}

function setIsSelf(val) {
  isSelf.value = isSelf.value === val ? null : val
  load()
}

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return records.value
  return records.value.filter((r) =>
    `${r.customer_name || ""} ${r.customer || ""} ${r.contact_mobile || ""} ${r.cp_name || ""}`.toLowerCase().includes(q)
  )
})

async function load() {
  loading.value = true
  error.value = ""
  try {
    const method = flow.value === "direct"
      ? "field_sales.api.catalog.order_list"
      : "field_sales.api.secondary_sales_order.secondary_sales_order_list"
    const args = { tab: tab.value }
    if (isSelf.value !== null) args.is_self = isSelf.value
    const result = await call(method, args)
    records.value = result?.records || []
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load sales orders."
  } finally {
    loading.value = false
  }
}

watch([flow, tab], load)
onMounted(load)
</script>

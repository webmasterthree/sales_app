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
    <AppBar title="Sales Order History" :subtitle="hasLoadedOnce ? `${filtered.length} result${filtered.length === 1 ? '' : 's'}` : ''" :back="false">
      <template #actions>
        <RouterLink
          :to="{ name: 'OrderNew' }"
          class="w-9 h-9 rounded-full bg-accent text-accent-fg flex items-center justify-center shrink-0"
          aria-label="New sales order"
        >
          <Icon name="plus" :size="18" />
        </RouterLink>
      </template>
    </AppBar>

    <div class="px-4 pt-3 max-w-2xl mx-auto">
      <div class="flex gap-2">
        <button
          v-for="f in flows"
          :key="f.key"
          type="button"
          class="flex-1 h-9 rounded-lg text-xs font-display font-bold border"
          :class="flow === f.key ? 'bg-accent text-accent-fg border-transparent' : 'bg-surface border-rule text-ink-2'"
          @click="setFlow(f.key)"
        >
          {{ f.label }}
        </button>
      </div>
    </div>

    <!-- search + filter trigger, collapsed like every other list - Status
         tabs and the mine/team toggle live in the sheet, opened on demand. -->
    <div class="flex gap-2 px-4 pt-3 max-w-2xl mx-auto">
      <div class="relative flex-1 min-w-0">
        <span class="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3">
          <Icon name="search" :size="16" />
        </span>
        <input
          v-model="search"
          type="search"
          placeholder="Search by name, phone, etc"
          class="w-full h-[48px] rounded-xl border border-rule bg-surface pl-9 pr-3 text-sm text-ink placeholder:text-ink-3 focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
        />
      </div>
      <button
        type="button"
        class="relative w-[48px] h-[48px] rounded-xl border flex items-center justify-center shrink-0"
        :class="isSelf !== null ? 'border-accent text-accent-ink' : 'border-rule text-ink-2'"
        aria-label="Filters"
        @click="filterSheetOpen = true"
      >
        <Icon name="filter" :size="18" />
        <span
          v-if="isSelf !== null"
          class="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-accent text-accent-fg text-[10px] font-mono font-bold flex items-center justify-center"
        >1</span>
      </button>
    </div>

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

  <!-- filter sheet - Status and the mine/team toggle live here, same
       collapsed pattern as every other list screen. Flow (Direct Customer /
       Channel Partner) stays visible above the fold since it's a primary
       mode switch (different doctype, different columns) rather than a
       true filter. -->
  <div
    v-if="filterSheetOpen"
    class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40"
    @click.self="filterSheetOpen = false"
  >
    <div class="bg-surface w-full sm:max-w-sm sm:rounded-2xl rounded-t-2xl overflow-hidden pb-safe max-h-[85vh] flex flex-col">
      <div class="h-[3px] shrink-0" style="background: linear-gradient(90deg, var(--fs-accent), var(--fs-chart))" aria-hidden="true" />
      <div class="flex justify-center pt-2 sm:hidden shrink-0"><div class="w-10 h-1 rounded-full bg-rule"></div></div>
      <div class="px-5 pt-3 pb-2 flex items-center justify-between shrink-0">
        <p class="text-lg font-display font-bold text-ink">Filters</p>
        <button v-if="isSelf !== null" type="button" class="text-sm font-display font-semibold text-accent-ink" @click="isSelf = null; load()">
          Clear all
        </button>
      </div>

      <div class="px-5 pb-4 overflow-y-auto space-y-5">
        <div>
          <p class="text-[10px] font-display font-semibold text-ink-3 uppercase tracking-wide mb-2">Status</p>
          <div class="flex gap-2 flex-wrap">
            <button
              v-for="t in tabs"
              :key="t.key"
              type="button"
              class="h-9 px-3.5 rounded-full text-sm font-display font-medium border"
              :class="tab === t.key ? 'bg-accent-soft text-accent-ink border-accent' : 'bg-surface text-ink-2 border-rule'"
              @click="tab = t.key"
            >
              {{ t.label }}
            </button>
          </div>
        </div>

        <div>
          <p class="text-[10px] font-display font-semibold text-ink-3 uppercase tracking-wide mb-2">Ownership</p>
          <div class="flex gap-2">
            <button
              type="button"
              class="flex-1 h-[42px] rounded-xl text-sm font-display font-semibold border"
              :class="isSelf === 1 ? 'bg-accent text-accent-fg border-transparent' : 'bg-surface text-ink-2 border-rule'"
              @click="setIsSelf(1)"
            >
              My orders
            </button>
            <button
              type="button"
              class="flex-1 h-[42px] rounded-xl text-sm font-display font-semibold border"
              :class="isSelf === 0 ? 'bg-accent text-accent-fg border-transparent' : 'bg-surface text-ink-2 border-rule'"
              @click="setIsSelf(0)"
            >
              Team's orders
            </button>
          </div>
        </div>
      </div>

      <div class="px-5 pb-4 pt-1 shrink-0">
        <button
          type="button"
          class="w-full h-[50px] rounded-xl bg-accent text-accent-fg font-display font-bold text-sm"
          @click="filterSheetOpen = false"
        >
          Show {{ filtered.length }} result{{ filtered.length === 1 ? "" : "s" }}
        </button>
      </div>
    </div>
  </div>
  </OrdersTheme>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue"
import { call } from "frappe-ui"
import OrdersTheme from "@/views/orders/OrdersTheme.vue"
import AppBar from "@/components/AppBar.vue"
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
const hasLoadedOnce = ref(false)
const error = ref("")
const isSelf = ref(null) // null = everyone in scope, 1 = mine, 0 = my team's
const filterSheetOpen = ref(false)

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
    hasLoadedOnce.value = true
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load sales orders."
  } finally {
    loading.value = false
  }
}

watch([flow, tab], load)
onMounted(load)
</script>

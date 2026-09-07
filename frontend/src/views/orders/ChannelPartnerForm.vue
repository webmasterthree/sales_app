<!--
  Channel partner order - a sale booked for a Secondary customer, reached
  through that customer's own fixed channel partner (Customer.custom_channel_partner
  - the same real field Field Visit and the Direct Customer order form
  already derive from). Books a real "Secondary Sales Order" (fmcg_cp),
  a genuinely different doctype from the native Sales Order the Direct
  Customer flow creates - see field_sales/api/secondary_sales_order.py's
  module docstring for why almost everything here (channel partner, every
  line's rate, item_template) has to be derived server-side rather than
  left to that doctype's own controller, which does nothing.
-->
<template>
  <OrdersTheme>
  <div v-if="!formReady" class="p-6 text-center text-sm text-ink-3">Loading visit details…</div>
  <FormView
    v-else
    title="New channel partner order"
    fallback="/orders"
    :steps="steps"
    :initial-data="initialData"
    submit-label="Submit"
    :on-submit="createOrder"
    @saved="onSaved"
  >
    <!-- Step 0: the Secondary customer (channel partner auto-derives),
         the channel partner's own warehouse, and the dates. -->
    <template #step-0="{ data, errors }">
      <div class="bg-surface rounded-2xl p-4 space-y-4">
        <p v-if="prefillError" class="text-xs text-warn bg-warn/10 border border-warn/30 rounded-xl p-3">{{ prefillError }}</p>
        <CustomerPicker
          label="Channel Partner *"
          :multiple="false"
          distributors-only
          :known-label="channelPartnerDisplayName"
          :model-value="selectedChannelPartner"
          @update:model-value="onChannelPartnerPicked(data, $event)"
        />

        <CustomerPicker
          v-if="selectedChannelPartner"
          label="Customer *"
          :multiple="false"
          secondary-only
          :extra-filters="{ custom_channel_partner: selectedChannelPartner }"
          :known-label="customerDisplayName"
          :model-value="data.customer"
          @update:model-value="onCustomerPicked(data, $event)"
        />
        <p v-else class="text-xs text-ink-3 -mt-2">Pick a channel partner first to see their customers.</p>

        <div v-if="data.customer" class="rounded-xl border border-rule bg-surface-2 px-3 py-2 text-sm text-ink">
          Channel Partner
          <span class="text-ink-2">· {{ channelPartnerName || "—" }}</span>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Channel partner warehouse <span class="text-crit">*</span></label>
          <select
            v-model="data.set_warehouse"
            class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
            :class="errors.set_warehouse ? 'border-crit' : ''"
          >
            <option value="">Select warehouse</option>
            <option v-for="w in warehouses" :key="w.name" :value="w.name">{{ w.warehouse_name }}</option>
          </select>
          <p v-if="!warehousesLoading && !warehouses.length" class="text-xs text-ink-3 mt-1">
            No channel partner warehouses are set up yet.
          </p>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Date <span class="text-crit">*</span></label>
          <input v-model="data.transaction_date" type="date" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm" />
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Delivery date (optional)</label>
          <input v-model="data.delivery_date" type="date" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm" />
        </div>
      </div>
    </template>

    <!-- Step 1: priced items - same catalogue/pricing engine as the Direct
         Customer flow (field_sales.api.catalog.item_price), quoted against
         this customer's own DL pricing, not the unpriced stock the old
         (fictional-doctype) version of this screen assumed. -->
    <template #step-1="{ data }">
      <div class="space-y-3">
        <p v-if="!data.items.length" class="text-sm text-ink-3 px-1">No items yet. Add one below.</p>

        <div v-for="(row, i) in data.items" :key="i" class="bg-surface rounded-2xl border border-rule p-4 space-y-3">
          <div class="flex items-center justify-between pb-1 border-b border-rule-soft">
            <span class="inline-flex items-center gap-2 text-sm font-display font-semibold text-ink">
              <span class="w-6 h-6 rounded-full bg-accent-soft text-accent-ink text-xs font-bold flex items-center justify-center shrink-0">{{ i + 1 }}</span>
              Item
            </span>
            <button
              type="button"
              class="w-8 h-8 rounded-full flex items-center justify-center text-ink-3 active:bg-surface-2"
              aria-label="Remove item"
              @click="data.items.splice(i, 1)"
            >
              <Icon name="close" :size="14" />
            </button>
          </div>

          <ItemPicker
            label="Item"
            :model-value="row.item_code"
            :display="row.item_code ? `${row.item_name || row.item_code}` : ''"
            @update:model-value="row.item_code = $event"
            @picked="(item) => onItemPicked(data, row, item)"
          />

          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block text-xs text-ink-3 mb-1">Qty</label>
              <input
                v-model.number="row.qty"
                type="number"
                min="0"
                step="0.01"
                class="w-full h-[42px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm"
                @change="refreshRate(data, row)"
              />
            </div>
            <div>
              <label class="block text-xs text-ink-3 mb-1">UOM</label>
              <input :value="row.uom" readonly placeholder="From item" class="w-full h-[42px] rounded-[10px] border border-rule bg-ground px-3 text-sm text-ink-3" />
            </div>
          </div>

          <div v-if="row.item_code && !row.priceNotFound">
            <label class="block text-xs text-ink-3 mb-1">Rate</label>
            <input
              :value="row.rate != null ? `₹${row.rate.toFixed(2)} / ${row.uom || 'unit'}` : 'Pricing…'"
              readonly
              class="w-full h-[42px] rounded-[10px] border border-rule bg-ground px-3 text-sm text-ink-3"
            />
          </div>

          <!-- No Item Price exists for this item at all - quote_custom_rate/
               quoted_rate are real fields the doctype already has for
               exactly this gap. The server only ever reaches for this when
               its own pricing engine has nothing to offer (see
               secondary_sales_order.py's _resolve_context) - it can't be
               used to undercut a price that does exist. -->
          <div v-else-if="row.priceNotFound" class="rounded-xl border border-warn/30 bg-warn/10 p-3 space-y-2">
            <p class="text-xs text-warn font-display font-medium">No price on file for this item.</p>
            <label class="flex items-center gap-2 text-sm text-ink">
              <input
                type="checkbox"
                :checked="!!row.quote_custom_rate"
                @change="toggleCustomRate(row, $event.target.checked)"
              />
              Quote a custom rate
            </label>
            <input
              v-if="row.quote_custom_rate"
              v-model.number="row.quoted_rate"
              type="number"
              min="0"
              step="0.01"
              placeholder="Rate per unit"
              class="w-full h-[42px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm"
              @input="onQuotedRateChanged(row)"
            />
          </div>

          <p v-if="row.rate != null" class="text-sm font-display font-semibold text-ink text-right">
            Amount: ₹{{ (row.rate * (row.qty || 0)).toFixed(2) }}
          </p>
        </div>

        <button
          type="button"
          class="w-full py-2.5 rounded-xl border border-dashed border-rule text-sm font-display text-ink-2"
          @click="data.items.push({ item_code: '', item_name: '', qty: 1, uom: '', rate: null, priceNotFound: false, quote_custom_rate: 0, quoted_rate: null })"
        >
          + Add item
        </button>

        <div class="bg-surface rounded-2xl p-4">
          <label class="block text-sm font-display text-ink-2 mb-1">Remarks (optional)</label>
          <textarea v-model="data.remarks" rows="3" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm" />
        </div>
      </div>
    </template>

    <!-- Step 2: review -->
    <template #step-2="{ data }">
      <div class="bg-surface rounded-2xl p-4 space-y-3">
        <div class="flex justify-between text-sm">
          <span class="text-ink-2">Customer</span>
          <span class="font-display font-medium">{{ customerLabel(data.customer) }}</span>
        </div>
        <div class="flex justify-between text-sm">
          <span class="text-ink-2">Channel Partner</span>
          <span class="font-display font-medium">{{ channelPartnerName || "—" }}</span>
        </div>
        <div class="flex justify-between text-sm">
          <span class="text-ink-2">Warehouse</span>
          <span class="font-display font-medium">{{ warehouseLabel(data.set_warehouse) }}</span>
        </div>
        <div class="flex justify-between text-sm">
          <span class="text-ink-2">Date</span>
          <span class="font-display font-medium">{{ data.transaction_date || "—" }}</span>
        </div>
        <div class="border-t border-rule-soft pt-2 space-y-2">
          <div v-for="(row, i) in data.items" :key="i" class="flex justify-between text-sm">
            <span class="text-ink-2">
              {{ row.item_name || row.item_code }} × {{ row.qty || 0 }}
              <span class="text-ink-3">(₹{{ (row.rate || 0).toFixed(2) }}/{{ row.uom || "unit" }})</span>
            </span>
            <span class="font-display font-medium">₹{{ ((row.rate || 0) * (row.qty || 0)).toFixed(2) }}</span>
          </div>
        </div>
        <div class="border-t border-rule-soft pt-2 flex justify-between">
          <span class="font-display font-bold text-ink">Total</span>
          <span class="font-display font-bold text-accent-ink">₹{{ orderTotal(data).toFixed(2) }}</span>
        </div>
        <p class="text-xs text-ink-3">
          This is an estimate. The server recalculates every line's rate
          when the order is created, so the amount actually booked may differ
          slightly.
        </p>
      </div>
    </template>
  </FormView>
  </OrdersTheme>
</template>

<script setup>
import { onMounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { call } from "frappe-ui"
import FormView from "@/components/FormView.vue"
import CustomerPicker from "@/components/CustomerPicker.vue"
import ItemPicker from "@/components/ItemPicker.vue"
import Icon from "@/components/Icon.vue"
import OrdersTheme from "@/views/orders/OrdersTheme.vue"
import { queueWrite } from "@/composables/offlineQueue"

const router = useRouter()
const route = useRoute()

const initialData = {
  customer: "",
  set_warehouse: "",
  transaction_date: new Date().toISOString().slice(0, 10),
  delivery_date: "",
  remarks: "",
  fs_field_visit: "",
  items: [],
}

const warehouses = ref([])
const warehousesLoading = ref(true)
const channelPartnerName = ref("")
const channelPartnerDisplayName = ref("")
const customerDisplayName = ref("")
const selectedChannelPartner = ref("")

// Same reason as orders/Form.vue's own formReady: FormView copies
// initial-data into its own reactive state once, at setup - a prefill
// fetched asynchronously has to land before <FormView> ever mounts.
const formReady = ref(!route.query.from_visit)
const prefillError = ref("")

async function loadVisitPrefill(visitName) {
  try {
    const result = await call("field_sales.api.secondary_sales_order.secondary_visit_order_prefill", {
      visit_name: visitName,
    })
    selectedChannelPartner.value = result.custom_channel_partner
    channelPartnerDisplayName.value = result.cp_name || result.custom_channel_partner
    channelPartnerName.value = result.cp_name || result.custom_channel_partner
    customerDisplayName.value = result.customer
    initialData.customer = result.customer
    initialData.fs_field_visit = result.fs_field_visit || ""
    initialData.remarks = result.remarks || ""
    if (result.delivery_date) initialData.delivery_date = result.delivery_date
    initialData.items = (result.items || []).map((i) => ({
      item_code: i.item_code, item_name: i.item_name, qty: i.qty, uom: i.uom || "",
      rate: i.rate, priceNotFound: false, quote_custom_rate: 0, quoted_rate: null,
    }))
  } catch (e) {
    prefillError.value = e?.messages?.[0] || e?.message || "Could not load this visit's details."
  } finally {
    formReady.value = true
  }
}

onMounted(async () => {
  try {
    warehouses.value = (await call("field_sales.api.secondary_sales_order.cp_warehouse_list")) || []
  } catch {
    warehouses.value = []
  } finally {
    warehousesLoading.value = false
  }
  if (route.query.from_visit) {
    await loadVisitPrefill(route.query.from_visit)
  }
})

// Picking the channel partner first, then their customers, matches how a
// rep actually works - they know which distributor they're booking for
// before they know which of that distributor's outlets placed the order -
// rather than searching every Secondary customer app-wide to find the
// right one.
function onChannelPartnerPicked(data, name) {
  selectedChannelPartner.value = name
  channelPartnerDisplayName.value = ""
  data.customer = ""
  channelPartnerName.value = ""
  customerDisplayName.value = ""
}

async function onCustomerPicked(data, customerName) {
  data.customer = customerName
  channelPartnerName.value = ""
  customerDisplayName.value = ""
  if (!customerName) return
  try {
    const detail = await call("field_sales.api.customers.customer", { name: customerName })
    channelPartnerName.value = detail.cp_name || detail.custom_channel_partner || ""
    customerDisplayName.value = detail.customer_name || customerName
  } catch {
    // shown as "—" until the server derives its own copy on submit either way
  }
  for (const row of data.items) await refreshRate(data, row)
}

async function onItemPicked(data, row, item) {
  row.item_name = item?.item_name || ""
  row.uom = item?.stock_uom || ""
  await refreshRate(data, row)
}

async function refreshRate(data, row) {
  row.priceNotFound = false
  if (!row.item_code || !data.customer) {
    row.rate = null
    return
  }
  try {
    const result = await call("field_sales.api.catalog.item_price", {
      item_code: row.item_code,
      customer: data.customer,
      warehouse: data.set_warehouse || undefined,
      qty: row.qty || 1,
    })
    row.rate = result.final_rate
    row.quote_custom_rate = 0
    row.quoted_rate = null
  } catch {
    // No Item Price at all for this item/customer - not a transient error,
    // the server-side pricing engine will hit the same PriceNotFound. Offer
    // the same rep-entered quote_custom_rate/quoted_rate fallback the
    // doctype already has, rather than blocking the item outright.
    row.rate = null
    row.priceNotFound = true
  }
}

function toggleCustomRate(row, checked) {
  row.quote_custom_rate = checked ? 1 : 0
  if (!checked) {
    row.quoted_rate = null
    row.rate = null
  } else if (row.quoted_rate) {
    row.rate = row.quoted_rate
  }
}

function onQuotedRateChanged(row) {
  row.rate = row.quoted_rate ? Number(row.quoted_rate) : null
}

function warehouseLabel(name) {
  return warehouses.value.find((w) => w.name === name)?.warehouse_name || name || "—"
}
function customerLabel(name) {
  return customerDisplayName.value || name || "—"
}
function orderTotal(data) {
  return (data.items || []).reduce((sum, row) => sum + (row.rate || 0) * (row.qty || 0), 0)
}

const steps = [
  {
    title: "Customer & warehouse",
    fields: [],
    validate: (d) => {
      if (!d.customer) return "Select the customer this order is for."
      if (!d.set_warehouse) return "Select the channel partner's warehouse."
      if (!d.transaction_date) return "Give a date."
      return ""
    },
  },
  {
    title: "Items",
    fields: [],
    validate: (d) => {
      const rows = (d.items || []).filter((r) => r.item_code && r.qty)
      if (!rows.length) return "Add at least one item with a quantity."
      const unpriced = rows.find((r) => r.priceNotFound && !(r.quote_custom_rate && r.quoted_rate))
      if (unpriced) return `${unpriced.item_name || unpriced.item_code} has no price - check "Quote a custom rate" and enter one, or remove it.`
      return ""
    },
  },
  {
    title: "Review",
    fields: [],
  },
]

async function createOrder(data, mode) {
  const items = data.items
    .filter((r) => r.item_code && r.qty)
    .map((r) => ({
      item_code: r.item_code,
      qty: r.qty,
      uom: r.uom || undefined,
      quote_custom_rate: r.quote_custom_rate ? 1 : 0,
      quoted_rate: r.quote_custom_rate ? r.quoted_rate : undefined,
    }))

  const args = {
    customer: data.customer,
    set_warehouse: data.set_warehouse,
    transaction_date: data.transaction_date,
    delivery_date: data.delivery_date || undefined,
    remarks: data.remarks || undefined,
    fs_field_visit: data.fs_field_visit || undefined,
    items,
  }

  const created = await queueWrite({
    method: "field_sales.api.secondary_sales_order.create_secondary_sales_order",
    args,
    label: "New channel partner order",
  })

  if (mode === "submit" && !created.queued && created?.name) {
    await call("field_sales.api.secondary_sales_order.submit_secondary_sales_order", { name: created.name })
  }
  return created
}

function onSaved(result) {
  if (result?.queued) {
    router.push({ name: "OrderList" })
  } else if (result?.name) {
    router.push({ name: "ChannelPartnerOrderDetail", params: { name: result.name } })
  }
}
</script>

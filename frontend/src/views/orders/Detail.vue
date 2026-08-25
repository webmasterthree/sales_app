<!--
  Bespoke (not the generic DetailView) to match the reference's line-item
  table + bordered info cards, rather than our usual collapsible sections.
  Scoped to Orders only via OrdersTheme.
-->
<template>
  <OrdersTheme>
  <div class="min-h-screen bg-ground pb-28">
    <header class="sticky top-0 z-30 bg-surface border-b border-rule pt-safe">
      <div class="flex items-center gap-2 px-2 py-2 max-w-2xl mx-auto">
        <button type="button" class="flex items-center justify-center w-11 h-11 rounded-full active:bg-surface-2 shrink-0" aria-label="Back" @click="onBack">
          <Icon name="chevron-left" :size="22" />
        </button>
        <h1 class="flex-1 font-display font-extrabold text-base text-ink truncate">
          {{ doc ? `Order #${doc.name}` : "Loading…" }}
        </h1>
        <StatusPill v-if="doc" :status="doc.status" />
      </div>
    </header>

    <LoadingSkeleton v-if="loading" :rows="4" />
    <ErrorState v-else-if="error" :message="error" @retry="load" />

    <div v-else-if="doc" class="max-w-2xl mx-auto px-4 pt-3 space-y-4">
      <div class="bg-surface">
        <div
          v-for="row in doc.items || []"
          :key="row.item_code + row.idx"
          class="flex items-center justify-between gap-3 py-2.5 border-b border-rule-soft text-sm"
        >
          <span class="text-ink">{{ row.item_code }} × {{ row.qty }}</span>
          <span class="font-display font-medium text-ink">₹{{ lineTotal(row) }}</span>
        </div>
        <div class="flex items-center justify-between gap-3 py-3">
          <span class="font-display font-extrabold text-ink">Grand Total</span>
          <span class="font-display font-extrabold text-ink">₹{{ doc.grand_total }}</span>
        </div>
      </div>

      <div class="bg-surface border border-rule rounded-xl p-3">
        <p class="font-display font-bold text-xs text-ink-2 mb-1">Delivery Date</p>
        <p class="text-sm text-ink">{{ doc.delivery_date || "—" }}</p>
      </div>

      <div v-if="doc.custom_delivery_term || doc.payment_terms_template" class="bg-surface border border-rule rounded-xl p-3 space-y-2">
        <p class="font-display font-bold text-xs text-ink-2">Sales Terms</p>
        <div v-if="doc.set_warehouse" class="flex justify-between text-sm">
          <span class="text-ink-2">Warehouse</span>
          <span class="text-ink">{{ doc.set_warehouse }}</span>
        </div>
        <div v-if="doc.custom_delivery_term" class="flex justify-between text-sm">
          <span class="text-ink-2">Delivery Term</span>
          <span class="text-ink">{{ doc.custom_delivery_term }}</span>
        </div>
        <div v-if="doc.payment_terms_template" class="flex justify-between text-sm">
          <span class="text-ink-2">Payment Term</span>
          <span class="text-ink">{{ doc.payment_terms_template }}</span>
        </div>
      </div>

      <div class="bg-surface border border-rule rounded-xl p-3">
        <p class="font-display font-bold text-xs text-ink-2 mb-1">Customer Information</p>
        <p class="text-sm text-ink font-medium">{{ doc.customer_name || doc.customer }}</p>
        <p class="text-xs text-ink-2">{{ doc.contact_display || doc.contact_mobile || "—" }} · {{ doc.territory || "—" }}</p>
      </div>
    </div>

    <div v-if="doc && doc.docstatus === 0" class="fixed bottom-0 inset-x-0 bg-surface border-t border-rule px-4 py-3 pb-safe z-30">
      <button
        type="button"
        class="w-full h-[52px] rounded-xl bg-accent text-accent-fg text-sm font-display font-bold disabled:opacity-60"
        :disabled="busy"
        @click="submitOrder"
      >
        {{ busy ? "Working…" : "Submit order" }}
      </button>
    </div>
  </div>
  </OrdersTheme>
</template>

<script setup>
import { ref, onMounted } from "vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"
import OrdersTheme from "@/views/orders/OrdersTheme.vue"
import StatusPill from "@/components/StatusPill.vue"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"
import Icon from "@/components/Icon.vue"

const props = defineProps({ name: { type: String, required: true } })
const router = useRouter()

const doc = ref(null)
const loading = ref(true)
const error = ref("")
const busy = ref(false)

function lineTotal(row) {
  return ((row.rate || 0) * (row.qty || 0)).toFixed(2)
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    doc.value = await call("field_sales.api.catalog.order", { name: props.name })
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load this order."
  } finally {
    loading.value = false
  }
}

async function submitOrder() {
  busy.value = true
  try {
    await call("field_sales.api.catalog.submit_order", { name: props.name })
    await load()
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not submit this order."
  } finally {
    busy.value = false
  }
}

function onBack() {
  if (window.history.state?.back) router.back()
  else router.replace("/orders")
}

onMounted(load)
</script>

<template>
  <DetailView ref="detailRef" :name="name" :config="config">
    <template #appbar-extra="{ doc }">
      <div
        v-if="doc && doc.check_in && !doc.check_out"
        class="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-accent-soft shrink-0"
        title="Visit in progress"
      >
        <span class="w-1.5 h-1.5 rounded-full bg-accent-ink animate-pulse"></span>
        <span class="font-mono text-xs font-semibold text-accent-ink">{{ elapsed }}</span>
      </div>
    </template>
    <template #extra="{ doc, reload }">
      <div v-if="geoError" class="bg-crit/10 text-crit text-sm rounded-[10px] px-3 py-2">
        {{ geoError }}
        <button type="button" class="underline font-display font-medium" @click="geoError = ''">Try again</button>
      </div>

      <div v-if="doc.shop_photo" class="rounded-2xl overflow-hidden border border-rule">
        <img :src="doc.shop_photo" alt="Shop photo" class="w-full h-48 object-cover block" />
      </div>

      <details v-if="doc.pitched_items?.length" class="bg-surface rounded-2xl border border-rule overflow-hidden">
        <summary class="px-4 py-3 font-display font-semibold cursor-pointer select-none">Products pitched</summary>
        <div class="px-4 pb-4 space-y-2">
          <div v-for="row in doc.pitched_items" :key="row.name" class="text-sm py-1 border-b border-rule-soft last:border-0">
            <div class="flex justify-between">
              <span class="text-ink">{{ row.item_code }}</span>
              <span class="text-ink-2">{{ row.qty }} {{ row.uom }}</span>
            </div>
            <p v-if="row.segment || row.competitor" class="text-xs text-ink-3">
              <span v-if="row.segment">{{ row.segment }}</span>
              <span v-if="row.competitor"> · vs {{ row.competitor }}</span>
            </p>
          </div>
        </div>
      </details>

      <details v-if="doc.consumption?.length" class="bg-surface rounded-2xl border border-rule overflow-hidden">
        <summary class="px-4 py-3 font-display font-semibold cursor-pointer select-none">Current consumption</summary>
        <div class="px-4 pb-4 space-y-2">
          <div v-for="row in doc.consumption" :key="row.name" class="flex justify-between text-sm py-1 border-b border-rule-soft last:border-0">
            <span class="text-ink">{{ row.product_name }} <span class="text-ink-3">({{ row.segment }})</span></span>
            <span class="text-ink-2">{{ row.monthly_qty }} {{ row.uom }}</span>
          </div>
        </div>
      </details>

      <CommentThread doctype="Field Visit" :docname="doc.name" />
    </template>
  </DetailView>

  <LocationConfirmModal :model-value="locationConfirm" @confirm="onLocationConfirm" @cancel="onLocationCancel" />
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"
import DetailView from "@/components/DetailView.vue"
import CommentThread from "@/components/CommentThread.vue"
import LocationConfirmModal from "@/components/LocationConfirmModal.vue"
import { buildLocationConfirm } from "@/utils/locationConfirm"
import { anchorKey, getPosition, setAnchor } from "@/composables/geolocation"

const props = defineProps({ name: { type: String, required: true } })
const router = useRouter()

const detailRef = ref(null)
const geoError = ref("")
const locationConfirm = ref(null)
const now = ref(Date.now())
let timer = null

onMounted(() => {
  timer = setInterval(() => (now.value = Date.now()), 1000)
})
onUnmounted(() => clearInterval(timer))

const elapsed = computed(() => {
  const doc = detailRef.value?.doc
  if (!doc?.check_in) return "00:00:00"

  const anchored = sessionStorage.getItem(anchorKey(doc.name))
  const start = anchored ? Number(anchored) : new Date(doc.check_in.replace(" ", "T")).getTime()
  const secs = Math.max(0, Math.floor((now.value - start) / 1000))
  const h = String(Math.floor(secs / 3600)).padStart(2, "0")
  const m = String(Math.floor((secs % 3600) / 60)).padStart(2, "0")
  const s = String(secs % 60).padStart(2, "0")
  return `${h}:${m}:${s}`
})

// The map popup is the final confirmation step, not a receipt: the actual
// check-in/out only fires once the rep taps Confirm, so a wrong-looking pin
// can still be caught and cancelled before anything is recorded.
let confirmResolve = null

function askLocationConfirm(label, confirmLabel, pos) {
  locationConfirm.value = { ...buildLocationConfirm(label, pos), confirmLabel }
  return new Promise((resolve) => {
    confirmResolve = resolve
  })
}

function onLocationConfirm() {
  locationConfirm.value = null
  confirmResolve?.(true)
  confirmResolve = null
}

function onLocationCancel() {
  locationConfirm.value = null
  confirmResolve?.(false)
  confirmResolve = null
}

// A visit's own visit_type is only a snapshot from whenever it was last
// saved - if the customer's own record changes customer_level afterward
// (a real gap found live: a customer moved to Secondary after several of
// its visits were already submitted as Primary), the stale value on old
// visits would show the wrong "Convert to..." button and the server's own
// live check would then correctly refuse it, which just reads as a
// confusing dead end. Fetching the customer's current level once per visit
// and preferring it once known - falling back to the visit's own value only
// until that arrives - keeps the button that's shown in sync with what the
// server will actually decide.
const liveCustomerLevel = ref(null)
let levelFetchedFor = null

function ensureLiveCustomerLevel(customerName) {
  if (!customerName || levelFetchedFor === customerName) return
  levelFetchedFor = customerName
  call("field_sales.api.customers.customer", { name: customerName })
    .then((c) => { liveCustomerLevel.value = c?.customer_level || "Primary" })
    .catch(() => { liveCustomerLevel.value = null })
}

function isSecondaryCustomer(doc) {
  ensureLiveCustomerLevel(doc.customer)
  if (liveCustomerLevel.value != null) return liveCustomerLevel.value === "Secondary"
  return doc.visit_type === "Secondary"
}

const config = {
  title: (doc) => doc?.customer_name || doc?.prospect_name || doc?.outlet_name || doc?.name || "Visit",
  method: "field_sales.api.field_visit.visit",
  fallback: "/visits",
  statusField: "order_status",
  sections: [
    {
      title: "Visit summary",
      fields: [
        { key: "party_type", label: "Party type" },
        { key: "visit_type", label: "Visit type" },
        { key: "customer_name", label: "Customer" },
        { key: "prospect_name", label: "Prospect" },
        { key: "outlet_name", label: "Outlet" },
        { key: "channel_partner", label: "Channel partner" },
        { key: "contact_number", label: "Contact" },
        { key: "visit_date", label: "Date" },
        { key: "address_line1", label: "Address line 1" },
        { key: "address_line2", label: "Address line 2" },
        { key: "city", label: "City" },
        { key: "state", label: "State" },
        { key: "pincode", label: "Pincode" },
        { key: "territory", label: "Territory" },
        { key: "sales_person_name", label: "Rep" },
      ],
    },
    {
      title: "Timing",
      fields: [
        { key: "check_in", label: "Checked in" },
        { key: "check_out", label: "Checked out" },
        { key: "duration", label: "Duration (s)" },
        { key: "geofence_status", label: "Geofence" },
      ],
    },
    {
      title: "Outcome",
      fields: [
        { key: "order_status", label: "Order status" },
        { key: "deal_confidence", label: "Deal confidence", format: (v) => (v ? `${v} / 5` : "—") },
        { key: "reason", label: "Reason (no order)" },
        { key: "remarks", label: "Remarks" },
      ],
    },
    {
      title: "Demo & follow-up",
      fields: [
        { key: "demo_requested", label: "Demo requested", format: (v) => (v ? "Yes" : "No") },
        { key: "demo_location", label: "Demo location" },
        { key: "onboarding_status", label: "Onboarding status" },
        { key: "workflow_state", label: "Workflow state" },
      ],
    },
  ],
  actions: [
    {
      label: "Check in",
      visible: (doc) => doc.docstatus === 0 && !doc.check_in,
      handler: async (doc, reload) => {
        geoError.value = ""
        const pos = await getPosition()
        if (!pos) {
          geoError.value = "Location is required to check in. Enable location access and try again."
          return
        }
        const proceed = await askLocationConfirm("Check in here?", "Confirm Check-in", pos)
        if (!proceed) return
        await call("field_sales.field_sales.doctype.field_visit.field_visit.check_in", {
          field_visit: doc.name, ...pos,
        })
        setAnchor(doc.name)
        await reload()
      },
    },
    {
      label: "Check out",
      visible: (doc) => doc.docstatus === 0 && doc.check_in && !doc.check_out,
      handler: async (doc, reload) => {
        const pos = await getPosition()
        if (pos) {
          const proceed = await askLocationConfirm("Check out here?", "Confirm Check-out", pos)
          if (!proceed) return
        }
        await call("field_sales.field_sales.doctype.field_visit.field_visit.check_out", {
          field_visit: doc.name, ...(pos || {}),
        })
        sessionStorage.removeItem(anchorKey(doc.name))
        await reload()
      },
    },
    {
      label: "Submit visit",
      visible: (doc) => doc.docstatus === 0 && doc.check_in && doc.check_out,
      confirm: "Submit this visit? It cannot be edited afterwards.",
      method: "field_sales.api.field_visit.submit_visit",
    },
    {
      // Mirrors, for UX only, the gating field_sales.api.catalog.
      // visit_order_prefill actually enforces: submitted, a real Customer
      // (not a Prospect), not already marked as having produced no order,
      // and not a Secondary customer - isSecondaryCustomer() above prefers
      // the customer's own current record over the visit's possibly-stale
      // visit_type, matching what the endpoint itself will actually decide.
      // A visit already converted (fs_field_visit on some Sales Order)
      // isn't checked here - the client has no cheap way to know that
      // without its own round trip - so that case surfaces as an error on
      // the order form itself rather than a hidden button here.
      //
      // No confirm dialog and no direct API call: this only navigates to
      // the real order form, pre-filled from the visit - nothing is created
      // or saved until the rep reviews it there and chooses to. Rate/price
      // lookup and the actual save happen entirely on that screen.
      label: "Convert to Order",
      visible: (doc) =>
        doc.docstatus === 1 &&
        doc.party_type === "Customer" &&
        !!doc.customer &&
        !isSecondaryCustomer(doc) &&
        doc.order_status !== "Without Order",
      handler: async (doc) => {
        router.push({ name: "OrderNewDirect", query: { from_visit: doc.name } })
      },
    },
    {
      // Same idea, other side: a Secondary customer's visit starts a
      // pre-filled Channel Partner order instead of a Direct Customer one -
      // field_sales.api.secondary_sales_order.secondary_visit_order_prefill
      // enforces the same guards (submitted, real Customer, not "Without
      // Order", not already converted, and specifically a Secondary
      // customer - the mirror image of the other action's own guard).
      label: "Convert to Channel Partner Order",
      visible: (doc) =>
        doc.docstatus === 1 &&
        doc.party_type === "Customer" &&
        !!doc.customer &&
        isSecondaryCustomer(doc) &&
        doc.order_status !== "Without Order",
      handler: async (doc) => {
        router.push({ name: "OrderNewChannelPartner", query: { from_visit: doc.name } })
      },
    },
  ],
}
</script>

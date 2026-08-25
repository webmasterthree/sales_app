<template>
  <DetailView ref="detailRef" :name="name" :config="config">
    <template #extra="{ doc, reload }">
      <div v-if="doc.check_in && !doc.check_out" class="bg-accent-soft rounded-2xl p-4 text-center">
        <p class="text-xs text-ink-2 mb-1">Visit in progress</p>
        <p class="font-mono text-2xl font-bold text-accent-ink">{{ elapsed }}</p>
      </div>
      <div v-if="geoDenied" class="bg-warn/10 text-warn text-sm rounded-[10px] px-3 py-2">
        Location access was denied. You can still check in/out without a location, or
        <button type="button" class="underline" @click="geoDenied = false">try again</button>.
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
    </template>
  </DetailView>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue"
import { call } from "frappe-ui"
import DetailView from "@/components/DetailView.vue"

const props = defineProps({ name: { type: String, required: true } })

const detailRef = ref(null)
const geoDenied = ref(false)
const now = ref(Date.now())
let timer = null

onMounted(() => {
  timer = setInterval(() => (now.value = Date.now()), 1000)
})
onUnmounted(() => clearInterval(timer))

// The server stamps check_in/check_out with a naive datetime in the site's
// own timezone, with no offset attached. Parsing that string as if it were
// in the *client's* timezone (as `new Date(str)` does) silently produces a
// wrong, sometimes-future instant whenever a rep's device timezone differs
// from the site's configured one - which then freezes this timer at
// 00:00:00 forever. Rather than trying to reconstruct the site's offset on
// the client, we anchor the running timer on the client's own clock at the
// moment check-in actually succeeds (recorded in sessionStorage so a reload
// during the same visit keeps ticking from the same anchor). Falling back
// to the raw server string only covers the case of reopening a visit that
// was checked in from a different browser/session.
function anchorKey(name) {
  return `field_sales:checkin_anchor:${name}`
}

function setAnchor(name) {
  sessionStorage.setItem(anchorKey(name), String(Date.now()))
}

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

function getPosition() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve({})
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
      (err) => {
        if (err.code === err.PERMISSION_DENIED) geoDenied.value = true
        resolve({})
      },
      { timeout: 8000, maximumAge: 30000 }
    )
  })
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
        { key: "customer_name", label: "Customer" },
        { key: "prospect_name", label: "Prospect" },
        { key: "outlet_name", label: "Outlet" },
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
        const pos = await getPosition()
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
        await call("field_sales.field_sales.doctype.field_visit.field_visit.check_out", {
          field_visit: doc.name, ...pos,
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
  ],
}
</script>

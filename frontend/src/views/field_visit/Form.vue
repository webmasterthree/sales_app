<template>
  <FormView
    title="New visit"
    fallback="/visits"
    :steps="steps"
    :initial-data="initialData"
    submit-label="Create visit"
    :on-submit="createVisit"
    @saved="onSaved"
  >
    <template #step-1="{ data }">
      <div class="bg-surface rounded-2xl p-4 space-y-4">
        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Order status <span class="text-crit">*</span></label>
          <div class="flex gap-2">
            <button
              v-for="opt in ['With Order', 'Without Order']"
              :key="opt"
              type="button"
              class="flex-1 py-2 rounded-[10px] text-sm font-display border"
              :class="data.order_status === opt ? 'bg-accent text-accent-fg border-accent' : 'bg-surface border-rule text-ink-2'"
              @click="data.order_status = opt"
            >
              {{ opt }}
            </button>
          </div>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Deal confidence</label>
          <input
            type="range"
            min="1"
            max="5"
            step="1"
            v-model.number="data.deal_confidence"
            class="w-full accent-[var(--fs-accent)]"
          />
          <div class="flex justify-between text-xs text-ink-3 mt-1">
            <span v-for="n in 5" :key="n">{{ n }}</span>
          </div>
          <p class="text-center text-sm font-display mt-1">{{ confidenceLabel(data.deal_confidence) }}</p>
        </div>

        <div v-if="data.order_status === 'Without Order'">
          <label class="block text-sm font-display text-ink-2 mb-1">Reason <span class="text-crit">*</span></label>
          <input v-model="data.reason" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" placeholder="Field Reason name" />
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Remarks (optional)</label>
          <textarea v-model="data.remarks" rows="3" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" />
        </div>

        <label class="flex items-center gap-2 text-sm">
          <input type="checkbox" v-model="data.demo_requested" true-value="1" false-value="0" />
          Demo requested at this outlet
        </label>
      </div>
    </template>

    <!-- Products pitched - mirrors the Flutter app's "Added Products" list:
         which items were pitched, in what segment, and who the customer
         currently buys them from. Entirely optional: a visit with no
         pitch (e.g. a pure relationship call) is a normal outcome. -->
    <template #step-2="{ data }">
      <div class="space-y-3">
        <div v-for="(row, i) in data.pitched_items" :key="i" class="bg-surface rounded-2xl p-4 space-y-2">
          <div class="flex items-start justify-between gap-2">
            <div class="flex-1 space-y-2">
              <input
                v-model="row.item_code"
                class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
                placeholder="Item code"
              />
              <div class="flex gap-2">
                <input
                  v-model.number="row.qty"
                  type="number"
                  min="0"
                  step="0.01"
                  class="w-1/3 rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
                  placeholder="Qty"
                />
                <input
                  v-model="row.uom"
                  class="w-1/3 rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
                  placeholder="UOM"
                />
                <input
                  v-model="row.segment"
                  class="w-1/3 rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
                  placeholder="Segment"
                />
              </div>
              <input
                v-model="row.competitor"
                class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
                placeholder="Currently using brand (competitor, optional)"
              />
            </div>
            <button type="button" class="text-crit text-sm font-display px-2 py-1" @click="data.pitched_items.splice(i, 1)">
              Remove
            </button>
          </div>
        </div>

        <button
          type="button"
          class="w-full py-2.5 rounded-xl border border-dashed border-rule text-sm font-display text-ink-2"
          @click="data.pitched_items.push({ item_code: '', qty: 1, uom: '', segment: '', competitor: '' })"
        >
          + Add pitched product
        </button>
      </div>
    </template>

    <!-- Current consumption - mirrors the Flutter app's per-segment
         "Monthly Consumption" entry. Also optional. -->
    <template #step-3="{ data }">
      <div class="space-y-3">
        <div v-for="(row, i) in data.consumption" :key="i" class="bg-surface rounded-2xl p-4 space-y-2">
          <div class="flex items-start justify-between gap-2">
            <div class="flex-1 space-y-2">
              <input
                v-model="row.segment"
                class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
                placeholder="Segment"
              />
              <input
                v-model="row.product_name"
                class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
                placeholder="Product"
              />
              <div class="flex gap-2">
                <input
                  v-model.number="row.monthly_qty"
                  type="number"
                  min="0"
                  step="0.01"
                  class="w-1/2 rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
                  placeholder="Monthly quantity"
                />
                <input
                  v-model="row.uom"
                  class="w-1/2 rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
                  placeholder="UOM"
                />
              </div>
            </div>
            <button type="button" class="text-crit text-sm font-display px-2 py-1" @click="data.consumption.splice(i, 1)">
              Remove
            </button>
          </div>
        </div>

        <button
          type="button"
          class="w-full py-2.5 rounded-xl border border-dashed border-rule text-sm font-display text-ink-2"
          @click="data.consumption.push({ segment: '', product_name: '', monthly_qty: 0, uom: '' })"
        >
          + Add consumption entry
        </button>
      </div>
    </template>

    <!-- Shop photo - optional. Uploaded ahead of the visit actually being
         created (there's no docname yet on a new-visit form), then the
         resulting file_url rides along in the create payload like any
         other field. -->
    <template #step-4="{ data }">
      <FileUpload
        v-model="data.shop_photo"
        doctype="Field Visit"
        label="Take a photo of the shop front (optional)"
      />
    </template>
  </FormView>
</template>

<script setup>
import { useRouter } from "vue-router"
import FormView from "@/components/FormView.vue"
import FileUpload from "@/components/FileUpload.vue"
import { queueWrite } from "@/composables/offlineQueue"

const router = useRouter()

const initialData = {
  party_type: "Customer",
  customer: "",
  prospect_name: "",
  outlet_name: "",
  contact_number: "",
  visit_date: new Date().toISOString().slice(0, 10),
  address_line1: "",
  address_line2: "",
  city: "",
  state: "",
  pincode: "",
  order_status: "With Order",
  deal_confidence: "3",
  reason: "",
  remarks: "",
  demo_requested: "0",
  pitched_items: [],
  consumption: [],
  shop_photo: "",
}

function confidenceLabel(v) {
  return { 1: "Very low", 2: "Low", 3: "Moderate", 4: "High", 5: "Very high" }[v] || "Moderate"
}

const steps = [
  {
    title: "Party & location",
    fields: [
      { key: "party_type", label: "Party type", type: "select", options: ["Customer", "Prospect"], required: true },
      { key: "customer", label: "Customer (if existing)", type: "text" },
      { key: "prospect_name", label: "Prospect name (if new)", type: "text" },
      { key: "outlet_name", label: "Outlet name", type: "text", required: true },
      { key: "contact_number", label: "Contact number", type: "text" },
      { key: "visit_date", label: "Visit date", type: "date", required: true },
      { key: "address_line1", label: "Address line 1", type: "text" },
      { key: "address_line2", label: "Address line 2", type: "text" },
      { key: "city", label: "City", type: "text" },
      { key: "state", label: "State", type: "text" },
      { key: "pincode", label: "Pincode", type: "text" },
    ],
    validate: (d) => {
      if (d.party_type === "Customer" && !d.customer) return "Select or enter the customer visited."
      if (d.party_type === "Prospect" && !d.prospect_name) return "Enter a name for the prospect visited."
      return ""
    },
  },
  {
    title: "Outcome",
    fields: [],
    validate: (d) => {
      if (d.order_status === "Without Order" && !d.reason) return "Give a reason why the visit did not produce an order."
      return ""
    },
  },
  {
    title: "Products pitched",
    fields: [],
  },
  {
    title: "Consumption",
    fields: [],
  },
  {
    title: "Photo",
    fields: [],
  },
]

async function createVisit(data) {
  const args = { ...data }
  if (args.party_type === "Customer") delete args.prospect_name
  else delete args.customer
  args.pitched_items = (args.pitched_items || []).filter((r) => r.item_code)
  args.consumption = (args.consumption || []).filter((r) => r.segment || r.product_name)
  return queueWrite({
    method: "field_sales.api.field_visit.create_visit",
    args,
    label: "New field visit",
  })
}

function onSaved(result) {
  if (result?.queued) {
    router.push({ name: "VisitList" })
  } else if (result?.name) {
    router.push({ name: "VisitDetail", params: { name: result.name } })
  }
}
</script>

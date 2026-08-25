<template>
  <FormView
    title="New product demo"
    fallback="/requisitions/demos"
    :steps="steps"
    :initial-data="initialData"
    submit-label="Create demo"
    :on-submit="createDemo"
    @saved="onSaved"
  >
    <template #step-0="{ data, errors }">
      <div class="bg-surface rounded-2xl p-4 space-y-4">
        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Party type <span class="text-crit">*</span></label>
          <div class="flex gap-2">
            <button
              v-for="opt in ['Customer', 'Prospect']"
              :key="opt"
              type="button"
              class="flex-1 py-2 rounded-[10px] text-sm font-display border"
              :class="data.party_type === opt ? 'bg-accent text-accent-fg border-accent' : 'bg-surface border-rule text-ink-2'"
              @click="data.party_type = opt"
            >
              {{ opt }}
            </button>
          </div>
        </div>

        <div v-if="data.party_type === 'Customer'">
          <label class="block text-sm font-display text-ink-2 mb-1">Customer <span class="text-crit">*</span></label>
          <input v-model="data.customer" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" :class="errors.customer ? 'border-crit' : ''" />
        </div>
        <div v-else>
          <label class="block text-sm font-display text-ink-2 mb-1">Prospect name <span class="text-crit">*</span></label>
          <input v-model="data.prospect_name" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" />
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Outlet name</label>
          <input v-model="data.outlet_name" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" />
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Demo date <span class="text-crit">*</span></label>
          <input v-model="data.demo_date" type="date" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" />
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Demo time (optional)</label>
          <input v-model="data.demo_time" type="time" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" />
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Location</label>
          <div class="flex gap-2">
            <button
              v-for="opt in ['On Site', 'Lab']"
              :key="opt"
              type="button"
              class="flex-1 py-2 rounded-[10px] text-sm font-display border"
              :class="data.demo_location === opt ? 'bg-accent text-accent-fg border-accent' : 'bg-surface border-rule text-ink-2'"
              @click="data.demo_location = opt"
            >
              {{ opt }}
            </button>
          </div>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Conducted by</label>
          <div class="flex gap-2">
            <button
              v-for="opt in ['Self', 'Specialist']"
              :key="opt"
              type="button"
              class="flex-1 py-2 rounded-[10px] text-sm font-display border"
              :class="data.conducted_by === opt ? 'bg-accent text-accent-fg border-accent' : 'bg-surface border-rule text-ink-2'"
              @click="data.conducted_by = opt"
            >
              {{ opt }}
            </button>
          </div>
        </div>

        <div v-if="data.conducted_by === 'Specialist'">
          <label class="block text-sm font-display text-ink-2 mb-1">Specialist (Employee ID)</label>
          <input v-model="data.specialist" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" />
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Tag a visit (optional)</label>
          <select v-model="data.field_visit" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm">
            <option value="">Not linked to a visit</option>
            <option v-for="visit in recentVisits" :key="visit.name" :value="visit.name">
              {{ visit.customer_name || visit.prospect_name || visit.name }} · {{ visit.visit_date }}
            </option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Remarks (optional)</label>
          <textarea v-model="data.remarks" rows="3" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" />
        </div>
      </div>
    </template>

    <template #step-1="{ data }">
      <div class="space-y-3">
        <div v-for="(row, i) in data.items" :key="i" class="bg-surface rounded-2xl p-4 space-y-2">
          <div class="flex items-start justify-between gap-2">
            <div class="flex-1 space-y-2">
              <input v-model="row.item_code" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" placeholder="Item code being demoed" />
              <div class="flex gap-2">
                <input v-model.number="row.qty" type="number" min="0" step="0.01" class="w-1/2 rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" placeholder="Qty" />
                <input v-model="row.uom" class="w-1/2 rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" placeholder="UOM" />
              </div>
              <input v-model="row.competitor_item" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" placeholder="Competitor product being displaced (optional)" />
              <input v-model.number="row.monthly_consumption" type="number" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" placeholder="Their monthly consumption (optional)" />
            </div>
            <button type="button" class="text-crit text-sm font-display px-2 py-1" @click="data.items.splice(i, 1)">
              Remove
            </button>
          </div>
        </div>

        <button
          type="button"
          class="w-full py-2.5 rounded-[10px] border border-dashed border-rule text-sm font-display text-ink-2"
          @click="data.items.push({ item_code: '', qty: 1, uom: '' })"
        >
          + Add item
        </button>
      </div>
    </template>
  </FormView>
</template>

<script setup>
import { onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"
import FormView from "@/components/FormView.vue"
import { queueWrite } from "@/composables/offlineQueue"

const router = useRouter()

const initialData = {
  party_type: "Customer",
  customer: "",
  prospect_name: "",
  outlet_name: "",
  demo_date: new Date().toISOString().slice(0, 10),
  demo_time: "",
  demo_location: "On Site",
  conducted_by: "Self",
  specialist: "",
  field_visit: "",
  remarks: "",
  items: [{ item_code: "", qty: 1, uom: "" }],
}

const recentVisits = ref([])

onMounted(async () => {
  try {
    const visitPage = await call("field_sales.api.field_visit.visit_list", { is_self: 1, limit: 20 })
    recentVisits.value = visitPage?.records || []
  } catch {
    recentVisits.value = []
  }
})

const steps = [
  {
    title: "Party & schedule",
    fields: [],
    validate: (d) => {
      if (d.party_type === "Customer" && !d.customer) return "Select the customer this demo is for."
      if (d.party_type === "Prospect" && !d.prospect_name) return "Enter a name for the prospect this demo is for."
      if (!d.demo_date) return "Give a demo date."
      return ""
    },
  },
  {
    title: "Items demoed",
    fields: [],
    validate: (d) => {
      const rows = (d.items || []).filter((r) => r.item_code)
      if (!rows.length) return "Add at least one item that was demoed."
      return ""
    },
  },
]

async function createDemo(data) {
  const args = { ...data }
  if (args.party_type === "Customer") delete args.prospect_name
  else delete args.customer
  args.items = (args.items || []).filter((r) => r.item_code)
  return queueWrite({
    method: "field_sales.api.demo.create_demo",
    args,
    label: "New product demo",
  })
}

function onSaved(result) {
  if (result?.queued) {
    router.push({ name: "DemoList" })
  } else if (result?.name) {
    router.push({ name: "DemoDetail", params: { name: result.name } })
  }
}
</script>

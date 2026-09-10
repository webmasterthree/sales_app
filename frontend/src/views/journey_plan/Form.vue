<template>
  <FormView
    title="New journey plan"
    fallback="/journey-plan/trips"
    :steps="steps"
    :initial-data="initialData"
    submit-label="Create plan"
    :on-submit="createPlan"
    @saved="onSaved"
  >
    <template #step-0="{ data }">
      <div class="bg-surface rounded-2xl p-4 space-y-4">
        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Visit date <span class="text-crit">*</span></label>
          <input v-model="data.visit_date" type="date" class="w-full h-[52px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm" />
        </div>
        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Nature of travel <span class="text-crit">*</span></label>
          <div class="flex gap-2 flex-wrap">
            <button
              v-for="opt in ['HQ', 'EX-HQ', 'NT', 'NO']"
              :key="opt"
              type="button"
              class="flex-1 py-2 rounded-[10px] text-sm font-display border min-w-[70px]"
              :class="data.nature_of_travel === opt ? 'bg-accent text-accent-fg border-accent' : 'bg-surface border-rule text-ink-2'"
              @click="data.nature_of_travel = opt"
            >
              {{ opt }}
            </button>
          </div>
        </div>
        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Remarks (optional)</label>
          <textarea v-model="data.remarks" rows="3" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" />
        </div>
      </div>
    </template>

    <!-- Trips - the travel legs that make up this journey plan. Each trip
         is a from -> to leg with a mode of travel and the customers it
         covers, mirroring the Flutter app's "Add Trip" rows. -->
    <template #step-1="{ data }">
      <div class="space-y-4">
        <div v-for="(row, i) in data.trips" :key="i" class="bg-surface rounded-2xl border border-rule p-4 space-y-4">
          <div class="flex items-center justify-between pb-1 border-b border-rule-soft">
            <span class="inline-flex items-center gap-2 text-sm font-display font-semibold text-ink">
              <span class="w-6 h-6 rounded-full bg-accent-soft text-accent-ink text-xs font-bold flex items-center justify-center shrink-0">{{ i + 1 }}</span>
              Trip
            </span>
            <button
              v-if="data.trips.length > 1"
              type="button"
              class="w-8 h-8 rounded-full flex items-center justify-center text-ink-3 active:bg-surface-2"
              aria-label="Remove trip"
              @click="data.trips.splice(i, 1)"
            >
              <Icon name="close" :size="14" />
            </button>
          </div>

          <div class="rounded-xl bg-ground border border-rule-soft p-3 space-y-2">
            <p class="text-xs font-display font-medium text-ink-3 uppercase tracking-wide">From</p>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <div>
                <label class="block text-xs text-ink-3 mb-1">State</label>
                <select
                  :value="row.travel_state_from"
                  class="w-full h-[42px] rounded-[10px] border border-rule bg-surface px-2 text-sm"
                  @change="onStateChange(row, i, 'from', $event.target.value)"
                >
                  <option value="">Select state</option>
                  <option v-for="s in states" :key="s.name" :value="s.name">{{ s.state }}</option>
                </select>
              </div>
              <div>
                <label class="block text-xs text-ink-3 mb-1">District</label>
                <select
                  :value="row.travel_from_district"
                  class="w-full h-[42px] rounded-[10px] border border-rule bg-surface px-2 text-sm disabled:opacity-50"
                  :disabled="!row.travel_state_from"
                  @change="onDistrictChange(row, i, 'from', $event.target.value)"
                >
                  <option value="">Select district</option>
                  <option v-for="d in rowMeta(i).fromDistricts" :key="d.name" :value="d.name">{{ d.district }}</option>
                </select>
              </div>
              <div>
                <label class="block text-xs text-ink-3 mb-1">City</label>
                <select
                  :value="row.travel_from_city"
                  class="w-full h-[42px] rounded-[10px] border border-rule bg-surface px-2 text-sm disabled:opacity-50"
                  :disabled="!row.travel_from_district"
                  @change="row.travel_from_city = $event.target.value"
                >
                  <option value="">Select city</option>
                  <option v-for="c in rowMeta(i).fromCities" :key="c.name" :value="c.name">{{ c.city }}</option>
                </select>
              </div>
            </div>
          </div>

          <label class="flex items-center gap-2 text-sm text-ink-2 -my-1">
            <input type="checkbox" v-model="row.same_as_from_address" true-value="1" false-value="0" class="accent-accent" />
            To address is the same as from
          </label>

          <div v-if="!isTrue(row.same_as_from_address)" class="rounded-xl bg-ground border border-rule-soft p-3 space-y-2">
            <p class="text-xs font-display font-medium text-ink-3 uppercase tracking-wide">To</p>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <div>
                <label class="block text-xs text-ink-3 mb-1">State</label>
                <select
                  :value="row.travel_to_state"
                  class="w-full h-[42px] rounded-[10px] border border-rule bg-surface px-2 text-sm"
                  @change="onStateChange(row, i, 'to', $event.target.value)"
                >
                  <option value="">Select state</option>
                  <option v-for="s in states" :key="s.name" :value="s.name">{{ s.state }}</option>
                </select>
              </div>
              <div>
                <label class="block text-xs text-ink-3 mb-1">District</label>
                <select
                  :value="row.travel_to_district"
                  class="w-full h-[42px] rounded-[10px] border border-rule bg-surface px-2 text-sm disabled:opacity-50"
                  :disabled="!row.travel_to_state"
                  @change="onDistrictChange(row, i, 'to', $event.target.value)"
                >
                  <option value="">Select district</option>
                  <option v-for="d in rowMeta(i).toDistricts" :key="d.name" :value="d.name">{{ d.district }}</option>
                </select>
              </div>
              <div>
                <label class="block text-xs text-ink-3 mb-1">City</label>
                <select
                  :value="row.travel_to_city"
                  class="w-full h-[42px] rounded-[10px] border border-rule bg-surface px-2 text-sm disabled:opacity-50"
                  :disabled="!row.travel_to_district"
                  @change="row.travel_to_city = $event.target.value"
                >
                  <option value="">Select city</option>
                  <option v-for="c in rowMeta(i).toCities" :key="c.name" :value="c.name">{{ c.city }}</option>
                </select>
              </div>
            </div>
          </div>

          <div class="border-t border-rule-soft pt-3 space-y-3">
            <div>
              <label class="block text-xs text-ink-3 mb-1">Mode of travel</label>
              <select v-model="row.mode_of_travel" class="w-full h-[44px] rounded-[10px] border border-rule bg-surface text-ink appearance-none px-3 text-sm">
                <option value="">Select mode</option>
                <option v-for="m in travelModes" :key="m.name" :value="m.name">{{ m.name }}</option>
              </select>
            </div>

            <CustomerPicker
              label="Primary customer(s)"
              :model-value="row.primary_customer"
              @update:model-value="row.primary_customer = $event"
            />
            <CustomerPicker
              label="Secondary customer(s) - channel partner, optional"
              :model-value="row.secondary_customer"
              @update:model-value="row.secondary_customer = $event"
            />
          </div>
        </div>

        <button
          type="button"
          class="w-full py-2.5 rounded-xl border border-dashed border-rule text-sm font-display text-ink-2"
          @click="data.trips.push(blankTrip())"
        >
          + Add trip
        </button>
      </div>
    </template>
  </FormView>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"
import FormView from "@/components/FormView.vue"
import CustomerPicker from "@/components/CustomerPicker.vue"
import Icon from "@/components/Icon.vue"
import { queueWrite } from "@/composables/offlineQueue"

const router = useRouter()

function blankTrip() {
  return {
    travel_state_from: "",
    travel_from_district: "",
    travel_from_city: "",
    same_as_from_address: "0",
    travel_to_state: "",
    travel_to_district: "",
    travel_to_city: "",
    mode_of_travel: "",
    primary_customer: "",
    secondary_customer: "",
  }
}

function isTrue(v) {
  return v === true || v === 1 || v === "1"
}

// Per-row district/city option lists, keyed by trip index - kept separate
// from the trip data itself since these are just fetched option lists,
// not something that gets submitted.
const rowMetaByIndex = reactive({})
function rowMeta(i) {
  if (!rowMetaByIndex[i]) {
    rowMetaByIndex[i] = { fromDistricts: [], fromCities: [], toDistricts: [], toCities: [] }
  }
  return rowMetaByIndex[i]
}

const states = ref([])
onMounted(async () => {
  try {
    states.value = (await call("field_sales.api.journey_plan.state_list")) || []
  } catch {
    states.value = []
  }
})

async function loadDistricts(state) {
  if (!state) return []
  try {
    return (await call("field_sales.api.journey_plan.district_list", { state })) || []
  } catch {
    return []
  }
}

async function loadCities(district) {
  if (!district) return []
  try {
    return (await call("field_sales.api.journey_plan.city_list", { district })) || []
  } catch {
    return []
  }
}

async function onStateChange(row, i, side, value) {
  row[side === "from" ? "travel_state_from" : "travel_to_state"] = value
  row[side === "from" ? "travel_from_district" : "travel_to_district"] = ""
  row[side === "from" ? "travel_from_city" : "travel_to_city"] = ""
  const meta = rowMeta(i)
  const districts = await loadDistricts(value)
  if (side === "from") {
    meta.fromDistricts = districts
    meta.fromCities = []
  } else {
    meta.toDistricts = districts
    meta.toCities = []
  }
}

async function onDistrictChange(row, i, side, value) {
  row[side === "from" ? "travel_from_district" : "travel_to_district"] = value
  row[side === "from" ? "travel_from_city" : "travel_to_city"] = ""
  const meta = rowMeta(i)
  const cities = await loadCities(value)
  if (side === "from") meta.fromCities = cities
  else meta.toCities = cities
}

const initialData = {
  visit_date: new Date().toISOString().slice(0, 10),
  nature_of_travel: "HQ",
  remarks: "",
  trips: [blankTrip()],
}

const travelModes = ref([])
onMounted(async () => {
  try {
    const page = await call("frappe.client.get_list", {
      doctype: "Travel Mode",
      filters: { disabled: 0 },
      fields: ["name"],
      limit_page_length: 0,
    })
    travelModes.value = page || []
  } catch {
    travelModes.value = []
  }
})

const steps = [
  {
    title: "Plan",
    fields: [],
    validate: (d) => {
      if (!d.visit_date) return "Give a date for this journey plan."
      if (!d.nature_of_travel) return "Choose the nature of travel."
      return ""
    },
  },
  {
    title: "Trips",
    fields: [],
    validate: (d) => {
      if (!d.trips || !d.trips.length) return "Add at least one trip."
      for (const row of d.trips) {
        if (!row.mode_of_travel) return "Give a mode of travel for every trip."
      }
      return ""
    },
  },
]

async function createPlan(data) {
  const args = { ...data }
  args.trips = (args.trips || []).filter((r) => r.mode_of_travel)
  return queueWrite({
    method: "field_sales.api.journey_plan.create_journey_plan",
    args,
    label: "New journey plan",
  })
}

function onSaved(result) {
  if (result?.queued) {
    router.push({ name: "JourneyPlanList" })
  } else if (result?.name) {
    router.push({ name: "JourneyPlanDetail", params: { name: result.name } })
  }
}
</script>

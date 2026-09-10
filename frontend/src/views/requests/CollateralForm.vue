<template>
  <FormView
    title="New collateral request"
    fallback="/requisitions/collateral"
    :steps="steps"
    :initial-data="initialData"
    submit-label="Submit request"
    :on-submit="createRequest"
    @saved="onSaved"
  >
    <template #step-0="{ data, errors }">
      <div class="space-y-4">
        <!-- Who the collateral is for - same gap and same fix as
             SampleForm.vue: REQUEST_WRITABLE_FIELDS already accepted
             party_type/customer/prospect_name, this form just never sent them. -->
        <div class="bg-surface rounded-2xl p-4 space-y-3">
          <div>
            <label class="block text-sm font-display text-ink-2 mb-1">Who is this for? <span class="text-crit">*</span></label>
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
          <CustomerPicker
            v-if="data.party_type === 'Customer'"
            label="Customer *"
            :multiple="false"
            :model-value="data.customer"
            @update:model-value="data.customer = $event"
          />
          <div v-else>
            <label class="block text-sm font-display text-ink-2 mb-1">Prospect name <span class="text-crit">*</span></label>
            <input
              v-model="data.prospect_name"
              class="w-full h-[44px] rounded-[10px] border border-rule bg-surface px-3 text-sm"
              :class="errors.prospect_name ? 'border-crit' : ''"
            />
          </div>
        </div>

        <div class="bg-surface rounded-2xl p-4 space-y-3">
          <div class="flex items-center justify-between">
            <label class="text-sm font-display text-ink-2">Requested material <span class="text-crit">*</span></label>
          </div>

          <div v-if="data.items.length" class="space-y-2">
            <div v-for="(row, i) in data.items" :key="row.collateral" class="flex items-center gap-2">
              <span class="flex-1 text-sm truncate">{{ row.collateral_name || row.collateral }}</span>
              <button type="button" class="w-7 h-7 rounded-full border border-rule text-ink-2" @click="row.qty = Math.max(0, row.qty - 1)">-</button>
              <span class="w-8 text-center text-sm font-display">{{ row.qty }}</span>
              <button type="button" class="w-7 h-7 rounded-full border border-rule text-ink-2" @click="row.qty += 1">+</button>
              <button type="button" class="text-crit text-xs font-display px-1" @click="data.items.splice(i, 1)">Remove</button>
            </div>
          </div>
          <p v-else class="text-xs text-ink-3">No material added yet.</p>

          <input
            v-model="materialSearch"
            type="search"
            placeholder="Search marketing collateral"
            class="w-full h-[44px] rounded-[10px] border border-rule bg-surface px-3 text-sm"
            @input="debouncedSearchMaterial"
          />
          <div v-if="materialResults.length" class="border border-rule rounded-[10px] divide-y divide-rule-soft max-h-56 overflow-y-auto">
            <button
              v-for="item in materialResults"
              :key="item.name"
              type="button"
              class="w-full text-left px-3 py-2 text-sm flex items-center justify-between gap-2"
              @click="addItem(data, item)"
            >
              <span class="truncate">{{ item.collateral_name || item.name }}</span>
              <span class="text-accent-ink text-xs font-display shrink-0">Add</span>
            </button>
          </div>
        </div>

        <div class="bg-surface rounded-2xl p-4">
          <label class="block text-sm font-display text-ink-2 mb-1">Remarks (optional)</label>
          <textarea v-model="data.purpose" rows="3" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" />
        </div>
      </div>
    </template>
  </FormView>
</template>

<script setup>
import { ref } from "vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"
import FormView from "@/components/FormView.vue"
import CustomerPicker from "@/components/CustomerPicker.vue"
import { queueWrite } from "@/composables/offlineQueue"

const router = useRouter()

const initialData = {
  party_type: "Customer",
  customer: "",
  prospect_name: "",
  purpose: "",
  items: [], // {collateral, collateral_name, qty}
}

const materialSearch = ref("")
const materialResults = ref([])
let debounceTimer = null

function debouncedSearchMaterial() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(searchMaterial, 300)
}

async function searchMaterial() {
  try {
    const res = await call("field_sales.api.requests.collateral_library", {
      search_text: materialSearch.value || undefined,
      limit: 15,
      current_page: 1,
    })
    materialResults.value = res?.records || []
  } catch {
    materialResults.value = []
  }
}

function addItem(data, item) {
  if (data.items.some((r) => r.collateral === item.name)) return
  data.items.push({
    collateral: item.name,
    collateral_name: item.collateral_name,
    description: item.collateral_name,
    qty: 1,
  })
}

const steps = [
  {
    title: "Collateral request",
    fields: [],
    validate: (d) => {
      if (d.party_type === "Customer" && !d.customer) return "Select the customer this material is for."
      if (d.party_type === "Prospect" && !d.prospect_name) return "Enter a name for the prospect this material is for."
      if (!d.items.length) return "Add at least one item."
      if (d.items.some((r) => !r.qty)) return "Every item needs a quantity."
      return ""
    },
  },
]

async function createRequest(data) {
  const args = {
    party_type: data.party_type,
    customer: data.party_type === "Customer" ? data.customer : undefined,
    prospect_name: data.party_type === "Prospect" ? data.prospect_name : undefined,
    purpose: data.purpose || undefined,
    items: data.items.map((r) => ({ collateral: r.collateral, description: r.description, qty: r.qty })),
  }
  const created = await queueWrite({
    method: "field_sales.api.requests.create_collateral_request",
    args,
    label: "New collateral request",
  })
  // Same reasoning as SampleForm.vue: the button reads "Submit request", and
  // there is no allow-draft step here, so create and submit happen as one
  // user action instead of leaving the request stuck at docstatus 0.
  if (!created.queued && created?.name) {
    await call("field_sales.api.requests.submit_collateral_request", { name: created.name })
  }
  return created
}

function onSaved(result) {
  if (result?.queued) {
    router.push({ name: "CollateralRequestList" })
  } else if (result?.name) {
    router.push({ name: "CollateralRequestDetail", params: { name: result.name } })
  }
}
</script>

<template>
  <FormView
    title="New sample request"
    fallback="/requisitions/samples"
    :steps="steps"
    :initial-data="initialData"
    submit-label="Submit request"
    :on-submit="createRequest"
    @saved="onSaved"
  >
    <template #step-0="{ data, errors }">
      <div class="space-y-4">
        <!-- Who the sample is for - the request write path (REQUEST_WRITABLE_FIELDS)
             already accepted party_type/customer/prospect_name, but this form
             never collected or sent them, so every request saved with a blank
             customer regardless of what the Detail page showed for older,
             directly-inserted records. -->
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
            <label class="text-sm font-display text-ink-2">Selected items <span class="text-crit">*</span></label>
          </div>

          <div v-if="data.items.length" class="space-y-2">
            <div v-for="(row, i) in data.items" :key="row.item_code" class="flex items-center gap-2">
              <span class="flex-1 text-sm truncate">{{ row.item_name || row.item_code }}</span>
              <button type="button" class="w-7 h-7 rounded-full border border-rule text-ink-2" @click="row.qty = Math.max(0, row.qty - 1)">-</button>
              <span class="w-8 text-center text-sm font-display">{{ row.qty }}</span>
              <button type="button" class="w-7 h-7 rounded-full border border-rule text-ink-2" @click="row.qty += 1">+</button>
              <button type="button" class="text-crit text-xs font-display px-1" @click="data.items.splice(i, 1)">Remove</button>
            </div>
          </div>
          <p v-else class="text-xs text-ink-3">No items added yet.</p>

          <input
            v-model="itemSearch"
            type="search"
            placeholder="Search items to add"
            class="w-full h-[44px] rounded-[10px] border border-rule bg-surface px-3 text-sm"
            @input="debouncedSearchItems"
          />
          <div v-if="itemResults.length" class="border border-rule rounded-[10px] divide-y divide-rule-soft max-h-56 overflow-y-auto">
            <button
              v-for="item in itemResults"
              :key="item.item_code"
              type="button"
              class="w-full text-left px-3 py-2 text-sm flex items-center justify-between gap-2"
              @click="addItem(data, item)"
            >
              <span class="truncate">{{ item.item_name }}</span>
              <span class="text-accent-ink text-xs font-display shrink-0">Add</span>
            </button>
          </div>
        </div>

        <div class="bg-surface rounded-2xl p-4">
          <label class="block text-sm font-display text-ink-2 mb-1">Sample required date <span class="text-crit">*</span></label>
          <input v-model="data.required_by" type="date" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" />
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
  required_by: "",
  purpose: "",
  items: [], // {item_code, item_name, qty}
}

const itemSearch = ref("")
const itemResults = ref([])
let debounceTimer = null

function debouncedSearchItems() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(searchItems, 300)
}

async function searchItems() {
  try {
    const res = await call("field_sales.api.catalog.item_list", {
      search_text: itemSearch.value || undefined,
      limit: 15,
      current_page: 1,
    })
    itemResults.value = res?.records || []
  } catch {
    itemResults.value = []
  }
}

function addItem(data, item) {
  if (data.items.some((r) => r.item_code === item.item_code)) return
  data.items.push({ item_code: item.item_code, item_name: item.item_name, qty: 1 })
}

const steps = [
  {
    title: "Sample request",
    fields: [],
    validate: (d) => {
      if (d.party_type === "Customer" && !d.customer) return "Select the customer this sample is for."
      if (d.party_type === "Prospect" && !d.prospect_name) return "Enter a name for the prospect this sample is for."
      if (!d.items.length) return "Add at least one item."
      if (d.items.some((r) => !r.qty)) return "Every item needs a quantity."
      if (!d.required_by) return "Give the date you need the sample by."
      return ""
    },
  },
]

async function createRequest(data) {
  const args = {
    party_type: data.party_type,
    customer: data.party_type === "Customer" ? data.customer : undefined,
    prospect_name: data.party_type === "Prospect" ? data.prospect_name : undefined,
    required_by: data.required_by,
    purpose: data.purpose || undefined,
    items: data.items.map((r) => ({ item_code: r.item_code, qty: r.qty })),
  }
  const created = await queueWrite({
    method: "field_sales.api.requests.create_sample_request",
    args,
    label: "New sample request",
  })
  // The button says "Submit request", not "Save draft" - FormView has no
  // allow-draft here, so this is the only action available, and it should
  // do what it says: file the request, then immediately submit it so it
  // actually reaches docstatus 1 instead of sitting as a draft forever.
  if (!created.queued && created?.name) {
    await call("field_sales.api.requests.submit_sample_request", { name: created.name })
  }
  return created
}

function onSaved(result) {
  if (result?.queued) {
    router.push({ name: "SampleRequestList" })
  } else if (result?.name) {
    router.push({ name: "SampleRequestDetail", params: { name: result.name } })
  }
}
</script>

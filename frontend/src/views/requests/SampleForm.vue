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
    <template #step-0="{ data }">
      <div class="space-y-4">
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
import { queueWrite } from "@/composables/offlineQueue"

const router = useRouter()

const initialData = {
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
      if (!d.items.length) return "Add at least one item."
      if (d.items.some((r) => !r.qty)) return "Every item needs a quantity."
      if (!d.required_by) return "Give the date you need the sample by."
      return ""
    },
  },
]

async function createRequest(data) {
  const args = {
    required_by: data.required_by,
    purpose: data.purpose || undefined,
    items: data.items.map((r) => ({ item_code: r.item_code, qty: r.qty })),
  }
  return queueWrite({
    method: "field_sales.api.requests.create_sample_request",
    args,
    label: "New sample request",
  })
}

function onSaved(result) {
  if (result?.queued) {
    router.push({ name: "SampleRequestList" })
  } else if (result?.name) {
    router.push({ name: "SampleRequestDetail", params: { name: result.name } })
  }
}
</script>

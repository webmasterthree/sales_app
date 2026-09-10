<template>
  <div>
    <label class="block text-xs text-ink-3 mb-1">{{ label }}</label>

    <div v-if="modelValue" class="flex items-center justify-between rounded-xl border border-rule bg-surface px-3 py-2 text-sm">
      <span>{{ display || modelValue }}</span>
      <button type="button" class="text-xs text-accent-ink font-display font-medium" @click="clear">Change</button>
    </div>

    <div v-else-if="segmentRequired && !segment" class="rounded-xl border border-dashed border-rule bg-ground px-3 py-2 text-sm text-ink-3">
      Choose a segment above first.
    </div>

    <div v-else class="relative">
      <input
        v-model="query"
        type="text"
        placeholder="Search item…"
        class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
        @input="onInput"
        @focus="onInput"
      />
      <div
        v-if="results.length"
        class="absolute z-10 mt-1 w-full max-h-48 overflow-y-auto rounded-xl border border-rule bg-surface shadow-lg"
      >
        <button
          v-for="r in results"
          :key="r.item_code"
          type="button"
          class="block w-full text-left px-3 py-2 text-sm hover:bg-ground"
          @click="pick(r)"
        >
          {{ r.item_name || r.item_code }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
// Single-item picker over the real catalogue (field_sales.api.catalog.item_list),
// used wherever a child row needs an Item Link instead of a typed item code.
// Emits both the chosen item_code and, via @picked, the full record - so a
// caller can auto-fill dependent fields like UOM (Item.stock_uom) without a
// second request.
import { ref } from "vue"
import { call } from "frappe-ui"

const props = defineProps({
  label: { type: String, default: "Item" },
  modelValue: { type: String, default: "" },
  display: { type: String, default: "" },
  // When set, search is scoped to items tagged with this real Segment
  // (via Item's Segment Mapping child table) instead of the whole catalogue.
  segment: { type: String, default: "" },
  // If true, search is blocked entirely until `segment` has a value -
  // used where picking a segment first is the whole point of the flow.
  segmentRequired: { type: Boolean, default: false },
  // Fully custom query source: (text) => Promise<items[]>. Takes priority
  // over segment/plain-catalogue search when given - lets callers reuse this
  // picker's UI against a different endpoint (e.g. a priced item-template or
  // item-variant search) without teaching this component every caller's API.
  search: { type: Function, default: null },
})
const emit = defineEmits(["update:modelValue", "picked"])

const query = ref("")
const results = ref([])
let debounceTimer = null

function pick(item) {
  emit("update:modelValue", item.item_code)
  emit("picked", item)
  query.value = ""
  results.value = []
}

function clear() {
  emit("update:modelValue", "")
  emit("picked", null)
}

// Loads a default (unfiltered) page of options - used both on focus, before
// the rep has typed anything, and whenever the query is cleared back to
// empty. Without this, opening the field showed nothing until you typed a
// character, which read as broken rather than as a search box.
async function loadDefault() {
  if (props.segmentRequired && !props.segment) {
    results.value = []
    return
  }
  try {
    if (props.search) {
      results.value = await props.search("")
    } else if (props.segment) {
      results.value = await call("field_sales.api.catalog.item_list_by_segment", {
        segment: props.segment,
        limit: 8,
      })
    } else {
      const page = await call("field_sales.api.catalog.item_list", {
        limit: 8,
        current_page: 1,
      })
      results.value = page?.records || []
    }
  } catch {
    results.value = []
  }
}

function onInput() {
  clearTimeout(debounceTimer)
  const text = query.value.trim()
  if (!text) {
    loadDefault()
    return
  }
  debounceTimer = setTimeout(async () => {
    try {
      if (props.search) {
        results.value = await props.search(text)
      } else if (props.segment) {
        results.value = await call("field_sales.api.catalog.item_list_by_segment", {
          segment: props.segment,
          search_text: text,
          limit: 8,
        })
      } else {
        const page = await call("field_sales.api.catalog.item_list", {
          search_text: text,
          limit: 8,
          current_page: 1,
        })
        results.value = page?.records || []
      }
    } catch {
      results.value = []
    }
  }, 250)
}
</script>

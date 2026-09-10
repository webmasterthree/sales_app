<template>
  <div>
    <div v-if="modelValue" class="flex items-center justify-between rounded-xl border border-rule bg-surface px-3 py-2 text-sm">
      <span>{{ modelValue }}</span>
      <button type="button" class="text-xs text-accent-ink font-display font-medium" @click="emit('update:modelValue', '')">Change</button>
    </div>

    <div v-else class="relative">
      <input
        v-model="query"
        type="text"
        :placeholder="placeholder"
        class="w-full h-[42px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm"
        @input="onInput"
        @focus="onInput"
      />
      <div
        v-if="results.length"
        class="absolute z-10 mt-1 w-full max-h-48 overflow-y-auto rounded-xl border border-rule bg-surface shadow-lg"
      >
        <button
          v-for="r in results"
          :key="r.name"
          type="button"
          class="block w-full text-left px-3 py-2 text-sm hover:bg-ground"
          @click="pick(r)"
        >
          {{ r.name }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
// Generic search picker for a flat { name } master doctype with no size
// guardrail of its own (e.g. Competitor) - the same debounced-search/
// default-page-on-focus pattern as CustomerPicker/ItemPicker, but without
// their doctype-specific fields, for masters that are just a name.
import { ref } from "vue"

const props = defineProps({
  modelValue: { type: String, default: "" },
  placeholder: { type: String, default: "Search…" },
  // (searchText) => Promise<{ name }[]>
  fetcher: { type: Function, required: true },
})
const emit = defineEmits(["update:modelValue"])

const query = ref("")
const results = ref([])
let debounceTimer = null

function pick(record) {
  emit("update:modelValue", record.name)
  query.value = ""
  results.value = []
}

async function loadDefault() {
  try {
    results.value = await props.fetcher("")
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
      results.value = await props.fetcher(text)
    } catch {
      results.value = []
    }
  }, 250)
}
</script>

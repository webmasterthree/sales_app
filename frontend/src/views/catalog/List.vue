<template>
  <div class="min-h-screen bg-ground pb-24">
    <AppBar title="Price List" fallback="/" />
    <div class="max-w-2xl mx-auto px-4 pt-3">
      <div class="flex gap-2 mb-3">
        <input
          v-model="searchText"
          type="search"
          placeholder="Search by SKU or product"
          class="flex-1 rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm"
          @input="debouncedLoad"
        />
        <button
          type="button"
          class="shrink-0 h-[38px] px-3 rounded-[10px] border border-rule bg-surface text-sm font-display"
          @click="showFilters = !showFilters"
        >
          Filter
        </button>
      </div>

      <!-- Warehouse and customer-type filters, matching the Flutter price
           list screen. Read-only display filters only - a rep can narrow
           what price shows, never edit the price itself. -->
      <div v-if="showFilters" class="bg-surface rounded-2xl p-4 mb-3 space-y-4">
        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Warehouse</label>
          <select v-model="filters.warehouse" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm" @change="load">
            <option value="">Any warehouse</option>
            <option v-for="w in warehouses" :key="w.name" :value="w.name">{{ w.warehouse_name || w.name }}</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Customer Type</label>
          <div class="flex gap-4">
            <label class="flex items-center gap-1.5 text-sm">
              <input type="radio" value="" v-model="filters.customer_type" @change="load" /> Any
            </label>
            <label class="flex items-center gap-1.5 text-sm">
              <input type="radio" value="DP" v-model="filters.customer_type" @change="load" /> DP
            </label>
            <label class="flex items-center gap-1.5 text-sm">
              <input type="radio" value="DL" v-model="filters.customer_type" @change="load" /> DL
            </label>
          </div>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Product Category</label>
          <select v-model="filters.item_group" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm" @change="load">
            <option value="">All</option>
            <option v-for="g in itemGroups" :key="g.name" :value="g.name">{{ g.name }}</option>
          </select>
        </div>
      </div>

      <div v-if="activeFilterChips.length" class="flex gap-2 flex-wrap mb-3">
        <button
          v-for="chip in activeFilterChips"
          :key="chip.key"
          type="button"
          class="inline-flex items-center gap-1 rounded-full border border-accent px-3 py-1 text-xs font-display"
          @click="clearFilter(chip.key)"
        >
          {{ chip.label }} ✕
        </button>
      </div>

      <LoadingSkeleton v-if="loading && !records.length" />
      <ErrorState v-else-if="error" :message="error" @retry="load" />
      <EmptyState
        v-else-if="!records.length"
        icon="price"
        title="No items found"
        description="No sellable items match this search."
      />
      <div v-else class="space-y-2">
        <div v-for="row in records" :key="row.name" class="bg-surface rounded-2xl p-3 flex items-center justify-between">
          <div class="min-w-0">
            <p class="font-display font-medium truncate">{{ row.item_name }}</p>
            <p class="text-xs text-ink-2">{{ row.item_code }} · {{ row.item_group }}</p>
          </div>
          <p class="font-display font-semibold shrink-0 ml-2">
            {{ row.rate != null ? `₹${row.rate}` : "Unpriced" }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue"
import { call } from "frappe-ui"
import AppBar from "@/components/AppBar.vue"
import EmptyState from "@/components/EmptyState.vue"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"

const records = ref([])
const loading = ref(true)
const error = ref("")
const searchText = ref("")
const showFilters = ref(false)
const warehouses = ref([])
const itemGroups = ref([])
const filters = reactive({ warehouse: "", customer_type: "", item_group: "" })
let timer = null

async function load() {
  loading.value = true
  error.value = ""
  try {
    const res = await call("field_sales.api.catalog.price_list", {
      search_text: searchText.value || undefined,
      warehouse: filters.warehouse || undefined,
      customer_type: filters.customer_type || undefined,
      item_group: filters.item_group || undefined,
    })
    records.value = res.records || []
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load the price list."
  } finally {
    loading.value = false
  }
}

function debouncedLoad() {
  clearTimeout(timer)
  timer = setTimeout(load, 350)
}

function clearFilter(key) {
  filters[key] = ""
  load()
}

const activeFilterChips = computed(() => {
  const chips = []
  if (filters.warehouse) {
    const w = warehouses.value.find((x) => x.name === filters.warehouse)
    chips.push({ key: "warehouse", label: w?.warehouse_name || filters.warehouse })
  }
  if (filters.customer_type) chips.push({ key: "customer_type", label: filters.customer_type })
  if (filters.item_group) chips.push({ key: "item_group", label: filters.item_group })
  return chips
})

onMounted(async () => {
  load()
  try {
    const [wh, groups] = await Promise.all([
      call("field_sales.api.catalog.warehouses"),
      call("frappe.client.get_list", { doctype: "Item Group", fields: ["name"], limit_page_length: 0 }),
    ])
    warehouses.value = wh || []
    itemGroups.value = groups || []
  } catch {
    // filters are optional - a failure here shouldn't block the list itself
  }
})
</script>

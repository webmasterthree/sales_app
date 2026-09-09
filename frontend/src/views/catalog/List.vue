<template>
  <div class="min-h-screen bg-ground pb-24">
    <AppBar title="Price List" fallback="/" />
    <div class="max-w-2xl mx-auto px-4 pt-3">
      <div class="flex gap-2 mb-3">
        <label class="flex-1 flex items-center gap-2 h-[46px] px-3.5 rounded-[14px] border border-rule bg-surface-2">
          <Icon name="search" :size="17" class="text-ink-3 shrink-0" />
          <input
            v-model="searchText"
            type="search"
            placeholder="Search by SKU or product"
            class="flex-1 min-w-0 bg-transparent outline-none text-sm"
            @input="debouncedLoad"
          />
        </label>
        <button
          type="button"
          class="relative shrink-0 w-[46px] h-[46px] rounded-[14px] border flex items-center justify-center"
          :class="activeFilterChips.length ? 'bg-accent-soft border-accent text-accent-ink' : 'bg-surface border-rule text-ink'"
          @click="filterSheetOpen = true"
        >
          <Icon name="filter" :size="18" />
          <span
            v-if="activeFilterChips.length"
            class="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-accent text-accent-fg text-[11px] font-bold flex items-center justify-center"
          >{{ activeFilterChips.length }}</span>
        </button>
      </div>

      <div v-if="activeFilterChips.length" class="flex gap-2 flex-wrap mb-3">
        <button
          v-for="chip in activeFilterChips"
          :key="chip.key"
          type="button"
          class="inline-flex items-center gap-1.5 rounded-full border border-accent bg-accent-soft px-3 py-1.5 text-xs font-display font-semibold text-accent-ink"
          @click="clearFilter(chip.key)"
        >
          {{ chip.label }}
          <Icon name="close" :size="11" />
        </button>
        <button type="button" class="rounded-full border border-rule px-3 py-1.5 text-xs font-display font-semibold text-ink-2" @click="clearAllFilters">
          Clear all
        </button>
      </div>

      <div v-if="!loading && !error && records.length" class="flex items-baseline justify-between mb-2 px-0.5">
        <p class="font-display font-bold text-sm text-ink">{{ listTitle }}</p>
        <p class="text-xs font-medium text-ink-3 tabular-nums">{{ records.length }} products</p>
      </div>

      <LoadingSkeleton v-if="loading && !records.length" />
      <ErrorState v-else-if="error" :message="error" @retry="load" />
      <EmptyState
        v-else-if="!records.length"
        icon="price"
        title="No products match"
        description="Nothing matches this search and your applied filters."
      />
      <div v-else class="rounded-[14px] border border-rule overflow-hidden bg-surface">
        <div class="grid grid-cols-[64px_1fr_70px_48px] gap-2 items-center bg-accent px-3 h-[42px]">
          <button type="button" class="text-left text-[11px] font-display font-extrabold text-accent-fg uppercase tracking-wide" @click="sortBy('item_code')">SKU{{ caret("item_code") }}</button>
          <button type="button" class="text-left text-[11px] font-display font-extrabold text-accent-fg uppercase tracking-wide" @click="sortBy('item_name')">Product{{ caret("item_name") }}</button>
          <button type="button" class="text-right text-[11px] font-display font-extrabold text-accent-fg uppercase tracking-wide" @click="sortBy('rate')">Price{{ caret("rate") }}</button>
          <span class="text-[11px] font-display font-extrabold text-accent-fg uppercase tracking-wide text-center">Type</span>
        </div>
        <div
          v-for="(row, i) in sortedRecords"
          :key="row.name"
          class="grid grid-cols-[64px_1fr_70px_48px] gap-2 items-center px-3 py-2.5 border-b border-rule-soft last:border-0"
          :class="i % 2 ? 'bg-surface-2/40' : ''"
        >
          <span class="font-mono text-[11px] text-ink-3 truncate">{{ row.item_code }}</span>
          <span class="text-[13px] font-display font-medium text-ink leading-snug truncate">{{ row.item_name }}</span>
          <span class="text-[13px] font-display font-bold text-ink text-right tabular-nums">{{ row.rate != null ? `₹${formatRate(row.rate)}` : "—" }}</span>
          <span
            class="justify-self-center text-[10px] font-display font-extrabold px-1.5 py-0.5 rounded"
            :style="{ background: groupTone(row.item_group).bg, color: groupTone(row.item_group).fg }"
            :title="row.item_group"
          >{{ groupInitials(row.item_group) }}</span>
        </div>
        <p class="text-center text-xs font-medium text-ink-3 py-3">Prices exclude GST</p>
      </div>
    </div>
  </div>

  <div
    v-if="filterSheetOpen"
    class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40"
    @click.self="filterSheetOpen = false"
  >
    <div class="bg-surface w-full sm:max-w-sm sm:rounded-2xl rounded-t-2xl overflow-hidden pb-safe">
      <div class="h-[3px]" style="background: linear-gradient(90deg, var(--fs-accent), var(--fs-chart))" aria-hidden="true" />
      <div class="flex justify-center pt-2 sm:hidden"><div class="w-10 h-1 rounded-full bg-rule"></div></div>
      <div class="px-5 pt-3 pb-4 max-h-[80vh] overflow-y-auto">
        <div class="flex items-center justify-between mb-4">
          <p class="text-lg font-display font-bold text-ink">Filter</p>
          <button type="button" class="w-9 h-9 rounded-full bg-surface-2 flex items-center justify-center" @click="filterSheetOpen = false">
            <Icon name="close" :size="14" />
          </button>
        </div>

        <label class="block text-xs font-display font-bold text-ink-2 mb-1.5">Warehouse</label>
        <select v-model="draftFilters.warehouse" class="w-full h-[48px] rounded-[13px] border border-rule bg-surface px-3.5 text-sm font-medium mb-5">
          <option value="">Select warehouse</option>
          <option v-for="w in warehouses" :key="w.name" :value="w.name">{{ w.warehouse_name || w.name }}</option>
        </select>

        <label class="block text-xs font-display font-bold text-ink-2 mb-1.5">Customer type</label>
        <div class="flex gap-2 mb-5">
          <button
            v-for="opt in [{ v: '', label: 'All' }, { v: 'DP', label: 'DP' }, { v: 'DL', label: 'DL' }]"
            :key="opt.v"
            type="button"
            class="flex-1 h-[46px] rounded-[13px] border-[1.5px] font-display font-bold text-sm"
            :class="draftFilters.customer_type === opt.v ? 'border-accent bg-accent-soft text-accent-ink' : 'border-rule text-ink-2'"
            @click="draftFilters.customer_type = opt.v"
          >{{ opt.label }}</button>
        </div>

        <!-- a real catalogue can have dozens of item groups - chips that
             wrap into a long scroll aren't practical at that count, unlike
             the app's other short, fixed-option filters. A select's closed
             control is still themed; only its OS-rendered open list isn't,
             which is the right trade-off here given how many options this
             one field actually has. -->
        <label class="block text-xs font-display font-bold text-ink-2 mb-1.5">Product category</label>
        <select v-model="draftFilters.item_group" class="w-full h-[48px] rounded-[13px] border border-rule bg-surface px-3.5 text-sm font-medium mb-6">
          <option value="">All categories</option>
          <option v-for="g in itemGroups" :key="g.name" :value="g.name">{{ g.name }}</option>
        </select>

        <div class="flex gap-2.5">
          <button type="button" class="flex-none h-[50px] px-5 rounded-[14px] border border-rule text-ink font-display font-bold" @click="resetDraftFilters">Reset</button>
          <button type="button" class="flex-1 h-[50px] rounded-[14px] bg-accent text-accent-fg font-display font-bold" @click="applyFilters">Show results</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue"
import { call } from "frappe-ui"
import AppBar from "@/components/AppBar.vue"
import Icon from "@/components/Icon.vue"
import EmptyState from "@/components/EmptyState.vue"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"

const records = ref([])
const loading = ref(true)
const error = ref("")
const searchText = ref("")
const filterSheetOpen = ref(false)
const warehouses = ref([])
const itemGroups = ref([])
const filters = reactive({ warehouse: "", customer_type: "", item_group: "" })
const draftFilters = reactive({ warehouse: "", customer_type: "", item_group: "" })
const sortKey = ref("item_code")
const sortDir = ref(1)
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

function clearAllFilters() {
  filters.warehouse = ""
  filters.customer_type = ""
  filters.item_group = ""
  load()
}

function resetDraftFilters() {
  draftFilters.warehouse = ""
  draftFilters.customer_type = ""
  draftFilters.item_group = ""
}

function applyFilters() {
  filters.warehouse = draftFilters.warehouse
  filters.customer_type = draftFilters.customer_type
  filters.item_group = draftFilters.item_group
  filterSheetOpen.value = false
  load()
}

function sortBy(key) {
  if (sortKey.value === key) {
    sortDir.value = -sortDir.value
  } else {
    sortKey.value = key
    sortDir.value = 1
  }
}

function caret(key) {
  if (sortKey.value !== key) return ""
  return sortDir.value === 1 ? " ↑" : " ↓"
}

// Sorted client-side over the loaded page - the backend's sortable fields
// (item_code/item_name/item_group) don't include price, since `rate` is
// computed per-row after the list query runs (see catalog.py's price_list),
// not a column the database can order by.
const sortedRecords = computed(() => {
  const key = sortKey.value
  const dir = sortDir.value
  return [...records.value].sort((a, b) => {
    const av = a[key], bv = b[key]
    if (av == null && bv == null) return 0
    if (av == null) return 1
    if (bv == null) return -1
    return av > bv ? dir : av < bv ? -dir : 0
  })
})

function formatRate(rate) {
  return Number(rate).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// Real item groups here ("Bakery Ingredients", "Emulsifiers", ...) aren't a
// fixed small enum the way the reference design's MP/BP/FP/TP codes were -
// so the pill is derived from whatever this catalogue actually has, not a
// fabricated tier scheme.
const GROUP_PALETTE = [
  { bg: "#EAF3DC", fg: "#456F17" },
  { bg: "#E5EEF7", fg: "#2B587F" },
  { bg: "#F7EEE1", fg: "#80501D" },
  { bg: "#EEE9F7", fg: "#543C7B" },
  { bg: "#FBEAE7", fg: "#8A2E22" },
  { bg: "#E3F2EF", fg: "#1E6B5C" },
]

function groupTone(group) {
  if (!group) return { bg: "#F0F2ED", fg: "#6E7668" }
  let hash = 0
  for (const ch of group) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return GROUP_PALETTE[hash % GROUP_PALETTE.length]
}

function groupInitials(group) {
  if (!group) return "—"
  return group
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase()
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

const listTitle = computed(() => {
  if (filters.warehouse) {
    const w = warehouses.value.find((x) => x.name === filters.warehouse)
    return `${w?.warehouse_name || filters.warehouse} price list`
  }
  return "Price list"
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

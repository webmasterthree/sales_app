<template>
  <div class="min-h-screen bg-ground pb-24">
    <AppBar
      :title="config.title"
      :subtitle="hasLoadedOnce ? `${total} result${total === 1 ? '' : 's'}` : ''"
      :fallback="config.fallback || '/'"
      :back="config.back !== false"
    />

    <div class="max-w-2xl mx-auto">
      <!-- search + filter trigger, collapsed by default so results are
           visible immediately instead of scrolling past every filter
           control first - tabs/mine-toggle/filters all live in the sheet
           below, opened on demand. -->
      <div v-if="config.searchable || hasFilterControls" class="flex gap-2 px-4 pt-3">
        <input
          v-if="config.searchable"
          v-model="searchText"
          type="search"
          placeholder="Search"
          class="flex-1 min-w-0 h-[48px] rounded-xl border border-rule bg-surface text-ink appearance-none px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
          @input="debouncedReload"
        />
        <button
          v-if="hasFilterControls"
          type="button"
          class="relative w-[48px] h-[48px] rounded-xl border flex items-center justify-center shrink-0"
          :class="activeFilterCount > 0 ? 'border-accent text-accent-ink' : 'border-rule text-ink-2'"
          aria-label="Filters"
          @click="filterSheetOpen = true"
        >
          <Icon name="filter" :size="18" />
          <span
            v-if="activeFilterCount > 0"
            class="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-accent text-accent-fg text-[10px] font-mono font-bold flex items-center justify-center"
          >{{ activeFilterCount }}</span>
        </button>
      </div>

      <!-- removable pills for whatever's actually filtering the list right
           now - tabs/mine-toggle aren't shown here since they always have
           some value selected (not meaningfully "clearable" the way an
           optional filter chip is). -->
      <div v-if="activeFilterPills.length" class="flex gap-1.5 px-4 pt-2 flex-wrap">
        <button
          v-for="p in activeFilterPills"
          :key="p.key"
          type="button"
          class="h-7 pl-2.5 pr-1.5 rounded-full text-xs font-display font-medium bg-accent-soft text-accent-ink flex items-center gap-1"
          @click="setFilter(p.key, '')"
        >
          {{ p.value }}
          <Icon name="close" :size="12" />
        </button>
      </div>

      <LoadingSkeleton v-if="loading && !records.length" class="mt-2" />
      <ErrorState
        v-else-if="error"
        class="mt-2"
        :message="error"
        @retry="reload"
      />
      <EmptyState
        v-else-if="!records.length"
        class="mt-2"
        :icon="config.emptyIcon || 'inbox'"
        :title="config.emptyTitle || 'Nothing to show'"
        :description="config.emptyDescription || 'Nothing matches right now.'"
      />
      <div v-else class="px-4 pt-3 space-y-2">
        <button
          v-for="(row, i) in records"
          :key="row.name"
          type="button"
          class="relative w-full text-left bg-surface rounded-2xl pl-4 pr-3 py-3 active:bg-surface-2 overflow-hidden"
          @click="openRow(row)"
        >
          <span
            class="absolute left-0 top-0 bottom-0 w-[3px]"
            :style="i % 2 === 0 ? 'background: var(--fs-accent)' : 'background: var(--fs-chart)'"
            aria-hidden="true"
          />
          <div class="flex items-start gap-3">
            <img
              v-if="config.cardImage && config.cardImage(row)"
              :src="config.cardImage(row)"
              alt=""
              class="w-12 h-12 rounded-lg object-cover shrink-0 border border-rule"
            />
            <div class="min-w-0 flex-1">
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <p class="font-display font-semibold text-ink truncate">{{ config.cardTitle(row) }}</p>
                  <p v-if="config.cardSubtitle" class="text-sm text-ink-2 truncate">{{ config.cardSubtitle(row) }}</p>
                </div>
                <div class="flex items-center gap-1.5 shrink-0">
                  <StatusPill v-if="config.cardBadge && config.cardBadge(row)" v-bind="config.cardBadge(row)" />
                  <StatusPill v-if="config.statusField" :status="row[config.statusField]" />
                </div>
              </div>
              <p v-if="config.cardMeta" class="text-xs text-ink-3 mt-1">{{ config.cardMeta(row) }}</p>
            </div>
          </div>
        </button>

        <div v-if="records.length < total" class="pt-1">
          <button
            type="button"
            class="w-full py-2 rounded-[10px] border border-rule text-sm font-display text-ink-2 disabled:opacity-50"
            :disabled="loading"
            @click="loadMore"
          >
            {{ loading ? "Loading…" : "Load more" }}
          </button>
        </div>
      </div>
    </div>

    <RouterLink
      v-if="config.createRouteName"
      :to="{ name: config.createRouteName }"
      class="fixed bottom-28 right-4 w-14 h-14 rounded-full bg-accent text-accent-fg text-2xl flex items-center justify-center shadow-lg z-40"
      aria-label="Create"
    >
      +
    </RouterLink>
  </div>

  <!-- filter sheet - tabs, mine/team toggle and every filter group live
       here instead of stacked inline, so the list itself stays scannable.
       Each control still applies immediately (same setTab/setIsSelf/setFilter
       as before) - this sheet is just where they now live, not a separate
       draft/apply state to keep in sync. -->
  <div
    v-if="filterSheetOpen"
    class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40"
    @click.self="filterSheetOpen = false"
  >
    <div class="bg-surface w-full sm:max-w-sm sm:rounded-2xl rounded-t-2xl overflow-hidden pb-safe max-h-[85vh] flex flex-col">
      <div class="h-[3px] shrink-0" style="background: linear-gradient(90deg, var(--fs-accent), var(--fs-chart))" aria-hidden="true" />
      <div class="flex justify-center pt-2 sm:hidden shrink-0"><div class="w-10 h-1 rounded-full bg-rule"></div></div>
      <div class="px-5 pt-3 pb-2 flex items-center justify-between shrink-0">
        <p class="text-lg font-display font-bold text-ink">Filters</p>
        <button
          v-if="activeFilterCount > 0"
          type="button"
          class="text-sm font-display font-semibold text-accent-ink"
          @click="clearAllFilters"
        >
          Clear all
        </button>
      </div>

      <div class="px-5 pb-4 overflow-y-auto space-y-5">
        <div v-if="config.tabs?.length">
          <p class="text-[10px] font-display font-semibold text-ink-3 uppercase tracking-wide mb-2">Status</p>
          <div class="flex gap-2">
            <button
              v-for="t in config.tabs"
              :key="t.key"
              type="button"
              class="flex-1 h-[42px] rounded-xl text-sm font-display font-semibold border"
              :class="tab === t.key ? 'bg-accent text-accent-fg border-transparent' : 'bg-surface text-ink-2 border-rule'"
              @click="setTab(t.key)"
            >
              {{ t.label }}
            </button>
          </div>
        </div>

        <div v-if="config.mineToggle">
          <p class="text-[10px] font-display font-semibold text-ink-3 uppercase tracking-wide mb-2">{{ config.mineLabel || "Items" }}</p>
          <div class="flex gap-2">
            <button
              type="button"
              class="flex-1 h-[42px] rounded-xl text-sm font-display font-semibold border"
              :class="isSelf === 1 ? 'bg-accent text-accent-fg border-transparent' : 'bg-surface text-ink-2 border-rule'"
              @click="setIsSelf(1)"
            >
              My {{ config.mineLabel || "items" }}
            </button>
            <button
              type="button"
              class="flex-1 h-[42px] rounded-xl text-sm font-display font-semibold border"
              :class="isSelf === 0 ? 'bg-accent text-accent-fg border-transparent' : 'bg-surface text-ink-2 border-rule'"
              @click="setIsSelf(0)"
            >
              My team's
            </button>
          </div>
        </div>

        <div v-for="f in config.filters || []" :key="f.key">
          <p class="text-[10px] font-display font-semibold text-ink-3 uppercase tracking-wide mb-2">{{ f.label }}</p>
          <div class="flex gap-2 flex-wrap">
            <button
              type="button"
              class="h-9 px-3.5 rounded-full text-sm font-display font-medium border"
              :class="!filterValues[f.key] ? 'bg-accent-soft text-accent-ink border-accent' : 'bg-surface text-ink-2 border-rule'"
              @click="setFilter(f.key, '')"
            >
              All
            </button>
            <button
              v-for="opt in f.options"
              :key="opt"
              type="button"
              class="h-9 px-3.5 rounded-full text-sm font-display font-medium border"
              :class="filterValues[f.key] === opt ? 'bg-accent-soft text-accent-ink border-accent' : 'bg-surface text-ink-2 border-rule'"
              @click="setFilter(f.key, opt)"
            >
              {{ opt }}
            </button>
          </div>
        </div>
      </div>

      <div class="px-5 pb-4 pt-1 shrink-0">
        <button
          type="button"
          class="w-full h-[50px] rounded-xl bg-accent text-accent-fg font-display font-bold text-sm"
          @click="filterSheetOpen = false"
        >
          Show {{ total }} result{{ total === 1 ? "" : "s" }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue"
import Icon from "@/components/Icon.vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"
import AppBar from "@/components/AppBar.vue"
import StatusPill from "@/components/StatusPill.vue"
import EmptyState from "@/components/EmptyState.vue"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"

const props = defineProps({
  // {
  //   title, method, searchable, tabs:[{key,label}], defaultTab,
  //   filters:[{key,label,options}], mineToggle, mineLabel,
  //   statusField, cardBadge(row) -> {status, tone} | null, cardImage(row), cardTitle(row), cardSubtitle(row), cardMeta(row),
  //   createRouteName, detailRouteName, fallback
  // }
  config: { type: Object, required: true },
})

const router = useRouter()

const records = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const hasLoadedOnce = ref(false)
const error = ref("")
const searchText = ref("")
const tab = ref(props.config.defaultTab || props.config.tabs?.[0]?.key || "")
const isSelf = ref(null)
const filterValues = reactive({})
for (const f of props.config.filters || []) filterValues[f.key] = ""

const filterSheetOpen = ref(false)
const hasFilterControls = computed(
  () => !!(props.config.tabs?.length || props.config.mineToggle || props.config.filters?.length)
)
// Only the optional `filters` chip groups count toward the badge/pills -
// tabs and the mine/team toggle always have some value selected, so
// treating them as "active" would show a nonzero badge even at rest.
const activeFilterCount = computed(
  () => (props.config.filters || []).filter((f) => filterValues[f.key]).length
)
const activeFilterPills = computed(() =>
  (props.config.filters || [])
    .filter((f) => filterValues[f.key])
    .map((f) => ({ key: f.key, value: filterValues[f.key] }))
)

function clearAllFilters() {
  for (const f of props.config.filters || []) filterValues[f.key] = ""
  reload()
}

let debounceTimer = null
function debouncedReload() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(reload, 350)
}

function setTab(key) {
  tab.value = key
  reload()
}

function setIsSelf(val) {
  isSelf.value = isSelf.value === val ? null : val
  reload()
}

function setFilter(key, value) {
  filterValues[key] = value
  reload()
}

async function fetchPage(pageNo) {
  loading.value = true
  error.value = ""
  try {
    const args = {
      current_page: pageNo,
      limit: 20,
      search_text: searchText.value || undefined,
      tab: tab.value || undefined,
    }
    if (isSelf.value !== null) args.is_self = isSelf.value
    for (const [k, v] of Object.entries(filterValues)) {
      if (v) args[k] = v
    }
    const res = await call(props.config.method, args)
    if (pageNo === 1) records.value = res.records || []
    else records.value = records.value.concat(res.records || [])
    total.value = res.total_count ?? records.value.length
    page.value = pageNo
    hasLoadedOnce.value = true
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load this list."
  } finally {
    loading.value = false
  }
}

function reload() {
  fetchPage(1)
}

function loadMore() {
  fetchPage(page.value + 1)
}

function openRow(row) {
  if (props.config.onOpen) return props.config.onOpen(row, router)
  if (props.config.detailRouteName) {
    router.push({ name: props.config.detailRouteName, params: { name: row.name } })
  }
}

defineExpose({ reload })

onMounted(reload)
</script>

<template>
  <div class="min-h-screen bg-ground pb-24">
    <AppBar :title="config.title" :fallback="config.fallback || '/'" :back="config.back !== false" />

    <div class="max-w-2xl mx-auto">
      <!-- search -->
      <div v-if="config.searchable" class="px-4 pt-3">
        <input
          v-model="searchText"
          type="search"
          placeholder="Search"
          class="w-full h-[52px] rounded-[10px] border border-rule bg-surface text-ink appearance-none px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
          @input="debouncedReload"
        />
      </div>

      <!-- tabs -->
      <div v-if="config.tabs?.length" class="flex gap-2 px-4 pt-3 overflow-x-auto">
        <button
          v-for="t in config.tabs"
          :key="t.key"
          type="button"
          class="px-3 py-1.5 rounded-full text-sm font-display whitespace-nowrap border"
          :class="tab === t.key ? 'bg-accent text-accent-fg border-accent' : 'bg-surface text-ink-2 border-rule'"
          @click="setTab(t.key)"
        >
          {{ t.label }}
        </button>
      </div>

      <!-- mine / team toggle - a labelled segmented control, never a bare switch -->
      <div v-if="config.mineToggle" class="px-4 pt-3">
        <div class="inline-flex rounded-[10px] border border-rule overflow-hidden text-sm font-display">
          <button
            type="button"
            class="px-3 py-1.5"
            :class="isSelf === 1 ? 'bg-accent text-accent-fg' : 'bg-surface-2 text-ink-2'"
            @click="setIsSelf(1)"
          >
            My {{ config.mineLabel || "items" }}
          </button>
          <button
            type="button"
            class="px-3 py-1.5 border-l border-rule"
            :class="isSelf === 0 ? 'bg-accent text-accent-fg' : 'bg-surface-2 text-ink-2'"
            @click="setIsSelf(0)"
          >
            My team's
          </button>
        </div>
      </div>

      <!-- filters - toggle buttons, not a native <select>: the closed
           control can be themed, but a native dropdown's expanded list is
           rendered by the OS/browser itself and always shows the device's
           own default colors (a jarring blue highlight, on most platforms)
           no matter what the rest of the app looks like. Same button style
           already used for tabs just above. -->
      <div v-if="config.filters?.length" class="px-4 pt-3 space-y-2">
        <div v-for="f in config.filters" :key="f.key">
          <p class="text-xs font-display font-medium text-ink-3 mb-1">{{ f.label }}</p>
          <div class="flex gap-2 overflow-x-auto">
            <button
              type="button"
              class="px-3 py-1.5 rounded-full text-sm font-display whitespace-nowrap border"
              :class="!filterValues[f.key] ? 'bg-accent text-accent-fg border-accent' : 'bg-surface text-ink-2 border-rule'"
              @click="setFilter(f.key, '')"
            >
              All
            </button>
            <button
              v-for="opt in f.options"
              :key="opt"
              type="button"
              class="px-3 py-1.5 rounded-full text-sm font-display whitespace-nowrap border"
              :class="filterValues[f.key] === opt ? 'bg-accent text-accent-fg border-accent' : 'bg-surface text-ink-2 border-rule'"
              @click="setFilter(f.key, opt)"
            >
              {{ opt }}
            </button>
          </div>
        </div>
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
          v-for="row in records"
          :key="row.name"
          type="button"
          class="w-full text-left bg-surface rounded-2xl border border-rule p-4 active:opacity-80"
          @click="openRow(row)"
        >
          <div class="flex items-start gap-3">
            <img
              v-if="config.cardImage && config.cardImage(row)"
              :src="config.cardImage(row)"
              alt=""
              class="w-14 h-14 rounded-xl object-cover shrink-0 border border-rule"
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

        <div v-if="records.length < total" class="pt-2">
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
</template>

<script setup>
import { onMounted, reactive, ref } from "vue"
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
const error = ref("")
const searchText = ref("")
const tab = ref(props.config.defaultTab || props.config.tabs?.[0]?.key || "")
const isSelf = ref(null)
const filterValues = reactive({})
for (const f of props.config.filters || []) filterValues[f.key] = ""

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

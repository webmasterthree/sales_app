<template>
  <div class="min-h-screen bg-ground pb-24">
    <AppBar title="Marketing Collateral" fallback="/" />

    <div class="max-w-2xl mx-auto px-4 pt-3 space-y-3">
      <input
        v-model="searchText"
        type="search"
        placeholder="Search by collateral name"
        class="w-full h-[52px] rounded-[10px] border border-rule bg-surface text-ink appearance-none px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
        @input="debouncedReload"
      />

      <LoadingSkeleton v-if="loading && !records.length" />
      <ErrorState v-else-if="error" :message="error" @retry="reload" />
      <EmptyState
        v-else-if="!records.length"
        icon="digital"
        title="Nothing published"
        description="No collateral has been published for sharing yet."
      />

      <!-- Card layout mirrors the Flutter Digital Marketing Collateral screen:
           a thumbnail preview, a file-type badge, and Download/Open actions.
           The generic ListView component (a plain text row list, used by
           Sample/Collateral requests) has no thumbnail or action-button
           support, so this stays a bespoke page rather than widening that
           shared component for one module. -->
      <div v-else class="space-y-3">
        <div v-for="row in records" :key="row.name" class="bg-surface rounded-2xl border border-rule overflow-hidden">
          <div v-if="row.thumbnail" class="bg-surface-2">
            <img :src="row.thumbnail" :alt="row.collateral_name || row.name" class="w-full max-h-48 object-cover" />
          </div>
          <div class="p-4 space-y-2">
            <div class="flex items-start justify-between gap-2">
              <p class="font-display font-semibold text-ink truncate">{{ row.collateral_name || row.name }}</p>
              <span
                v-if="fileType(row)"
                class="text-[10px] font-display px-2 py-0.5 rounded-full border border-accent text-accent-ink shrink-0"
              >
                {{ fileType(row) }}
              </span>
            </div>
            <p v-if="row.segment" class="text-xs text-ink-3">{{ row.segment }}</p>
            <p v-if="row.description" class="text-xs text-ink-2 line-clamp-2">{{ row.description }}</p>

            <div class="flex gap-2 pt-1">
              <a
                v-if="row.attachment"
                :href="row.attachment"
                target="_blank"
                rel="noopener"
                download
                class="flex-1 text-center py-2 rounded-[10px] bg-accent text-accent-fg text-sm font-display font-medium"
              >
                Download
              </a>
              <a
                v-if="row.attachment"
                :href="row.attachment"
                target="_blank"
                rel="noopener"
                class="px-4 py-2 rounded-[10px] border border-rule text-sm font-display text-ink-2"
              >
                Open
              </a>
              <p v-if="!row.attachment" class="text-xs text-ink-3">No file attached</p>
            </div>
          </div>
        </div>

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
  </div>
</template>

<script setup>
import { ref } from "vue"
import { call } from "frappe-ui"
import AppBar from "@/components/AppBar.vue"
import EmptyState from "@/components/EmptyState.vue"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"

const records = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const error = ref("")
const searchText = ref("")

let debounceTimer = null
function debouncedReload() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(reload, 350)
}

function fileType(row) {
  if (!row.attachment) return ""
  const ext = row.attachment.split(".").pop()
  return (ext || "").split("?")[0].toUpperCase()
}

async function fetchPage(pageNo) {
  loading.value = true
  error.value = ""
  try {
    const res = await call("field_sales.api.requests.collateral_library", {
      current_page: pageNo,
      limit: 20,
      search_text: searchText.value || undefined,
    })
    if (pageNo === 1) records.value = res.records || []
    else records.value = records.value.concat(res.records || [])
    total.value = res.total_count ?? records.value.length
    page.value = pageNo
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load the collateral library."
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

reload()
</script>

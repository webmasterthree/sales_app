<template>
  <div class="min-h-screen bg-ground pb-24">
    <header class="pt-safe px-4 pt-4 pb-2 max-w-2xl mx-auto">
      <h1 class="font-display text-xl font-bold">Notifications</h1>
    </header>

    <div class="max-w-2xl mx-auto px-4">
      <div class="flex gap-2 mb-3">
        <button
          v-for="t in ['all', 'unread']"
          :key="t"
          type="button"
          class="px-3 py-1.5 rounded-full text-sm font-display capitalize"
          :class="tab === t ? 'bg-accent text-accent-fg' : 'bg-surface-2 text-ink-2'"
          @click="setTab(t)"
        >
          {{ t }}
        </button>
        <button
          v-if="records.length"
          type="button"
          class="ml-auto text-sm text-accent-ink font-display"
          @click="markAll"
        >
          Mark all read
        </button>
      </div>

      <LoadingSkeleton v-if="loading" />
      <ErrorState v-else-if="error" :message="error" @retry="load" />
      <EmptyState
        v-else-if="!records.length"
        icon="bell"
        title="No notifications"
        :description="tab === 'unread' ? 'Nothing unread right now.' : 'Nothing here yet.'"
      />
      <div v-else class="space-y-2">
        <button
          v-for="n in records"
          :key="n.name"
          type="button"
          class="w-full text-left bg-surface rounded-2xl p-3 active:opacity-80"
          :class="!n.read ? 'border-l-4 border-accent' : ''"
          @click="markRead(n)"
        >
          <p class="font-display text-sm font-medium">{{ n.subject }}</p>
          <p class="text-xs text-ink-3 mt-1">{{ n.from_user }} · {{ n.creation }}</p>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue"
import { call } from "frappe-ui"
import { useRouter } from "vue-router"
import EmptyState from "@/components/EmptyState.vue"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"
import { refreshUnreadCount } from "@/data/notifications"

// Where a notification's document_type routes to, matching the `name`s
// declared in router/index.js. A doctype not listed here (or a document
// that's since been deleted) falls back to marking the notification read
// with no navigation, rather than throwing.
const DETAIL_ROUTES = {
  "Field Visit": "VisitDetail",
  "Customer Onboarding": "OnboardingDetail",
  "Product Demo": "DemoDetail",
  "Sample Request": "SampleRequestDetail",
  "Collateral Request": "CollateralRequestDetail",
  "Issue": "ComplaintDetail",
  "Sales Order": "OrderDetail",
  "Customer": "CustomerDetail",
}

const router = useRouter()
const records = ref([])
const loading = ref(true)
const error = ref("")
const tab = ref("all")

async function load() {
  loading.value = true
  error.value = ""
  try {
    const res = await call("field_sales.api.home.notifications", { unread_only: tab.value === "unread" ? 1 : 0, limit: 50 })
    records.value = res.records || []
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load notifications."
  } finally {
    loading.value = false
  }
}

function setTab(t) {
  tab.value = t
  load()
}

async function markRead(n) {
  if (!n.read) {
    try {
      await call("field_sales.api.home.mark_notification_read", { name: n.name })
      n.read = 1
      refreshUnreadCount()
    } catch (err) {
      error.value = err.messages?.[0] || err.message
    }
  }
  navigateToRecord(n)
}

// Route to the notification's own record, when this app has a detail view
// for its doctype. A notification about something this app doesn't render
// (or whose document has since been deleted) just stays here, marked read -
// no route, no error.
function navigateToRecord(n) {
  const routeName = DETAIL_ROUTES[n.document_type]
  if (!routeName || !n.document_name) return
  router.push({ name: routeName, params: { name: n.document_name } })
}

async function markAll() {
  try {
    await call("field_sales.api.home.mark_notification_read", { all_of_them: 1 })
    records.value.forEach((n) => (n.read = 1))
    refreshUnreadCount()
  } catch (err) {
    error.value = err.messages?.[0] || err.message
  }
}

onMounted(load)
</script>

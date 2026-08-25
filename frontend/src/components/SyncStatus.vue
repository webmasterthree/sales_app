<template>
  <div
    v-if="syncState !== 'synced' || !online"
    class="flex items-center gap-1 text-xs font-display px-2 py-1 rounded-full shrink-0"
    :class="badgeClass"
    :title="lastError || undefined"
  >
    <span class="w-1.5 h-1.5 rounded-full" :class="dotClass" />
    {{ label }}
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue"
import { syncState, pendingCount, lastError } from "@/composables/offlineQueue"

const online = ref(navigator.onLine)
function setOnline() { online.value = true }
function setOffline() { online.value = false }
onMounted(() => {
  window.addEventListener("online", setOnline)
  window.addEventListener("offline", setOffline)
})
onUnmounted(() => {
  window.removeEventListener("online", setOnline)
  window.removeEventListener("offline", setOffline)
})

const label = computed(() => {
  if (!online.value) return pendingCount.value ? `Offline · ${pendingCount.value} queued` : "Offline"
  if (syncState.value === "syncing") return "Syncing…"
  if (syncState.value === "failed") return "Sync failed"
  if (syncState.value === "pending") return `${pendingCount.value} pending`
  return ""
})

const badgeClass = computed(() => {
  if (!online.value) return "bg-surface-2 text-ink-2"
  if (syncState.value === "failed") return "bg-crit/10 text-crit"
  if (syncState.value === "syncing" || syncState.value === "pending") return "bg-warn/10 text-warn"
  return "bg-good/10 text-good"
})

const dotClass = computed(() => {
  if (!online.value) return "bg-ink-3"
  if (syncState.value === "failed") return "bg-crit"
  if (syncState.value === "syncing" || syncState.value === "pending") return "bg-warn animate-pulse"
  return "bg-good"
})
</script>

<template>
  <Teleport to="body">
    <div class="fixed top-0 inset-x-0 z-[100] flex flex-col items-center gap-2 px-4 pt-safe pointer-events-none" style="padding-top: max(env(safe-area-inset-top, 0px), 12px)">
      <TransitionGroup name="push-toast">
        <button
          v-for="t in toasts"
          :key="t.id"
          type="button"
          class="pointer-events-auto w-full max-w-md text-left bg-surface border border-rule rounded-2xl shadow-lg p-3 flex items-start gap-3"
          @click="open(t)"
        >
          <span class="w-9 h-9 rounded-lg bg-accent-soft text-accent-ink flex items-center justify-center shrink-0" aria-hidden="true">
            <Icon name="bell" :size="16" />
          </span>
          <span class="min-w-0 flex-1">
            <span class="block font-display font-semibold text-sm text-ink truncate">{{ t.title }}</span>
            <span class="block text-xs text-ink-2 line-clamp-2">{{ t.body }}</span>
          </span>
        </button>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { ref } from "vue"
import { useRouter } from "vue-router"
import Icon from "@/components/Icon.vue"

const router = useRouter()
const toasts = ref([])
let nextId = 1

function push(payload) {
  const id = nextId++
  toasts.value.push({
    id,
    title: payload?.title || "Notification",
    body: payload?.body || "",
    clickAction: payload?.click_action || "",
  })
  setTimeout(() => dismiss(id), 6000)
}

function dismiss(id) {
  toasts.value = toasts.value.filter((t) => t.id !== id)
}

function open(t) {
  dismiss(t.id)
  if (!t.clickAction) return
  try {
    const url = new URL(t.clickAction, window.location.origin)
    router.push(url.pathname.replace(/^\/field_sales_app/, "") || "/")
  } catch {
    // not a URL we can route internally - ignore rather than navigate away
  }
}

defineExpose({ push })
</script>

<style scoped>
.push-toast-enter-active,
.push-toast-leave-active {
  transition: all 0.25s ease;
}
.push-toast-enter-from {
  opacity: 0;
  transform: translateY(-12px);
}
.push-toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>

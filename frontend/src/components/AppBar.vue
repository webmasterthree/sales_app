<template>
  <header class="sticky top-0 z-30 bg-surface border-b border-rule pt-safe">
    <div class="flex items-center gap-2 px-2 py-2 max-w-2xl mx-auto">
      <button
        v-if="back"
        type="button"
        class="flex items-center justify-center w-11 h-11 rounded-full active:bg-accent-soft shrink-0"
        aria-label="Back"
        @click="onBack"
      >
        <Icon name="chevron-left" :size="22" />
      </button>
      <div class="flex-1 min-w-0">
        <h1 class="font-display font-semibold text-base truncate">{{ title }}</h1>
        <p v-if="subtitle" class="text-xs text-ink-2 truncate">{{ subtitle }}</p>
      </div>
      <SyncStatus />
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup>
import { useRouter } from "vue-router"
import SyncStatus from "@/components/SyncStatus.vue"
import Icon from "@/components/Icon.vue"

const props = defineProps({
  title: { type: String, default: "" },
  subtitle: { type: String, default: "" },
  back: { type: Boolean, default: true },
  fallback: { type: String, default: "/" },
})

const router = useRouter()

function onBack() {
  if (window.history.state?.back) router.back()
  else router.replace(props.fallback)
}
</script>

<template>
  <div class="flex flex-col items-center justify-center text-center px-6 py-12 gap-3">
    <div class="w-14 h-14 rounded-full bg-crit/10 flex items-center justify-center text-crit">
      <Icon name="alert-circle" :size="26" />
    </div>
    <h3 class="font-display font-semibold text-ink">{{ title }}</h3>
    <p class="text-sm text-ink-2 max-w-xs">{{ message }}</p>
    <button
      type="button"
      class="mt-2 px-4 py-2 rounded-[10px] bg-accent text-accent-fg text-sm font-display font-medium active:opacity-80"
      @click="$emit('retry')"
    >
      Try again
    </button>
  </div>
</template>

<script setup>
import Icon from "@/components/Icon.vue"

defineProps({
  title: { type: String, default: "Something went wrong" },
  message: { type: String, default: "Could not reach the server. Check your connection and try again." },
})
defineEmits(["retry"])
</script>

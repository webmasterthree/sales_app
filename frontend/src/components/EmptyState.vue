<template>
  <div class="flex flex-col items-center justify-center text-center px-6 py-12 gap-3">
    <div class="w-14 h-14 rounded-full bg-surface-2 text-ink-3 flex items-center justify-center">
      <Icon :name="icon" :size="26" />
    </div>
    <h3 class="font-display font-semibold text-ink">{{ title }}</h3>
    <p v-if="description" class="text-sm text-ink-2 max-w-xs">{{ description }}</p>
    <button
      v-if="actionLabel"
      type="button"
      class="mt-2 px-4 py-2 rounded-[10px] bg-accent text-accent-fg text-sm font-display font-medium active:opacity-80"
      @click="$emit('action')"
    >
      {{ actionLabel }}
    </button>
  </div>
</template>

<script setup>
import Icon from "@/components/Icon.vue"

defineProps({
  icon: { type: String, default: "inbox" },
  title: { type: String, default: "Nothing here yet" },
  description: { type: String, default: "" },
  actionLabel: { type: String, default: "" },
})
defineEmits(["action"])
</script>

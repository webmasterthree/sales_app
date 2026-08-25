<template>
  <div class="px-4 py-3 space-y-3" aria-busy="true" aria-label="Loading">
    <div v-for="i in rows" :key="i" class="bg-surface rounded-2xl border border-rule p-4 space-y-2 animate-pulse">
      <div class="h-3 w-1/3 bg-surface-2 rounded" />
      <div class="h-4 w-2/3 bg-surface-2 rounded" />
      <div class="h-3 w-1/2 bg-surface-2 rounded" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  rows: { type: Number, default: 4 },
})
</script>

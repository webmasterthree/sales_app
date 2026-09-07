<template>
  <div
    v-if="modelValue"
    class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40"
    @click.self="$emit('cancel')"
  >
    <div class="bg-surface w-full sm:max-w-sm sm:rounded-2xl rounded-t-2xl overflow-hidden pb-safe">
      <div class="flex justify-center pt-2 sm:hidden">
        <div class="w-10 h-1 rounded-full bg-rule"></div>
      </div>
      <div class="px-5 pt-3 pb-4 text-center">
        <p class="text-xs font-display font-semibold text-accent-ink uppercase tracking-wide mb-2">
          {{ modelValue.label }}
        </p>
        <p class="text-2xl font-display font-bold text-ink">{{ modelValue.time }}</p>
        <p class="text-sm text-ink-3 mt-0.5">{{ modelValue.date }}</p>
        <p class="text-xs text-ink-2 mt-2">
          Latitude: {{ modelValue.lat.toFixed(5) }}°, Longitude: {{ modelValue.lon.toFixed(5) }}°
        </p>
      </div>
      <iframe
        class="w-full h-48 border-0 border-t border-rule"
        :src="mapEmbedUrl(modelValue.lat, modelValue.lon)"
        loading="lazy"
        title="Location"
      />
      <div class="p-3 space-y-2">
        <button
          type="button"
          class="w-full h-[48px] rounded-[10px] bg-accent text-accent-fg text-sm font-display font-medium"
          @click="$emit('confirm')"
        >
          {{ modelValue.confirmLabel || "Confirm" }}
        </button>
        <button
          type="button"
          class="w-full h-[40px] rounded-[10px] text-sm font-display text-ink-2"
          @click="$emit('cancel')"
        >
          Cancel
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
// The actual check-in/out or attendance punch happens only once the rep
// taps Confirm here - this map is the last thing they see before it's
// committed, not a receipt shown afterwards, so a wrong-looking pin can
// still be caught and cancelled before it's recorded.
defineProps({ modelValue: { type: Object, default: null } })
defineEmits(["confirm", "cancel"])

function mapEmbedUrl(lat, lon) {
  const d = 0.003
  const bbox = `${lon - d},${lat - d},${lon + d},${lat + d}`
  return `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&marker=${lat},${lon}`
}
</script>

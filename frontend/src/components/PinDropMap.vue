<template>
  <div>
    <div ref="mapEl" :style="{ height: `${height}px` }" class="w-full rounded-2xl overflow-hidden border border-rule" />
    <p class="font-mono text-[11px] text-ink-3 mt-1.5">
      <template v-if="modelValue">{{ modelValue.lat.toFixed(5) }}° N, {{ modelValue.lng.toFixed(5) }}° E</template>
      <template v-else>Tap the map to drop a pin</template>
    </p>
  </div>
</template>

<script setup>
// A real tap/drag-to-place map, backed by free OpenStreetMap tiles (no API
// key, no billing) - the reference design's "map" was a decorative striped
// placeholder with a hardcoded coordinate, not an actual interactive one.
// Leaflet's default marker icon is served from relative image paths that
// break once bundled, so this uses a plain SVG divIcon instead of importing
// leaflet's marker-icon assets.
import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue"
import L from "leaflet"
import "leaflet/dist/leaflet.css"

const props = defineProps({
  modelValue: { type: Object, default: null }, // { lat, lng } | null
  center: { type: Object, default: () => ({ lat: 20.5937, lng: 78.9629 }) }, // India, used only when no pin/GPS yet
  height: { type: Number, default: 220 },
})
const emit = defineEmits(["update:modelValue"])

const mapEl = ref(null)
const map = shallowRef(null)
const marker = shallowRef(null)

const pinIcon = L.divIcon({
  className: "",
  html: `<svg width="26" height="30" viewBox="0 0 26 30" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M13 29C13 29 24 18.5 24 12A11 11 0 1 0 2 12C2 18.5 13 29 13 29Z" fill="var(--fs-accent)" stroke="var(--fs-accent-ink)" stroke-width="1.5"/>
    <circle cx="13" cy="12" r="4" fill="#FFFFFF"/>
  </svg>`,
  iconSize: [26, 30],
  iconAnchor: [13, 29],
})

function setPin(lat, lng) {
  emit("update:modelValue", { lat, lng })
  if (marker.value) {
    marker.value.setLatLng([lat, lng])
  } else if (map.value) {
    marker.value = L.marker([lat, lng], { icon: pinIcon, draggable: true }).addTo(map.value)
    marker.value.on("dragend", () => {
      const { lat: la, lng: ln } = marker.value.getLatLng()
      emit("update:modelValue", { lat: la, lng: ln })
    })
  }
}

onMounted(() => {
  const start = props.modelValue || props.center
  map.value = L.map(mapEl.value, { attributionControl: true }).setView([start.lat, start.lng], props.modelValue ? 16 : 5)
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map.value)

  if (props.modelValue) setPin(props.modelValue.lat, props.modelValue.lng)

  map.value.on("click", (e) => setPin(e.latlng.lat, e.latlng.lng))
})

// If a GPS fix or saved location arrives after mount (async), recentre once.
watch(() => props.modelValue, (v) => {
  if (v && map.value && !marker.value) {
    map.value.setView([v.lat, v.lng], 16)
    setPin(v.lat, v.lng)
  }
})

onBeforeUnmount(() => {
  map.value?.remove()
})
</script>

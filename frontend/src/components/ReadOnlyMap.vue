<template>
  <div ref="mapEl" :style="{ height: `${height}px` }" class="w-full rounded-xl overflow-hidden border border-rule" />
</template>

<script setup>
// A fixed, non-interactive pin - for showing where a visit was actually
// recorded (e.g. on a manager's report), not for picking a location. See
// PinDropMap.vue for the tap/drag-to-place version used when a rep is
// setting a location themselves.
import { onBeforeUnmount, onMounted, shallowRef, ref } from "vue"
import L from "leaflet"
import "leaflet/dist/leaflet.css"

const props = defineProps({
  lat: { type: Number, required: true },
  lng: { type: Number, required: true },
  height: { type: Number, default: 160 },
})

const mapEl = ref(null)
const map = shallowRef(null)

const pinIcon = L.divIcon({
  className: "",
  html: `<svg width="26" height="30" viewBox="0 0 26 30" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M13 29C13 29 24 18.5 24 12A11 11 0 1 0 2 12C2 18.5 13 29 13 29Z" fill="var(--fs-accent)" stroke="var(--fs-accent-ink)" stroke-width="1.5"/>
    <circle cx="13" cy="12" r="4" fill="#FFFFFF"/>
  </svg>`,
  iconSize: [26, 30],
  iconAnchor: [13, 29],
})

onMounted(() => {
  map.value = L.map(mapEl.value, {
    attributionControl: true,
    dragging: false,
    scrollWheelZoom: false,
    doubleClickZoom: false,
    touchZoom: false,
    zoomControl: false,
  }).setView([props.lat, props.lng], 16)
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map.value)
  L.marker([props.lat, props.lng], { icon: pinIcon }).addTo(map.value)
})

onBeforeUnmount(() => {
  map.value?.remove()
})
</script>

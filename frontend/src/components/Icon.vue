<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    aria-hidden="true"
    v-html="PATHS[name] || PATHS.square"
  />
</template>

<script setup>
// Single source of truth for every icon in the app. Stroke-based, 24x24
// viewBox, stroke="currentColor" / stroke-width="2", no fill - matching the
// hand-drawn icons already in Home.vue (bell, needs-your-action check-in,
// pending-approval clock, chevron). Nothing here is copy-pasted into
// templates; views ask for an icon by name and colour/size it with normal
// classes/props, same as the rest of the design system.
defineProps({
  name: { type: String, default: "square" },
  size: { type: [Number, String], default: 20 },
})

const PATHS = {
  // nav / chrome
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V9.5"/>',
  "bar-chart": '<path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/>',
  bell: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.58-6 8-6s8 2 8 6"/>',
  "chevron-left": '<path d="M15 18l-6-6 6-6"/>',
  "chevron-right": '<path d="M9 18l6-6-6-6"/>',
  close: '<path d="M18 6 6 18"/><path d="M6 6l12 12"/>',
  plus: '<path d="M12 5v14"/><path d="M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',

  // module grid concepts (field_sales.api.home.module_grid icon names)
  visit: '<path d="M21 10c0 6.5-9 12-9 12s-9-5.5-9-12a9 9 0 0 1 18 0Z"/><circle cx="12" cy="10" r="3"/>',
  order: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><path d="M9 13h6"/><path d="M9 17h6"/>',
  customer: '<path d="M3 9.5 5 4h14l2 5.5"/><path d="M4 10v9a1 1 0 0 0 1 1h4v-6h6v6h4a1 1 0 0 0 1-1v-9"/><path d="M3 10h18"/>',
  kyc: '<rect x="2" y="5" width="20" height="14" rx="2"/><circle cx="8" cy="11" r="2"/><path d="M5.5 16c0-1.4 1.1-2.5 2.5-2.5s2.5 1.1 2.5 2.5"/><path d="M14 10h5"/><path d="M14 14h5"/>',
  price: '<path d="M20.59 13.41 13.42 20.58a2 2 0 0 1-2.83 0l-8.17-8.17A2 2 0 0 1 2 11V4a2 2 0 0 1 2-2h7a2 2 0 0 1 1.41.59l8.18 8.18a2 2 0 0 1 0 2.83Z"/><path d="M7 7h.01"/>',
  requisitions: '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4a2 2 0 0 0 1-1.73Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
  sample: '<path d="M9 3h6"/><path d="M10 3v6.2L4.9 18a2 2 0 0 0 1.8 3h10.6a2 2 0 0 0 1.8-3L14 9.2V3"/>',
  collateral: '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4a2 2 0 0 0 1-1.73Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
  demo: '<circle cx="12" cy="12" r="10"/><path d="m10 8 6 4-6 4Z"/>',
  scheme: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  complaint: '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  digital: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/>',
  report: '<path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/>',

  // state icons
  "check-circle": '<path d="M21.5 11.1V12a9.5 9.5 0 1 1-5.6-8.68"/><path d="M21.5 4 12 13.5l-3-3"/>',
  "alert-circle": '<circle cx="12" cy="12" r="9.5"/><path d="M12 7.5v5"/><path d="M12 16.5h.01"/>',
  inbox: '<path d="M21.5 12h-5.4l-1.6 2.5h-4l-1.6-2.5H2.5"/><path d="M5.6 5.4 2.5 12v5.5a1.5 1.5 0 0 0 1.5 1.5h16a1.5 1.5 0 0 0 1.5-1.5V12l-3.1-6.6a1.5 1.5 0 0 0-1.36-.9H6.96a1.5 1.5 0 0 0-1.36.9Z"/>',
  square: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  smartphone: '<rect x="6" y="2.5" width="12" height="19" rx="2"/><path d="M11.5 18h1"/>',
  camera: '<path d="M4 8h3l1.5-2.5h7L17 8h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z"/><circle cx="12" cy="13.5" r="3.5"/>',
}
</script>

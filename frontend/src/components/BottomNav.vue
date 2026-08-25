<template>
  <nav class="fixed bottom-0 inset-x-0 z-40 pb-safe pointer-events-none">
    <div
      class="relative grid grid-cols-4 items-center max-w-md mx-4 sm:mx-auto mb-3 bg-surface rounded-full shadow-lg border border-rule/60 px-2 pointer-events-auto"
    >
      <RouterLink
        v-for="tab in tabs"
        :key="tab.name"
        :to="{ name: tab.name }"
        class="relative flex items-center justify-center py-3"
        :aria-label="tab.label"
      >
        <span
          class="flex items-center justify-center rounded-full transition-all"
          :class="isActive(tab.name)
            ? 'w-11 h-11 -mt-6 bg-accent text-accent-fg shadow-md'
            : 'w-9 h-9 text-ink-3'"
          aria-hidden="true"
        ><Icon :name="tab.icon" :size="isActive(tab.name) ? 20 : 18" /></span>
        <span class="sr-only">{{ tab.label }}</span>
        <span
          v-if="tab.name === 'Notifications' && unread > 0"
          class="absolute top-1 right-4 min-w-[16px] h-4 px-1 rounded-full bg-crit text-white text-[10px] flex items-center justify-center"
        >{{ unread > 9 ? '9+' : unread }}</span>
      </RouterLink>
    </div>
  </nav>
</template>

<script setup>
import { useRoute } from "vue-router"
import Icon from "@/components/Icon.vue"
import { unreadCount } from "@/data/notifications"

const route = useRoute()
const unread = unreadCount

const tabs = [
  { name: "Home", label: "Home", icon: "home" },
  { name: "Performance", label: "Performance", icon: "bar-chart" },
  { name: "Notifications", label: "Alerts", icon: "bell" },
  { name: "Profile", label: "Profile", icon: "user" },
]

function isActive(name) {
  return route.name === name
}
</script>

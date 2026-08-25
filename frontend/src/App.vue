<template>
  <div class="min-h-screen bg-ground text-ink font-sans">
    <div :class="showBottomNav ? 'pb-24' : ''">
      <router-view v-slot="{ Component, route }">
        <component :is="Component" :key="route.fullPath" />
      </router-view>
    </div>
    <BottomNav v-if="showBottomNav" />
    <InstallPrompt />
  </div>
</template>

<script setup>
import { computed } from "vue"
import { useRoute } from "vue-router"
import BottomNav from "@/components/BottomNav.vue"
import InstallPrompt from "@/components/InstallPrompt.vue"

const TAB_ROUTES = ["Home", "Performance", "Notifications", "Profile"]

const route = useRoute()
const showBottomNav = computed(() => TAB_ROUTES.includes(route.name))
</script>

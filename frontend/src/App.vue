<template>
  <div class="min-h-screen bg-ground text-ink font-sans">
    <div :class="showBottomNav ? 'pb-24' : ''">
      <router-view v-slot="{ Component, route }">
        <component :is="Component" :key="route.fullPath" />
      </router-view>
    </div>
    <BottomNav v-if="showBottomNav" />
    <PushToast ref="pushToast" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { useRoute } from "vue-router"
import BottomNav from "@/components/BottomNav.vue"
import PushToast from "@/components/PushToast.vue"

const TAB_ROUTES = ["Home", "Performance", "Notifications", "Profile"]

const route = useRoute()
const showBottomNav = computed(() => TAB_ROUTES.includes(route.name))

const pushToast = ref(null)

// A push notification that arrives while the app is actually open never
// reaches the service worker's own background handler (that's the whole
// point of "foreground" vs "background") - FrappePushNotification's own
// onMessage is the one hook for showing something here instead of the
// message silently landing nowhere.
onMounted(() => {
  window?.frappePushNotification?.onMessage((payload) => {
    pushToast.value?.push(payload?.data)
  })
})
</script>

<template>
  <div class="min-h-screen bg-ground pb-24">
    <AppBar title="Reports" fallback="/" />

    <!-- Three tiles, matching the Flutter app's Special Report screen
         (Sales Target / Trial Target / New Wins). Only Sales Target is
         wired to a real screen because field_sales.api.home.sales_target
         reads real ERPNext Sales Person / Target Detail records. Trial
         Target and New Wins have no backing data anywhere in this app -
         there is no demo-target doctype and nothing tracks a "new win" -
         so those two tiles stay disabled with an honest reason attached
         rather than showing fabricated numbers. -->
    <div class="max-w-2xl mx-auto px-4 pt-3 space-y-3">
      <RouterLink
        :to="{ name: 'SalesTargetReport' }"
        class="block bg-surface rounded-2xl border border-rule p-4 active:opacity-80"
      >
        <div class="flex items-center gap-3">
          <span class="w-10 h-10 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center shrink-0">
            <Icon name="report" :size="18" />
          </span>
          <div class="min-w-0">
            <p class="font-display font-semibold text-ink">Sales Target</p>
            <p class="text-xs text-ink-2">This month's target vs. what you've billed</p>
          </div>
        </div>
      </RouterLink>

      <div
        v-for="tile in unavailableTiles"
        :key="tile.title"
        class="bg-surface rounded-2xl border border-rule p-4 opacity-60"
      >
        <div class="flex items-center gap-3">
          <span class="w-10 h-10 rounded-full bg-surface-2 text-ink-3 flex items-center justify-center shrink-0">
            <Icon :name="tile.icon" :size="18" />
          </span>
          <div class="min-w-0">
            <p class="font-display font-semibold text-ink">{{ tile.title }}</p>
            <p class="text-xs text-ink-2">{{ tile.reason }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import AppBar from "@/components/AppBar.vue"
import Icon from "@/components/Icon.vue"

const unavailableTiles = [
  {
    title: "Trial Target",
    icon: "demo",
    reason: "Not available yet - there is no demo target set in the backend to report against.",
  },
  {
    title: "New Wins",
    icon: "customer",
    reason: "Not available yet - nothing in the backend tracks newly won customers.",
  },
]
</script>

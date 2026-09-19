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

      <RouterLink
        :to="{ name: 'Performance' }"
        class="block bg-surface rounded-2xl border border-rule p-4 active:opacity-80"
      >
        <div class="flex items-center gap-3">
          <span class="w-10 h-10 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center shrink-0">
            <Icon name="bar-chart" :size="18" />
          </span>
          <div class="min-w-0">
            <p class="font-display font-semibold text-ink">Team Performance</p>
            <p class="text-xs text-ink-2">How you rank on visits and orders this month</p>
          </div>
        </div>
      </RouterLink>

      <RouterLink
        :to="{ name: 'JourneyPlanVisitReport' }"
        class="block bg-surface rounded-2xl border border-rule p-4 active:opacity-80"
      >
        <div class="flex items-center gap-3">
          <span class="w-10 h-10 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center shrink-0">
            <Icon name="journey" :size="18" />
          </span>
          <div class="min-w-0">
            <p class="font-display font-semibold text-ink">Visit Report</p>
            <p class="text-xs text-ink-2">Journey plans vs. actual field visits, with geolocation</p>
          </div>
        </div>
      </RouterLink>

      <RouterLink
        :to="{ name: 'CustomerCoverageReport' }"
        class="block bg-surface rounded-2xl border border-rule p-4 active:opacity-80"
      >
        <div class="flex items-center gap-3">
          <span class="w-10 h-10 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center shrink-0">
            <Icon name="customer" :size="18" />
          </span>
          <div class="min-w-0">
            <p class="font-display font-semibold text-ink">Customer Coverage</p>
            <p class="text-xs text-ink-2">Which of your customers haven't been visited lately</p>
          </div>
        </div>
      </RouterLink>

      <RouterLink
        :to="{ name: 'CollectionsReport' }"
        class="block bg-surface rounded-2xl border border-rule p-4 active:opacity-80"
      >
        <div class="flex items-center gap-3">
          <span class="w-10 h-10 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center shrink-0">
            <Icon name="report" :size="18" />
          </span>
          <div class="min-w-0">
            <p class="font-display font-semibold text-ink">Collections</p>
            <p class="text-xs text-ink-2">Outstanding balance across your customers, ranked by amount owed</p>
          </div>
        </div>
      </RouterLink>

      <RouterLink
        :to="{ name: 'OnboardingFunnelReport' }"
        class="block bg-surface rounded-2xl border border-rule p-4 active:opacity-80"
      >
        <div class="flex items-center gap-3">
          <span class="w-10 h-10 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center shrink-0">
            <Icon name="customer" :size="18" />
          </span>
          <div class="min-w-0">
            <p class="font-display font-semibold text-ink">Onboarding Funnel</p>
            <p class="text-xs text-ink-2">New customer requests - pending, approved, rejected, and how long each took</p>
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
]
</script>

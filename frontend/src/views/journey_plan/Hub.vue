<template>
  <div class="min-h-screen bg-ground">
    <AppBar title="Journey Plan" fallback="/" />
    <div class="max-w-2xl mx-auto px-4 pt-3 grid grid-cols-2 gap-3">
      <RouterLink :to="{ name: 'JourneyPlanList' }" class="bg-surface rounded-2xl border border-rule p-4 flex flex-col items-center gap-2 active:opacity-80">
        <span class="w-9 h-9 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center"><Icon name="journey" :size="18" /></span>
        <span class="font-display text-sm">Trip Plan</span>
      </RouterLink>
      <RouterLink :to="{ name: 'SampleRequestList' }" class="bg-surface rounded-2xl border border-rule p-4 flex flex-col items-center gap-2 active:opacity-80">
        <span class="w-9 h-9 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center"><Icon name="sample" :size="18" /></span>
        <span class="font-display text-sm">Sample Requisition</span>
      </RouterLink>
      <RouterLink :to="{ name: 'VisitList' }" class="bg-surface rounded-2xl border border-rule p-4 flex flex-col items-center gap-2 active:opacity-80">
        <span class="w-9 h-9 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center"><Icon name="visit" :size="18" /></span>
        <span class="font-display text-sm">Visit Plan</span>
      </RouterLink>
      <RouterLink :to="{ name: 'CollateralRequestList' }" class="bg-surface rounded-2xl border border-rule p-4 flex flex-col items-center gap-2 active:opacity-80">
        <span class="w-9 h-9 rounded-full bg-accent-soft text-accent-ink flex items-center justify-center"><Icon name="collateral" :size="18" /></span>
        <span class="font-display text-sm">Marketing Collaterals</span>
      </RouterLink>
    </div>
  </div>
</template>

<script setup>
import AppBar from "@/components/AppBar.vue"
import Icon from "@/components/Icon.vue"
</script>

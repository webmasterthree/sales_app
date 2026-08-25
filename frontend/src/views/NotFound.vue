<template>
  <div class="min-h-screen bg-ground">
    <AppBar title="Not found" fallback="/" />
    <EmptyState icon="alert-circle" title="Page not found" description="That screen doesn't exist." />
  </div>
</template>

<script setup>
import AppBar from "@/components/AppBar.vue"
import EmptyState from "@/components/EmptyState.vue"
</script>

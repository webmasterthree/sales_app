<!--
  Entry point for "New order", matching the Flutter app's single "New Sales
  Order" screen with a Primary/Secondary toggle. Primary books a normal
  direct-customer Sales Order (native ERPNext doctype, field_sales.api.catalog);
  Secondary books a channel-partner sale for a Secondary customer - a real,
  distinct doctype (Secondary Sales Order, owned by fmcg_cp - see
  field_sales.api.secondary_sales_order). The two flows are genuinely
  different documents with different fields and validation, so rather than
  cramming both into one FormView :steps array, this screen just routes to
  two separate wizards.
-->
<template>
  <OrdersTheme>
  <div class="min-h-screen bg-ground pb-28">
    <header class="sticky top-0 z-30 bg-surface border-b border-rule pt-safe">
      <div class="flex items-center gap-2 px-2 py-2 max-w-2xl mx-auto">
        <button type="button" class="flex items-center justify-center w-11 h-11 rounded-full active:bg-surface-2 shrink-0" aria-label="Back" @click="router.replace({ name: 'OrderList' })">
          <Icon name="chevron-left" :size="22" />
        </button>
        <h1 class="flex-1 font-display font-extrabold text-base text-ink">New order</h1>
      </div>
    </header>

    <div class="max-w-2xl mx-auto px-4 pt-4 space-y-3">
      <p class="text-sm text-ink-2">Who is this order for?</p>

      <RouterLink
        :to="{ name: 'OrderNewDirect' }"
        class="block bg-surface border border-rule rounded-2xl p-4 active:bg-surface-2"
      >
        <p class="font-display font-bold text-ink">Direct Customer</p>
        <p class="text-sm text-ink-2 mt-1">A normal order booked straight against a customer, at the priced catalogue.</p>
      </RouterLink>

      <RouterLink
        :to="{ name: 'OrderNewChannelPartner' }"
        class="block bg-surface border border-rule rounded-2xl p-4 active:bg-surface-2"
      >
        <p class="font-display font-bold text-ink">Channel Partner</p>
        <p class="text-sm text-ink-2 mt-1">A sale for a Secondary customer, routed through their own fixed channel partner.</p>
      </RouterLink>
    </div>
  </div>
  </OrdersTheme>
</template>

<script setup>
import { useRouter } from "vue-router"
import OrdersTheme from "@/views/orders/OrdersTheme.vue"
import Icon from "@/components/Icon.vue"

const router = useRouter()
</script>

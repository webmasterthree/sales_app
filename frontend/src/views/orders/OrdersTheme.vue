<!--
  Sales Order used to carry its own separate visual identity here (a warm
  off-white/near-black/Manrope theme matching an early reference design,
  distinct from the rest of the app). That's been retired in favour of the
  app-wide Neon Ops theme - this wrapper is kept as a harmless passthrough
  (still used by List/Detail/Form/New/ChannelPartnerForm/ChannelPartnerDetail)
  so removing it everywhere isn't required just to drop the override.
-->
<template>
  <div class="orders-theme">
    <slot />
  </div>
</template>

<!--
  Scoped visual override for the Sales Order module, matching the reference
  design ("Mohan Impex · ASM · Sales Order") the user supplied: a warm
  off-white ground, Manrope type, near-black primary actions, and a
  terracotta accent - distinct from the rest of the app's green/Poppins
  brand. This works by redefining the same --fs-* custom properties the
  shared List/Detail/FormView/StatusPill/AppBar components already read,
  scoped to this subtree only via normal CSS cascade - no shared component
  or global token was touched, so every other module is unaffected.
-->
<template>
  <div class="orders-theme">
    <slot />
  </div>
</template>

<style scoped>
.orders-theme {
  --fs-ground: #EDEEEA;
  --fs-ground-home: #EDEEEA;
  --fs-surface: #FFFFFF;
  --fs-surface-2: #F5F6F3;
  --fs-ink: #14180F;
  --fs-ink-2: #5B5F52;
  --fs-ink-3: #8B8F80;
  --fs-rule: #E4E7E0;
  --fs-rule-soft: #EFF1EC;
  /* near-black - primary buttons, active segmented pills */
  --fs-accent: #171A14;
  --fs-accent-fg: #FFFFFF;
  --fs-accent-soft: #F5F6F3;
  --fs-accent-ink: #171A14;
  /* white/bordered - "Previous"/secondary buttons */
  --fs-action2: #FFFFFF;
  --fs-action2-fg: #14180F;
  --fs-warn: #C8862A;
  --fs-good: #4C7A1F;
  --fs-crit: #B23A2E;
  --fs-shadow: none;
  --fs-display: "Manrope", "Segoe UI", system-ui, sans-serif;
  --fs-mono: "Manrope", ui-monospace, "SFMono-Regular", Consolas, monospace;
}
/* the reference's one warm accent, used only for the create FAB and the
   customer-type selection - not the same as --fs-accent (near-black), so it
   isn't a design-system token, just this module's own thing. */
.orders-theme :deep(.orders-fab) {
  background: #C0392B;
  color: #FFFFFF;
}
</style>

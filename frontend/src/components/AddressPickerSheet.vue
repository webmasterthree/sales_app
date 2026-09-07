<template>
  <div
    v-if="open"
    class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40"
    @click.self="$emit('close')"
  >
    <div class="bg-surface w-full sm:max-w-sm sm:rounded-2xl rounded-t-2xl overflow-hidden pb-safe max-h-[80vh] flex flex-col">
      <div class="flex justify-center pt-2 sm:hidden shrink-0">
        <div class="w-10 h-1 rounded-full bg-rule"></div>
      </div>
      <div class="px-5 pt-3 pb-2 shrink-0 flex items-center justify-between">
        <p class="text-lg font-display font-bold text-ink">Select {{ title }} Address</p>
        <button type="button" class="w-8 h-8 rounded-full flex items-center justify-center text-ink-3 shrink-0" aria-label="Close" @click="$emit('close')">
          <Icon name="close" :size="16" />
        </button>
      </div>
      <div class="px-5 pb-5 overflow-y-auto space-y-2.5">
        <button
          v-for="a in addresses"
          :key="a.name"
          type="button"
          class="w-full text-left rounded-[13px] border-[1.5px] p-3"
          :class="a.name === modelValue ? 'border-accent bg-accent-soft' : 'border-rule bg-surface'"
          @click="pick(a.name)"
        >
          <p class="text-sm font-display font-bold text-ink mb-0.5">{{ a.address_title || a.name }}</p>
          <p class="text-xs text-ink-2 leading-relaxed">{{ addressLine(a) }}</p>
        </button>
        <p v-if="!addresses.length" class="text-sm text-ink-3 text-center py-4">
          No addresses on file for this customer.
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
// A bottom sheet for picking one of a customer's addresses, replacing a
// plain <select> - matches the pick-a-card pattern already used for
// location confirmation elsewhere in the app (LocationConfirmModal.vue).
import Icon from "@/components/Icon.vue"

defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: "" },
  addresses: { type: Array, default: () => [] },
  modelValue: { type: String, default: "" },
})
const emit = defineEmits(["update:modelValue", "close"])

function addressLine(a) {
  return [a.address_line1, a.address_line2, a.city, a.state, a.pincode].filter(Boolean).join(", ")
}

function pick(name) {
  emit("update:modelValue", name)
  emit("close")
}
</script>

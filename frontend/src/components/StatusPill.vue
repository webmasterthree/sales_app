<template>
  <span
    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-display font-medium whitespace-nowrap"
    :class="classes"
  >
    {{ label }}
  </span>
</template>

<script setup>
import { computed } from "vue"

const props = defineProps({
  status: { type: String, default: "" },
  // optional override map: { "Pending": "warn", ... }
  tone: { type: String, default: "" },
})

// Unified vocabulary across modules per the design brief: Draft / Submitted /
// Pending / Approved / Rejected / Cancelled, mapped to the same three
// semantic tones everywhere rather than each module inventing its own.
const TONE_MAP = {
  draft: "muted",
  pending: "warn",
  submitted: "accent",
  open: "warn",
  "to deliver": "warn",
  "to deliver and bill": "warn",
  approved: "good",
  completed: "good",
  resolved: "good",
  closed: "good",
  done: "good",
  rejected: "crit",
  cancelled: "crit",
  overdue: "crit",
  "without order": "crit",
  "with order": "good",
  inside: "good",
  outside: "crit",
  "not checked": "muted",
}

const label = computed(() => props.status || "—")

const classes = computed(() => {
  const tone = (props.tone || TONE_MAP[(props.status || "").toLowerCase()] || "muted")
  return {
    muted: "bg-surface-2 text-ink-2",
    accent: "bg-accent-soft text-accent-ink",
    warn: "bg-warn/10 text-warn",
    good: "bg-good/10 text-good",
    crit: "bg-crit/10 text-crit",
  }[tone]
})
</script>

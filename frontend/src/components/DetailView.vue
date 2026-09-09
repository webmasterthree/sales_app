<template>
  <div class="min-h-screen bg-ground pb-28">
    <AppBar :title="loading ? 'Loading…' : config.title(doc) " :fallback="config.fallback">
      <template #actions>
        <slot name="appbar-extra" :doc="doc" />
        <StatusPill v-if="doc && config.statusField" :status="doc[config.statusField]" />
      </template>
    </AppBar>

    <LoadingSkeleton v-if="loading" :rows="3" />
    <ErrorState v-else-if="error" :message="error" @retry="load" />

    <div v-else-if="doc" class="max-w-2xl mx-auto px-4 pt-3 space-y-3">
      <!-- Optional identity band - only rendered when a screen's own config
           opts in with real fields (config.hero). Generic Detail screens
           that don't define this (Sales Order, Field Visit, ...) are
           unaffected and keep the plain AppBar-only header. -->
      <div
        v-if="config.hero"
        class="rounded-2xl p-4 relative overflow-hidden border border-rule"
        style="background: linear-gradient(155deg, var(--fs-surface) 0%, var(--fs-accent-soft) 100%)"
      >
        <div
          class="w-11 h-11 rounded-xl flex items-center justify-center font-display font-extrabold text-base mb-2.5"
          style="background: linear-gradient(155deg, var(--fs-accent), var(--fs-good)); color: var(--fs-accent-fg)"
        >
          {{ heroBadge }}
        </div>
        <p class="font-display font-bold text-ink mb-2">{{ config.title(doc) }}</p>
        <div class="flex flex-wrap gap-1.5">
          <span
            v-for="(chip, i) in heroChips"
            :key="chip.label"
            class="font-mono text-[10px] font-semibold px-2 py-1 rounded-full"
            :style="i % 2 === 0
              ? 'background: var(--fs-accent-soft); color: var(--fs-accent-ink)'
              : 'background: color-mix(in srgb, var(--fs-chart) 16%, transparent); color: var(--fs-chart)'"
          >
            {{ chip.value }}
          </span>
        </div>
      </div>

      <details
        v-for="(section, i) in config.sections"
        :key="section.title"
        class="bg-surface rounded-2xl border border-rule overflow-hidden"
        :open="i === 0"
      >
        <summary class="px-4 py-3 font-display font-semibold cursor-pointer select-none">
          {{ section.title }}
        </summary>
        <div class="px-4 pb-4 space-y-2">
          <div
            v-for="f in section.fields"
            v-show="!(f.hidden && f.hidden(doc))"
            :key="f.key"
            class="py-1 border-b border-rule-soft last:border-0"
          >
            <template v-if="f.html">
              <span class="text-ink-2 text-sm block mb-1">{{ f.label }}</span>
              <div v-if="doc[f.key]" class="text-ink text-sm prose-html" v-html="doc[f.key]" />
              <span v-else class="text-ink text-sm">—</span>
            </template>
            <div v-else-if="f.pill" class="flex justify-between items-center gap-3 text-sm">
              <span class="text-ink-2">{{ f.label }}</span>
              <StatusPill v-if="doc[f.key]" :status="doc[f.key]" />
              <span v-else class="text-ink text-right">—</span>
            </div>
            <div v-else class="flex justify-between gap-3 text-sm">
              <span class="text-ink-2">{{ f.label }}</span>
              <span class="text-ink text-right">{{ format(f) }}</span>
            </div>
          </div>
        </div>
      </details>

      <slot name="extra" :doc="doc" :reload="load" />
    </div>

    <div
      v-if="doc && config.actions?.length"
      class="fixed bottom-0 inset-x-0 bg-surface border-t border-rule px-4 py-3 flex gap-2 pb-safe z-30"
    >
      <button
        v-for="a in visibleActions"
        :key="a.label"
        type="button"
        class="flex-1 h-[52px] rounded-[10px] text-sm font-display font-medium"
        :class="a.tone === 'crit' ? 'bg-crit text-white'
          : a.tone === 'muted' ? 'bg-action2 text-action2-fg'
          : a.tone === 'outline' ? 'bg-transparent text-accent-ink border border-rule'
          : 'bg-accent text-accent-fg'"
        :disabled="busy"
        @click="runAction(a)"
      >
        {{ a.label }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { call } from "frappe-ui"
import AppBar from "@/components/AppBar.vue"
import StatusPill from "@/components/StatusPill.vue"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"

const props = defineProps({
  name: { type: String, required: true },
  // { method, title(doc), fallback, statusField,
  //   sections: [{title, fields:[{label, key, format?}]}],
  //   actions: [{label, tone, method, args(doc), confirm, visible(doc)}] }
  config: { type: Object, required: true },
})
const emit = defineEmits(["loaded"])

// config.hero is optional: { chips: [{label, key}] } - badge is always
// derived from the title, never configured separately, so there's only one
// source of truth for "what this record is called."
const heroBadge = computed(() => {
  const title = props.config.title(doc.value) || ""
  const words = title.trim().split(/\s+/).filter(Boolean)
  if (!words.length) return "?"
  return words.length === 1 ? words[0].slice(0, 2).toUpperCase() : (words[0][0] + words[1][0]).toUpperCase()
})

const heroChips = computed(() => {
  if (!props.config.hero?.chips || !doc.value) return []
  return props.config.hero.chips
    .map((c) => ({ label: c.label, value: doc.value[c.key] }))
    .filter((c) => c.value)
})

const doc = ref(null)
const loading = ref(true)
const error = ref("")
const busy = ref(null)

const visibleActions = computed(() => (props.config.actions || []).filter((a) => !a.visible || a.visible(doc.value)))

function format(f) {
  const v = doc.value?.[f.key]
  if (f.format) return f.format(v, doc.value)
  if (v === null || v === undefined || v === "") return "—"
  return v
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    doc.value = await call(props.config.method, { name: props.name })
    emit("loaded", doc.value)
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load this record."
  } finally {
    loading.value = false
  }
}

async function runAction(a) {
  if (a.confirm && !window.confirm(a.confirm)) return
  busy.value = a.label
  try {
    if (a.handler) {
      await a.handler(doc.value, load)
    } else {
      await call(a.method, { name: props.name, ...(a.args ? a.args(doc.value) : {}) })
      await load()
    }
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "That action failed."
  } finally {
    busy.value = null
  }
}

defineExpose({ load, doc })

onMounted(load)
</script>

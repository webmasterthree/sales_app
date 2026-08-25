<template>
  <div class="min-h-screen bg-ground pb-28">
    <AppBar :title="loading ? 'Loading…' : config.title(doc) " :fallback="config.fallback">
      <template #actions>
        <StatusPill v-if="doc && config.statusField" :status="doc[config.statusField]" />
      </template>
    </AppBar>

    <LoadingSkeleton v-if="loading" :rows="3" />
    <ErrorState v-else-if="error" :message="error" @retry="load" />

    <div v-else-if="doc" class="max-w-2xl mx-auto px-4 pt-3 space-y-3">
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
          <div v-for="f in section.fields" :key="f.key" class="py-1 border-b border-rule-soft last:border-0">
            <template v-if="f.html">
              <span class="text-ink-2 text-sm block mb-1">{{ f.label }}</span>
              <div v-if="doc[f.key]" class="text-ink text-sm prose-html" v-html="doc[f.key]" />
              <span v-else class="text-ink text-sm">—</span>
            </template>
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
        :class="a.tone === 'crit' ? 'bg-crit text-white' : a.tone === 'muted' ? 'bg-action2 text-action2-fg' : 'bg-accent text-accent-fg'"
        :disabled="busy"
        @click="runAction(a)"
      >
        {{ busy === a.label ? "Working…" : a.label }}
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

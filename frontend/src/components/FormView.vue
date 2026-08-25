<template>
  <div class="min-h-screen bg-ground pb-28">
    <AppBar :title="title" :fallback="fallback" />

    <!-- step progress -->
    <div v-if="steps.length > 1" class="max-w-2xl mx-auto px-4 pt-3">
      <div class="flex items-center gap-1">
        <div
          v-for="(s, i) in steps"
          :key="s.title"
          class="flex-1 h-1.5 rounded-full"
          :class="i <= stepIndex ? 'bg-accent' : 'bg-rule'"
        />
      </div>
      <p class="text-xs text-ink-2 mt-1 font-display">
        Step {{ stepIndex + 1 }} of {{ steps.length }} · {{ steps[stepIndex].title }}
      </p>
    </div>

    <ErrorState v-if="loadError" :message="loadError" @retry="$emit('retry')" />

    <form v-else class="max-w-2xl mx-auto px-4 pt-3 space-y-4" @submit.prevent>
      <div v-if="formError" class="bg-crit/10 text-crit text-sm rounded-[10px] px-3 py-2">{{ formError }}</div>

      <slot :name="`step-${stepIndex}`" :data="formData" :errors="fieldErrors">
        <div class="bg-surface rounded-2xl p-4 space-y-4">
          <div v-for="f in steps[stepIndex].fields" :key="f.key">
            <label class="block text-sm font-display text-ink-2 mb-1">
              {{ f.label }}
              <span v-if="f.required" class="text-crit">*</span>
              <span v-else class="text-ink-3 font-normal">(optional)</span>
            </label>

            <select
              v-if="f.type === 'select'"
              v-model="formData[f.key]"
              class="w-full h-[52px] rounded-[10px] border border-rule bg-surface text-ink appearance-none px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
              :class="fieldErrors[f.key] ? 'border-crit' : ''"
            >
              <option value="">Select…</option>
              <option v-for="opt in f.options" :key="opt" :value="opt">{{ opt }}</option>
            </select>

            <textarea
              v-else-if="f.type === 'textarea'"
              v-model="formData[f.key]"
              rows="3"
              class="w-full rounded-[10px] border border-rule bg-surface text-ink px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
              :class="fieldErrors[f.key] ? 'border-crit' : ''"
            />

            <input
              v-else
              v-model="formData[f.key]"
              :type="f.type || 'text'"
              class="w-full h-[52px] rounded-[10px] border border-rule bg-surface text-ink appearance-none px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
              :class="fieldErrors[f.key] ? 'border-crit' : ''"
            />

            <p v-if="fieldErrors[f.key]" class="text-xs text-crit mt-1">{{ fieldErrors[f.key] }}</p>
          </div>
        </div>
      </slot>
    </form>

    <div class="fixed bottom-0 inset-x-0 bg-surface border-t border-rule px-4 py-3 flex gap-2 pb-safe z-30">
      <button
        v-if="stepIndex > 0"
        type="button"
        class="px-4 h-[52px] rounded-[10px] bg-surface-2 text-ink text-sm font-display font-medium"
        @click="stepIndex--"
      >
        Back
      </button>
      <button
        v-if="allowDraft && stepIndex === steps.length - 1"
        type="button"
        class="px-4 h-[52px] rounded-[10px] bg-action2 text-action2-fg text-sm font-display font-medium"
        :disabled="submitting"
        @click="save('draft')"
      >
        Save draft
      </button>
      <button
        type="button"
        class="flex-1 h-[52px] rounded-[10px] bg-accent text-accent-fg text-sm font-display font-medium disabled:opacity-60"
        :disabled="submitting"
        @click="stepIndex < steps.length - 1 ? next() : save('submit')"
      >
        {{ submitting ? "Working…" : (stepIndex < steps.length - 1 ? "Next" : submitLabel) }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, watch } from "vue"
import AppBar from "@/components/AppBar.vue"
import ErrorState from "@/components/ErrorState.vue"

const props = defineProps({
  title: { type: String, default: "" },
  fallback: { type: String, default: "/" },
  steps: { type: Array, required: true }, // [{title, fields:[{key,label,type,required,options}], validate(data)}]
  initialData: { type: Object, default: () => ({}) },
  allowDraft: { type: Boolean, default: false },
  submitLabel: { type: String, default: "Submit" },
  loadError: { type: String, default: "" },
  onSubmit: { type: Function, required: true }, // (data, mode) => Promise
})
const emit = defineEmits(["retry", "saved"])

const formData = reactive({ ...props.initialData })
watch(() => props.initialData, (v) => Object.assign(formData, v))

const stepIndex = ref(0)
const fieldErrors = reactive({})
const formError = ref("")
const submitting = ref(false)

function validateStep(i) {
  const step = props.steps[i]
  let ok = true
  for (const key in fieldErrors) delete fieldErrors[key]
  for (const f of step.fields || []) {
    if (f.required && !String(formData[f.key] ?? "").trim()) {
      fieldErrors[f.key] = "This is required."
      ok = false
    }
  }
  if (step.validate) {
    const msg = step.validate(formData)
    if (msg) {
      formError.value = msg
      ok = false
    }
  }
  return ok
}

function next() {
  formError.value = ""
  if (!validateStep(stepIndex.value)) return
  stepIndex.value++
}

async function save(mode) {
  formError.value = ""
  if (mode === "submit" && !validateStep(stepIndex.value)) return
  submitting.value = true
  try {
    const result = await props.onSubmit({ ...formData }, mode)
    emit("saved", result)
  } catch (err) {
    formError.value = err.messages?.[0] || err.message || "Could not save. Please try again."
  } finally {
    submitting.value = false
  }
}

defineExpose({ formData, stepIndex })
</script>

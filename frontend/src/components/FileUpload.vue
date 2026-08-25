<template>
  <div>
    <!-- existing/uploaded file -->
    <div v-if="modelValue && !uploading" class="relative rounded-2xl border border-rule overflow-hidden bg-surface-2" :style="{ aspectRatio: preview ? '4/3' : undefined }">
      <img v-if="isImage" :src="modelValue" class="w-full h-full object-cover block" :alt="label" />
      <div v-else class="flex items-center gap-2 p-3">
        <Icon name="collateral" :size="18" class="text-ink-2 shrink-0" />
        <span class="text-sm text-ink truncate">{{ fileName }}</span>
      </div>
      <button
        v-if="!readonly"
        type="button"
        class="absolute top-2 right-2 w-7 h-7 rounded-full bg-ink/70 text-white flex items-center justify-center"
        aria-label="Remove"
        @click="clear"
      >
        <Icon name="close" :size="14" />
      </button>
    </div>

    <!-- upload control -->
    <label
      v-else-if="!readonly"
      class="flex flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-rule bg-surface p-6 text-center cursor-pointer active:opacity-80"
    >
      <Icon :name="uploading ? 'inbox' : 'camera'" :size="22" class="text-ink-3" />
      <span class="text-sm font-display font-medium text-ink-2">
        <template v-if="uploading">Uploading… {{ progress }}%</template>
        <template v-else>{{ label }}</template>
      </span>
      <span v-if="error" class="text-xs text-crit">{{ error }}</span>
      <input
        type="file"
        :accept="accept"
        capture="environment"
        class="sr-only"
        :disabled="uploading"
        @change="onPick"
      />
    </label>

    <p v-else class="text-sm text-ink-3">No file attached.</p>
  </div>
</template>

<script setup>
import { computed, ref } from "vue"
import Icon from "@/components/Icon.vue"
import { uploadFile } from "@/composables/upload"

const props = defineProps({
  modelValue: { type: String, default: "" },
  doctype: { type: String, required: true },
  docname: { type: String, default: "" },
  fieldname: { type: String, default: "" },
  label: { type: String, default: "Take or choose a photo" },
  accept: { type: String, default: "image/*" },
  readonly: { type: Boolean, default: false },
  preview: { type: Boolean, default: true },
})
const emit = defineEmits(["update:modelValue", "uploaded"])

const uploading = ref(false)
const progress = ref(0)
const error = ref("")

const isImage = computed(() => /\.(png|jpe?g|gif|webp)(\?|$)/i.test(props.modelValue || ""))
const fileName = computed(() => (props.modelValue || "").split("/").pop())

async function onPick(e) {
  const file = e.target.files?.[0]
  e.target.value = ""
  if (!file) return
  error.value = ""
  uploading.value = true
  progress.value = 0
  try {
    const result = await uploadFile({
      file,
      doctype: props.doctype,
      docname: props.docname,
      fieldname: props.fieldname,
      onProgress: (p) => (progress.value = p),
    })
    emit("update:modelValue", result.file_url)
    emit("uploaded", result)
  } catch (err) {
    error.value = err.message || "Upload failed."
  } finally {
    uploading.value = false
  }
}

function clear() {
  emit("update:modelValue", "")
}
</script>

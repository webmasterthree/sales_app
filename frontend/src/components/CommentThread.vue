<template>
  <div class="bg-surface rounded-2xl border border-rule overflow-hidden">
    <div class="px-4 py-3 font-display font-semibold border-b border-rule-soft">Comments</div>

    <div class="px-4 py-3">
      <p v-if="loading" class="text-sm text-ink-3">Loading comments…</p>
      <p v-else-if="error" class="text-sm text-crit">{{ error }}</p>
      <p v-else-if="!comments.length" class="text-sm text-ink-3">No comments yet.</p>
      <div v-else class="space-y-3">
        <div v-for="c in comments" :key="c.name" class="text-sm border-b border-rule-soft pb-3 last:border-0 last:pb-0">
          <div class="flex items-baseline justify-between gap-2">
            <span class="font-display font-medium text-ink">{{ c.comment_by || c.comment_email }}</span>
            <span class="text-xs text-ink-3 shrink-0">{{ c.creation }}</span>
          </div>
          <p class="text-ink-2 whitespace-pre-wrap mt-0.5">{{ c.content }}</p>
        </div>
      </div>
    </div>

    <div class="px-4 pb-4 pt-1 flex items-end gap-2">
      <textarea
        v-model="draft"
        rows="2"
        placeholder="Add a comment…"
        class="flex-1 rounded-xl border border-rule bg-ground px-3 py-2 text-sm text-ink resize-none"
        :disabled="posting"
      />
      <button
        type="button"
        class="h-10 px-4 rounded-[10px] bg-accent text-accent-fg text-sm font-display font-medium disabled:opacity-60 shrink-0"
        :disabled="posting || !draft.trim()"
        @click="post"
      >
        {{ posting ? "Adding…" : "Add" }}
      </button>
    </div>
    <p v-if="postError" class="px-4 pb-3 -mt-2 text-xs text-crit">{{ postError }}</p>
  </div>
</template>

<script setup>
// Reusable comment thread for any doctype the backend has allow-listed in
// field_sales.api.comments.COMMENT_DOCTYPES. Read history + add a comment,
// nothing more - the app already handles status changes as their own
// role-gated actions per module (see e.g. onboarding/Detail.vue's
// Approve/Reject), so this component doesn't try to generalise that too.
import { onMounted, ref } from "vue"
import { call } from "frappe-ui"

const props = defineProps({
  doctype: { type: String, required: true },
  docname: { type: String, required: true },
})

const comments = ref([])
const loading = ref(true)
const error = ref("")
const draft = ref("")
const posting = ref(false)
const postError = ref("")

async function load() {
  loading.value = true
  error.value = ""
  try {
    comments.value = await call("field_sales.api.comments.comment_list", {
      doctype: props.doctype,
      docname: props.docname,
    })
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load comments."
  } finally {
    loading.value = false
  }
}

async function post() {
  const content = draft.value.trim()
  if (!content) return
  posting.value = true
  postError.value = ""
  try {
    const comment = await call("field_sales.api.comments.add_comment", {
      doctype: props.doctype,
      docname: props.docname,
      content,
    })
    comments.value.push(comment)
    draft.value = ""
  } catch (err) {
    postError.value = err.messages?.[0] || err.message || "Could not add the comment."
  } finally {
    posting.value = false
  }
}

defineExpose({ reload: load })

onMounted(load)
</script>

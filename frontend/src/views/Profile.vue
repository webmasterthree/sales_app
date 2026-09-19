<template>
  <div class="min-h-screen bg-ground pb-24">
    <header class="pt-safe px-4 pt-4 pb-2 max-w-2xl mx-auto">
      <h1 class="font-display text-xl font-bold">Profile</h1>
    </header>

    <div class="max-w-2xl mx-auto px-4 space-y-4">
      <LoadingSkeleton v-if="loading" :rows="1" />
      <ErrorState v-else-if="error" :message="error" @retry="load" />
      <div v-else-if="profile" class="bg-surface rounded-2xl p-4">
        <div class="flex items-start justify-between">
          <div>
            <p class="font-display font-semibold text-lg">{{ profile.full_name }}</p>
            <p class="text-sm text-ink-2">{{ profile.user }}</p>
            <p v-if="profile.designation" class="text-sm text-ink-2 mt-1">{{ profile.designation }}</p>
          </div>
          <button
            v-if="!editing"
            type="button"
            class="text-sm text-accent font-display font-medium"
            @click="startEdit"
          >
            Edit
          </button>
        </div>

        <p v-if="profile.territories?.length" class="text-xs text-ink-3 mt-2">
          Territories: {{ profile.territories.join(", ") }}
        </p>
        <p v-if="profile.roles?.length" class="text-xs text-ink-3 mt-1">
          Roles: {{ profile.roles.join(", ") }}
        </p>

        <form v-if="editing" class="mt-4 space-y-3 border-t border-rule pt-4" @submit.prevent="saveProfile">
          <div class="grid grid-cols-1 gap-3">
            <div>
              <label class="block text-xs font-display text-ink-2 mb-1">First name</label>
              <input
                v-model="form.first_name"
                type="text"
                class="w-full h-[44px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
              />
            </div>
            <div>
              <label class="block text-xs font-display text-ink-2 mb-1">Last name</label>
              <input
                v-model="form.last_name"
                type="text"
                class="w-full h-[44px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
              />
            </div>
          </div>
          <div>
            <label class="block text-xs font-display text-ink-2 mb-1">Mobile number</label>
            <input
              v-model="form.mobile_no"
              type="tel"
              class="w-full h-[44px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
            />
          </div>
          <div>
            <label class="block text-xs font-display text-ink-2 mb-1">Alternate phone</label>
            <input
              v-model="form.phone"
              type="tel"
              class="w-full h-[44px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm focus:outline-none focus:ring-2 focus:ring-accent/40 focus:border-accent"
            />
          </div>
          <label class="flex items-center gap-2 text-sm text-ink-2">
            <input v-model="form.mute_sounds" type="checkbox" />
            Mute notification sounds
          </label>
          <label class="flex items-center gap-2 text-sm text-ink-2">
            <input v-model="form.thread_notify" type="checkbox" />
            Notify me on comment threads
          </label>
          <p v-if="saveError" class="text-sm text-crit">{{ saveError }}</p>
          <div class="flex gap-2">
            <button
              type="button"
              class="flex-1 h-[44px] rounded-[10px] border border-rule text-ink-2 font-display"
              @click="editing = false"
            >
              Cancel
            </button>
            <button
              type="submit"
              class="flex-1 h-[44px] rounded-[10px] bg-accent text-accent-fg font-display font-medium disabled:opacity-60"
              :disabled="saving"
            >
              {{ saving ? "Saving…" : "Save" }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue"
import { call } from "frappe-ui"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"

const profile = ref(null)
const loading = ref(true)
const error = ref("")

const editing = ref(false)
const saving = ref(false)
const saveError = ref("")
const form = reactive({
  first_name: "",
  last_name: "",
  mobile_no: "",
  phone: "",
  mute_sounds: false,
  thread_notify: false,
})

async function load() {
  loading.value = true
  error.value = ""
  try {
    profile.value = await call("field_sales.api.auth.session")
  } catch (err) {
    error.value = err.messages?.[0] || err.message || "Could not load your profile."
  } finally {
    loading.value = false
  }
}

function startEdit() {
  form.first_name = profile.value?.first_name || ""
  form.last_name = profile.value?.last_name || ""
  form.mobile_no = profile.value?.mobile_no || ""
  form.phone = profile.value?.phone || ""
  form.mute_sounds = !!profile.value?.mute_sounds
  form.thread_notify = !!profile.value?.thread_notify
  saveError.value = ""
  editing.value = true
}

async function saveProfile() {
  saving.value = true
  saveError.value = ""
  try {
    const res = await call("field_sales.api.auth.update_profile", { ...form })
    profile.value = res
    editing.value = false
  } catch (err) {
    saveError.value = err.messages?.[0] || err.message || "Could not save your changes."
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

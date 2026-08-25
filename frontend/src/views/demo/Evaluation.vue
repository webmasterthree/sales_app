<template>
  <div class="min-h-screen bg-ground pb-28">
    <AppBar :title="`Evaluate ${itemCode}`" :fallback="`/requisitions/demos/${name}`" />

    <LoadingSkeleton v-if="loading" :rows="3" />
    <ErrorState v-else-if="loadError" :message="loadError" @retry="load" />

    <form v-else class="max-w-2xl mx-auto px-4 pt-3 space-y-4" @submit.prevent>
      <div v-if="formError" class="bg-crit/10 text-crit text-sm rounded-[10px] px-3 py-2">{{ formError }}</div>

      <!-- per-parameter scorecard: a rating control for Rating parameters,
           a measurement input (with the parameter's own unit) for
           everything else. This is what actually gets validated - the
           server rejects a rating against a measured parameter and vice
           versa, so the inline messages here mirror that rather than
           inventing softer rules of their own. -->
      <div class="bg-surface rounded-2xl p-4 space-y-5">
        <p class="font-display font-semibold">Scorecard</p>

        <div v-for="p in parameters" :key="p.name" class="space-y-2">
          <label class="block text-sm font-display text-ink-2">{{ p.parameter_name }}</label>

          <div v-if="p.value_type === 'Rating'" class="flex gap-2">
            <button
              v-for="opt in RATING_OPTIONS"
              :key="opt"
              type="button"
              class="flex-1 py-2 rounded-[10px] text-xs font-display border"
              :class="scores[p.name].rating === opt ? 'bg-accent text-accent-fg border-accent' : 'bg-surface border-rule text-ink-2'"
              @click="scores[p.name].rating = opt"
            >
              {{ opt }}
            </button>
          </div>

          <div v-else class="flex items-center gap-2">
            <input
              v-model.number="scores[p.name].value"
              type="number"
              step="any"
              class="flex-1 rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm"
              :placeholder="p.value_type"
            />
            <span v-if="p.unit" class="text-sm text-ink-2">{{ p.unit }}</span>
          </div>

          <div v-if="p.requires_remarks">
            <input
              v-model="scores[p.name].remarks"
              class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm"
              :class="rowErrors[p.name] ? 'border-crit' : ''"
              placeholder="Remarks (required)"
            />
          </div>
          <p v-if="rowErrors[p.name]" class="text-xs text-crit">{{ rowErrors[p.name] }}</p>
        </div>

        <p v-if="!parameters.length" class="text-sm text-ink-2">
          No scorecard parameters are configured yet.
        </p>
      </div>

      <!-- outcome -->
      <div class="bg-surface rounded-2xl p-4 space-y-4">
        <p class="font-display font-semibold">Outcome</p>

        <div class="flex gap-2">
          <button
            v-for="opt in ['Successful', 'Unsuccessful']"
            :key="opt"
            type="button"
            class="flex-1 py-2 rounded-[10px] text-sm font-display border"
            :class="outcome.outcome === opt ? 'bg-accent text-accent-fg border-accent' : 'bg-surface border-rule text-ink-2'"
            @click="outcome.outcome = opt"
          >
            {{ opt }}
          </button>
        </div>

        <label class="flex items-center gap-2 text-sm">
          <input type="checkbox" v-model="outcome.order_received" true-value="1" false-value="0" />
          An order was placed on the back of this demo
        </label>

        <div v-if="outcome.outcome === 'Unsuccessful' && outcome.order_received !== '1'">
          <label class="block text-sm font-display text-ink-2 mb-1">Why no order? <span class="text-crit">*</span></label>
          <select v-model="outcome.no_order_reason" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm">
            <option value="">Select…</option>
            <option v-for="opt in NO_ORDER_REASONS" :key="opt" :value="opt">{{ opt }}</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Remarks (optional)</label>
          <textarea v-model="outcome.remarks" rows="3" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" />
        </div>
      </div>
    </form>

    <div v-if="!loading && !loadError" class="fixed bottom-0 inset-x-0 bg-surface border-t border-rule px-4 py-3 pb-safe z-30">
      <button
        type="button"
        class="w-full py-3 rounded-[10px] bg-accent text-accent-fg text-sm font-display font-medium disabled:opacity-60"
        :disabled="submitting"
        @click="submit"
      >
        {{ submitting ? "Working…" : "Finish evaluation" }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"
import AppBar from "@/components/AppBar.vue"
import ErrorState from "@/components/ErrorState.vue"
import LoadingSkeleton from "@/components/LoadingSkeleton.vue"

const props = defineProps({
  name: { type: String, required: true },
  item_code: { type: String, required: true },
})
const itemCode = props.item_code

const router = useRouter()

const RATING_OPTIONS = ["Poor", "Fair", "Good", "Excellent"]
const NO_ORDER_REASONS = ["Price", "Stock still available", "Needs more testing", "Decision pending", "Other"]

const loading = ref(true)
const loadError = ref("")
const submitting = ref(false)
const formError = ref("")
const rowErrors = reactive({})

const parameters = ref([])
const scores = reactive({})
const outcome = reactive({
  outcome: "",
  order_received: "0",
  no_order_reason: "",
  remarks: "",
  evaluated_on: new Date().toISOString().slice(0, 10),
})

async function load() {
  loading.value = true
  loadError.value = ""
  try {
    parameters.value = await call("field_sales.api.demo.demo_parameters")
    for (const p of parameters.value) {
      scores[p.name] = { rating: "", value: null, remarks: "" }
    }
  } catch (err) {
    loadError.value = err.messages?.[0] || err.message || "Could not load the scorecard."
  } finally {
    loading.value = false
  }
}

function validate() {
  formError.value = ""
  for (const key in rowErrors) delete rowErrors[key]
  let ok = true

  for (const p of parameters.value) {
    const row = scores[p.name]
    const touched = p.value_type === "Rating" ? !!row.rating : row.value !== null && row.value !== ""
    if (!touched) continue // an untouched parameter is simply left off the scorecard
    if (p.requires_remarks && !(row.remarks || "").trim()) {
      rowErrors[p.name] = "This parameter needs remarks."
      ok = false
    }
  }

  if (!outcome.outcome) {
    formError.value = "Say whether the demo was successful."
    ok = false
  } else if (outcome.outcome === "Unsuccessful" && outcome.order_received !== "1" && !outcome.no_order_reason) {
    formError.value = "Say why the demo did not produce an order."
    ok = false
  }

  return ok
}

async function submit() {
  if (!validate()) return
  submitting.value = true
  try {
    const rows = parameters.value
      .filter((p) => {
        const row = scores[p.name]
        return p.value_type === "Rating" ? !!row.rating : row.value !== null && row.value !== ""
      })
      .map((p) => {
        const row = scores[p.name]
        return p.value_type === "Rating"
          ? { parameter: p.name, rating: row.rating, remarks: row.remarks || undefined }
          : { parameter: p.name, value: row.value, remarks: row.remarks || undefined }
      })

    const created = await call("field_sales.api.demo.create_evaluation", {
      product_demo: props.name,
      item_code: props.item_code,
      evaluated_on: outcome.evaluated_on,
      outcome: outcome.outcome,
      order_received: outcome.order_received,
      no_order_reason: outcome.order_received === "1" ? undefined : outcome.no_order_reason || undefined,
      remarks: outcome.remarks || undefined,
      parameters: rows,
    })
    await call("field_sales.api.demo.submit_evaluation", { name: created.name })
    router.push({ name: "DemoDetail", params: { name: props.name } })
  } catch (err) {
    formError.value = err.messages?.[0] || err.message || "Could not save this evaluation."
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

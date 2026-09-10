<template>
  <FormView
    title="File visit expense"
    fallback="/journey-plan/trips"
    :steps="steps"
    :initial-data="initialData"
    submit-label="File expense claim"
    :on-submit="createClaim"
    @saved="onSaved"
  >
    <template #step-0="{ data }">
      <div class="space-y-4">
        <div class="bg-surface rounded-2xl p-4">
          <p class="text-xs font-display text-ink-3">Journey Plan</p>
          <p class="text-sm font-display font-semibold text-ink">{{ journeyPlan }}</p>
        </div>

        <div class="bg-surface rounded-2xl p-4 space-y-3">
          <div class="flex items-center justify-between">
            <label class="text-sm font-display text-ink-2">Expenses <span class="text-crit">*</span></label>
          </div>

          <div v-if="data.expenses.length" class="space-y-3">
            <div
              v-for="(row, i) in data.expenses"
              :key="i"
              class="border border-rule rounded-[10px] p-3 space-y-2"
            >
              <div class="flex items-start justify-between gap-2">
                <span class="w-6 h-6 rounded-full bg-accent-soft text-accent-ink text-xs font-display flex items-center justify-center shrink-0">
                  {{ i + 1 }}
                </span>
                <button type="button" class="w-7 h-7 rounded-full border border-rule text-ink-2 shrink-0" @click="data.expenses.splice(i, 1)">
                  ×
                </button>
              </div>
              <select v-model="row.expense_type" class="w-full h-[44px] rounded-[10px] border border-rule bg-surface px-3 text-sm">
                <option value="" disabled>Select expense type</option>
                <option v-for="t in expenseTypes" :key="t.name" :value="t.name">{{ t.name }}</option>
              </select>
              <div class="flex gap-2">
                <input v-model="row.expense_date" type="date" class="w-1/2 h-[44px] rounded-[10px] border border-rule bg-surface px-3 text-sm" />
                <input v-model.number="row.amount" type="number" min="0" step="0.01" placeholder="Amount" class="w-1/2 h-[44px] rounded-[10px] border border-rule bg-surface px-3 text-sm" />
              </div>
              <input v-model="row.description" placeholder="Description (optional)" class="w-full h-[44px] rounded-[10px] border border-rule bg-surface px-3 text-sm" />
            </div>
          </div>
          <p v-else class="text-xs text-ink-3">No expenses added yet.</p>

          <button
            type="button"
            class="w-full py-2.5 rounded-[10px] border border-dashed border-rule text-sm font-display text-ink-2"
            @click="data.expenses.push({ expense_type: '', expense_date: today, amount: null, description: '' })"
          >
            + Add expense
          </button>
        </div>
      </div>
    </template>
  </FormView>
</template>

<script setup>
import { onMounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { call } from "frappe-ui"
import FormView from "@/components/FormView.vue"
import { queueWrite } from "@/composables/offlineQueue"

const route = useRoute()
const router = useRouter()

const journeyPlan = route.query.journey_plan || ""
const today = new Date().toISOString().slice(0, 10)

const initialData = {
  expenses: [{ expense_type: "", expense_date: today, amount: null, description: "" }],
}

const expenseTypes = ref([])

onMounted(async () => {
  try {
    expenseTypes.value = (await call("field_sales.api.expense_claim.expense_claim_type_list")) || []
  } catch {
    expenseTypes.value = []
  }
})

const steps = [
  {
    title: "Expenses",
    fields: [],
    validate: (d) => {
      if (!journeyPlan) return "No journey plan linked - go back and use the button on the plan's own page."
      const rows = (d.expenses || []).filter((r) => r.expense_type)
      if (!rows.length) return "Add at least one expense."
      if (rows.some((r) => !r.amount || r.amount <= 0)) return "Every expense needs an amount."
      return ""
    },
  },
]

async function createClaim(data) {
  const args = {
    journey_plan: journeyPlan,
    expenses: data.expenses
      .filter((r) => r.expense_type)
      .map((r) => ({
        expense_type: r.expense_type,
        expense_date: r.expense_date,
        amount: r.amount,
        description: r.description || undefined,
      })),
  }
  // Unlike Sample/Collateral Request, this never auto-submits: Expense
  // Claim's own on_submit refuses while approval_status is still Draft
  // (HRMS requires an Expense Approver to Approve/Reject first) - filing
  // the claim as a draft IS the rep's whole action here.
  return queueWrite({
    method: "field_sales.api.expense_claim.create_visit_expense_claim",
    args,
    label: "Visit expense claim",
  })
}

function onSaved(result) {
  if (result?.queued || result?.name) {
    router.push({ name: "JourneyPlanDetail", params: { name: journeyPlan } })
  }
}
</script>

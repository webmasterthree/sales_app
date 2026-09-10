<template>
  <DetailView ref="detailRef" :name="name" :config="config">
    <template #extra="{ doc }">
      <details v-if="doc.trips?.length" open class="bg-surface rounded-2xl border border-rule overflow-hidden">
        <summary class="px-4 py-3 font-display font-semibold cursor-pointer select-none">Trips</summary>
        <div class="px-4 pb-4 space-y-3">
          <div v-for="(row, i) in doc.trips" :key="row.name" class="text-sm py-2 border-b border-rule-soft last:border-0">
            <div class="flex justify-between items-baseline">
              <span class="font-display text-ink">Trip {{ i + 1 }}</span>
              <span class="text-ink-2">{{ row.mode_of_travel }}</span>
            </div>
            <p class="text-ink-2">
              {{ [row.travel_from_city, row.travel_from_district, row.travel_state_from].filter(Boolean).join(", ") }}
              <span class="text-ink-3">→</span>
              {{ row.same_as_from_address
                ? "Same as from"
                : [row.travel_to_city, row.travel_to_district, row.travel_to_state].filter(Boolean).join(", ") }}
            </p>
            <p v-if="row.primary_customer" class="text-xs text-ink-3">Primary: {{ row.primary_customer }}</p>
            <p v-if="row.secondary_customer" class="text-xs text-ink-3">Secondary: {{ row.secondary_customer }}</p>
          </div>
        </div>
      </details>
    </template>
  </DetailView>
</template>

<script setup>
import { onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"
import DetailView from "@/components/DetailView.vue"

const props = defineProps({ name: { type: String, required: true } })

const router = useRouter()

const detailRef = ref(null)

// Which workflow actions (Approve/Reject/reset-to-Pending) the signed-in
// user can actually take on this plan right now, computed server-side
// from the real Workflow (role + current state) - not guessed at here
// from role names, since those turned out not to be trustworthy (see the
// SE Role Profile cleanup).
const availableActions = ref([])

onMounted(async () => {
  try {
    availableActions.value = (await call("field_sales.api.journey_plan.journey_plan_actions", { name: props.name })) || []
  } catch {
    availableActions.value = []
  }
})

function canDo(action) {
  return availableActions.value.some((a) => a.action === action)
}

async function refreshActions() {
  try {
    availableActions.value = (await call("field_sales.api.journey_plan.journey_plan_actions", { name: props.name })) || []
  } catch {
    availableActions.value = []
  }
}

async function runWorkflowAction(action, doc, load) {
  await call("field_sales.api.journey_plan.apply_journey_plan_action", { name: doc.name, action })
  await load()
  await refreshActions()
}

const config = {
  title: (doc) => (doc ? `Journey Plan · ${doc.visit_date || doc.name}` : "Journey Plan"),
  method: "field_sales.api.journey_plan.journey_plan",
  fallback: "/journey-plan/trips",
  statusField: "workflow_state",
  sections: [
    {
      title: "Plan",
      fields: [
        { key: "visit_date", label: "Date" },
        { key: "nature_of_travel", label: "Nature of travel" },
        { key: "territory", label: "Territory" },
        { key: "sales_person_name", label: "Rep" },
        { key: "remarks", label: "Remarks" },
        { key: "workflow_state", label: "Workflow state" },
        { key: "expense_status", label: "Expense claim", pill: true },
      ],
    },
  ],
  actions: [
    {
      // A plan reaches docstatus 1 only via this Approve action from an
      // NSM (or the ASM's own Approve, which moves it to "ASM Approved"
      // and still needs NSM sign-off after) - never by the rep submitting
      // their own plan. Which of these two shows, if either, depends on
      // the plan's current state and the signed-in user's real role,
      // both resolved server-side in journey_plan_actions.
      label: "Approve",
      visible: () => canDo("Approve"),
      confirm: "Approve this journey plan?",
      handler: (doc, load) => runWorkflowAction("Approve", doc, load),
    },
    {
      label: "Reject",
      visible: () => canDo("Reject"),
      confirm: "Reject this journey plan? The rep will need to revise it before it can be reviewed again.",
      handler: (doc, load) => runWorkflowAction("Reject", doc, load),
    },
    {
      // Covers both real uses of this transition: a rep revising a
      // Rejected plan, or anyone resetting an ASM Approved plan back for
      // further review.
      label: "Reset to Pending",
      visible: () => canDo("Pending"),
      handler: (doc, load) => runWorkflowAction("Pending", doc, load),
    },
    {
      // Navigation only, same pattern as Field Visit's "Convert to Order" -
      // nothing is created here; the expense claim form does that once the
      // rep has actually entered the expenses and reviewed them.
      label: "File Visit Expense",
      visible: (doc) => doc.docstatus === 1,
      handler: async (doc) => {
        router.push({ name: "ExpenseClaimNew", query: { journey_plan: doc.name } })
      },
    },
  ],
}
</script>

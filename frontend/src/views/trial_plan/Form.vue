<template>
  <FormView
    title="New trial plan"
    fallback="/trial-plan"
    :steps="steps"
    :initial-data="initialData"
    submit-label="Submit"
    :on-submit="createTrial"
    @saved="onSaved"
  >
    <template #step-0="{ data }">
      <div class="bg-surface rounded-2xl p-4 space-y-4">
        <CustomerPicker
          label="Select Customer *"
          :multiple="false"
          :model-value="data.customer"
          @update:model-value="onCustomerPicked(data, $event)"
        />

        <!-- Customer Type and Channel Partner are fixed on the customer's
             own master record (Customer.customer_level / custom_channel_partner)
             - not something a rep chooses per trial. See field_trial_plan.py's
             set_channel_partner for why this mirrors Field Visit's identical
             derivation rather than letting a rep pick a different channel
             partner for the same customer on different trials. -->
        <div v-if="data.customer">
          <label class="block text-sm font-display text-ink-2 mb-1">Customer Type</label>
          <div class="rounded-[10px] border border-rule bg-surface-2 px-3 py-2.5 text-sm text-ink">
            {{ data.visit_type || "Primary" }}
            <span v-if="data.visit_type === 'Secondary'" class="text-ink-2">
              · via {{ channelPartnerName || data.channel_partner }}
            </span>
          </div>
          <p class="text-xs text-ink-3 mt-1">From this customer's own record - not editable here.</p>
        </div>

        <ItemPicker
          label="Product Name *"
          :model-value="data.item_code"
          :display="data.item_name"
          @update:model-value="data.item_code = $event"
          @picked="(item) => (data.item_name = item?.item_name || '')"
        />

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Select Delivery Date <span class="text-crit">*</span></label>
          <input v-model="data.delivery_date" type="date" class="w-full h-[52px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm" />
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Remarks (optional)</label>
          <textarea v-model="data.remarks" rows="3" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" />
        </div>
      </div>
    </template>
  </FormView>
</template>

<script setup>
import { ref } from "vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"
import FormView from "@/components/FormView.vue"
import CustomerPicker from "@/components/CustomerPicker.vue"
import ItemPicker from "@/components/ItemPicker.vue"
import { queueWrite } from "@/composables/offlineQueue"

const router = useRouter()
const channelPartnerName = ref("")

async function onCustomerPicked(data, customerName) {
  data.customer = customerName
  data.visit_type = "Primary"
  data.channel_partner = ""
  channelPartnerName.value = ""
  if (!customerName) return
  try {
    const detail = await call("field_sales.api.customers.customer", { name: customerName })
    // Mirrors field_trial_plan.py's set_channel_partner - shown here so the
    // rep sees it before submitting, not decided here. The server derives
    // its own copy from the same Customer record regardless of what's sent.
    data.visit_type = detail.customer_level || "Primary"
    data.channel_partner = detail.custom_channel_partner || ""
    channelPartnerName.value = detail.cp_name || detail.custom_channel_partner || ""
  } catch {
    // Leave the defaults - the server-side derivation is authoritative anyway.
  }
}

const initialData = {
  visit_type: "Primary",
  customer: "",
  channel_partner: "",
  item_code: "",
  item_name: "",
  delivery_date: new Date().toISOString().slice(0, 10),
  remarks: "",
}

const steps = [
  {
    title: "Trial Details",
    fields: [],
    validate: (d) => {
      if (!d.customer) return "Select the customer this trial is for."
      if (d.visit_type === "Secondary" && !d.channel_partner) return "A Secondary trial needs a Channel Partner."
      if (!d.item_code) return "Choose the product being trialed."
      if (!d.delivery_date) return "Give a delivery date for this trial."
      return ""
    },
  },
]

async function createTrial(data) {
  const { item_name, ...args } = data
  return queueWrite({
    method: "field_sales.api.trial_plan.create_trial_plan",
    args,
    label: "New trial plan",
  })
}

function onSaved(result) {
  if (result?.queued) {
    router.push({ name: "TrialPlanList" })
  } else if (result?.name) {
    router.push({ name: "TrialPlanDetail", params: { name: result.name } })
  }
}
</script>

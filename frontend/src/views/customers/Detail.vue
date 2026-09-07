<template>
  <DetailView :name="name" :config="config">
    <template #extra="{ doc }">
      <RouterLink
        :to="{ name: 'CustomerLedger', params: { name: doc.name } }"
        class="flex items-center justify-between bg-surface rounded-2xl p-4 active:opacity-80"
      >
        <span class="font-display font-semibold text-ink">View Ledger</span>
        <Icon name="chevron-right" :size="18" class="text-ink-3" />
      </RouterLink>

      <div v-if="doc.addresses?.length" class="bg-surface rounded-2xl p-4">
        <p class="font-display font-semibold mb-2">Addresses</p>
        <div v-for="a in doc.addresses" :key="a.name" class="text-sm py-1 border-b border-rule-soft last:border-0">
          <p>{{ [a.address_line1, a.address_line2, a.city, a.state, a.pincode].filter(Boolean).join(", ") }}</p>
          <p class="text-xs text-ink-3">{{ a.address_type }}</p>
        </div>
      </div>
      <div v-if="doc.contacts?.length" class="bg-surface rounded-2xl p-4">
        <p class="font-display font-semibold mb-2">Contacts</p>
        <div v-for="c in doc.contacts" :key="c.name" class="text-sm py-1 border-b border-rule-soft last:border-0">
          <p>{{ [c.first_name, c.last_name].filter(Boolean).join(" ") }}</p>
          <p class="text-xs text-ink-3">{{ c.mobile_no }} {{ c.email_id }}</p>
        </div>
      </div>

      <div v-if="doc.credit_limits?.length" class="bg-surface rounded-2xl p-4">
        <p class="font-display font-semibold mb-2">Credit information</p>
        <div v-for="c in doc.credit_limits" :key="c.name" class="flex justify-between text-sm py-1 border-b border-rule-soft last:border-0">
          <span class="text-ink-2">{{ c.company }}</span>
          <span class="text-ink">₹{{ c.credit_limit }}</span>
        </div>
      </div>

      <div v-if="doc.customer_consumption_info?.length" class="bg-surface rounded-2xl p-4">
        <p class="font-display font-semibold mb-2">Customer segment</p>
        <div v-for="s in doc.customer_consumption_info" :key="s.name" class="text-sm py-1 border-b border-rule-soft last:border-0">
          <div class="flex justify-between">
            <span class="text-ink">{{ s.product_name }}</span>
            <span class="text-ink-2">{{ s.consumption_qty }} {{ s.uom }}</span>
          </div>
          <p class="text-xs text-ink-3">{{ [s.segment, s.category_type].filter(Boolean).join(" · ") }}</p>
        </div>
      </div>
    </template>
  </DetailView>

  <!-- Request a change: replaces a raw window.prompt() with a proper sheet,
       matching the bottom-sheet pattern already used for address picking
       elsewhere in the app. -->
  <div
    v-if="requestOpen"
    class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40"
    @click.self="closeRequest"
  >
    <div class="bg-surface w-full sm:max-w-sm sm:rounded-2xl rounded-t-2xl overflow-hidden pb-safe">
      <div class="flex justify-center pt-2 sm:hidden"><div class="w-10 h-1 rounded-full bg-rule"></div></div>
      <div class="px-5 pt-3 pb-4">
        <p class="text-lg font-display font-bold text-ink mb-3">Change Request</p>
        <label class="block text-xs font-display font-semibold text-ink-2 mb-1">What needs correcting?</label>
        <textarea
          v-model="requestText"
          rows="4"
          class="w-full rounded-[13px] border border-rule bg-surface px-3 py-2 text-sm"
          placeholder="e.g. Shop moved to a new address, segment is wrong…"
        />
        <p v-if="requestError" class="text-xs text-crit mt-2">{{ requestError }}</p>
        <div class="flex gap-2 mt-4">
          <button type="button" class="flex-1 h-[48px] rounded-[13px] border border-rule text-ink font-display font-medium" @click="closeRequest">
            Cancel
          </button>
          <button
            type="button"
            class="flex-1 h-[48px] rounded-[13px] bg-accent text-accent-fg font-display font-bold disabled:opacity-60"
            :disabled="submittingRequest"
            @click="submitRequest"
          >
            {{ submittingRequest ? "Sending…" : "Submit" }}
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Change Log: past requests raised for this customer, with status. -->
  <div
    v-if="logOpen"
    class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40"
    @click.self="logOpen = false"
  >
    <div class="bg-surface w-full sm:max-w-sm sm:rounded-2xl rounded-t-2xl overflow-hidden pb-safe max-h-[70vh] flex flex-col">
      <div class="flex justify-center pt-2 sm:hidden shrink-0"><div class="w-10 h-1 rounded-full bg-rule"></div></div>
      <div class="px-5 pt-3 pb-2 flex items-center justify-between shrink-0">
        <p class="text-lg font-display font-bold text-ink">Change Request</p>
        <button type="button" class="w-8 h-8 rounded-full flex items-center justify-center text-ink-3" aria-label="Close" @click="logOpen = false">
          <Icon name="close" :size="16" />
        </button>
      </div>
      <div class="px-5 pb-5 overflow-y-auto">
        <p v-if="logLoading" class="text-sm text-ink-3 text-center py-6">Loading…</p>
        <p v-else-if="!changeLog.length" class="text-sm text-ink-3 text-center py-6">No change requests raised yet.</p>
        <div
          v-for="c in changeLog"
          :key="c.name"
          class="py-3 border-b border-rule-soft last:border-0 flex justify-between gap-3"
        >
          <p class="text-sm text-ink leading-relaxed flex-1">{{ c.requested_change }}</p>
          <StatusPill :status="c.status" class="shrink-0" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue"
import { call } from "frappe-ui"
import DetailView from "@/components/DetailView.vue"
import StatusPill from "@/components/StatusPill.vue"
import Icon from "@/components/Icon.vue"

const props = defineProps({ name: { type: String, required: true } })

const requestOpen = ref(false)
const requestText = ref("")
const requestError = ref("")
const submittingRequest = ref(false)

const logOpen = ref(false)
const logLoading = ref(false)
const changeLog = ref([])

function closeRequest() {
  requestOpen.value = false
  requestText.value = ""
  requestError.value = ""
}

async function submitRequest() {
  if (!requestText.value.trim()) {
    requestError.value = "Describe what needs changing."
    return
  }
  submittingRequest.value = true
  requestError.value = ""
  try {
    await call("field_sales.api.customers.request_customer_change", {
      customer: props.name, requested_change: requestText.value.trim(),
    })
    closeRequest()
  } catch (err) {
    requestError.value = err.messages?.[0] || err.message || "Could not submit the request."
  } finally {
    submittingRequest.value = false
  }
}

async function openLog() {
  logOpen.value = true
  logLoading.value = true
  try {
    changeLog.value = (await call("field_sales.api.customers.customer_change_requests", { customer: props.name })) || []
  } catch {
    changeLog.value = []
  } finally {
    logLoading.value = false
  }
}

const config = {
  title: (doc) => doc?.customer_name || doc?.name || "Customer",
  method: "field_sales.api.customers.customer",
  fallback: "/customers",
  sections: [
    {
      title: "Overview",
      // Business/compliance fields (email, GST, business type, proposed
      // credit) belong to the Primary/distributor account, not to each
      // Secondary outlet reached through one - see the legacy
      // my_customer_form's identical field split for Primary vs Secondary.
      fields: [
        { key: "customer_name", label: "Customer name" },
        { key: "customer_level", label: "Customer type" },
        {
          key: "custom_channel_partner",
          label: "Channel Partner",
          format: (v, doc) => doc.cp_name || v,
          hidden: (doc) => doc.customer_level !== "Secondary",
        },
        { key: "customer_group", label: "Group" },
        { key: "territory", label: "Territory" },
        { key: "mobile_no", label: "Mobile" },
        { key: "email_id", label: "Email", hidden: (doc) => doc.customer_level === "Secondary" },
        { key: "business_type", label: "Business type", hidden: (doc) => doc.customer_level === "Secondary" },
        { key: "gstin", label: "GST No.", hidden: (doc) => doc.customer_level === "Secondary" },
        { key: "proposed_credit", label: "Proposed credit", hidden: (doc) => doc.customer_level === "Secondary" },
        { key: "payment_terms", label: "Payment term" },
        { key: "disabled", label: "Disabled", format: (v) => (v ? "Yes" : "No") },
      ],
    },
  ],
  actions: [
    {
      label: "Change Request",
      tone: "muted",
      handler: () => { requestOpen.value = true },
    },
    {
      label: "Change Log",
      handler: openLog,
    },
  ],
}
</script>

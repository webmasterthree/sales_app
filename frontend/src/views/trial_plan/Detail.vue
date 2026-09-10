<template>
  <DetailView ref="detailRef" :name="name" :config="config">
    <template #extra="{ doc }">
      <div class="bg-surface rounded-2xl border border-rule p-4">
        <p class="font-display font-bold text-sm text-ink mb-3">Attendance</p>
        <div class="flex items-center justify-between py-1.5 border-b border-rule-soft">
          <span class="text-sm text-ink">Sample distributed</span>
          <StatusPill :status="doc.sample_distributed ? 'Confirmed' : 'Pending'" />
        </div>
        <div class="flex items-center justify-between py-1.5 border-b border-rule-soft">
          <span class="text-sm text-ink">Customer feedback collected</span>
          <StatusPill :status="doc.feedback_collected ? 'Confirmed' : 'Pending'" />
        </div>
        <div class="flex items-center justify-between py-1.5">
          <span class="text-sm text-ink">Follow-up order</span>
          <RouterLink
            v-if="doc.follow_up_order"
            :to="{ name: 'OrderDetail', params: { name: doc.follow_up_order } }"
            class="text-xs font-display font-semibold text-accent-ink underline"
          >{{ doc.follow_up_order }}</RouterLink>
          <StatusPill v-else status="Pending" />
        </div>
      </div>

      <CommentThread doctype="Field Trial Plan" :docname="doc.name" />
    </template>
  </DetailView>

  <div
    v-if="attendanceOpen"
    class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40"
    @click.self="closeAttendance"
  >
    <div class="bg-surface w-full sm:max-w-sm sm:rounded-2xl rounded-t-2xl overflow-hidden pb-safe">
      <div class="flex justify-center pt-2 sm:hidden"><div class="w-10 h-1 rounded-full bg-rule"></div></div>
      <div class="px-5 pt-3 pb-4">
        <p class="text-lg font-display font-bold text-ink mb-4">Record attendance</p>

        <label class="flex items-center gap-2.5 text-sm text-ink py-2 border-b border-rule-soft">
          <input type="checkbox" v-model="form.sample_distributed" class="w-4 h-4 accent-accent" />
          Sample distributed
        </label>
        <label class="flex items-center gap-2.5 text-sm text-ink py-2 border-b border-rule-soft mb-4">
          <input type="checkbox" v-model="form.feedback_collected" class="w-4 h-4 accent-accent" />
          Customer feedback collected
        </label>

        <label class="block text-xs font-display font-bold text-ink-2 mb-1.5">Follow-up order</label>
        <select v-model="form.follow_up_order" class="w-full h-[48px] rounded-[13px] border border-rule bg-surface px-3.5 text-sm font-medium mb-1">
          <option value="">None yet</option>
          <option v-for="o in customerOrders" :key="o.name" :value="o.name">{{ o.name }} · ₹{{ o.grand_total }}</option>
        </select>
        <p class="text-xs text-ink-3 mb-4">Only this customer's own submitted orders are listed.</p>

        <p v-if="attendanceError" class="text-xs text-crit mb-3">{{ attendanceError }}</p>

        <div class="flex gap-2.5">
          <button type="button" class="flex-1 h-[50px] rounded-[14px] border border-rule text-ink font-display font-bold" @click="closeAttendance">Cancel</button>
          <button
            type="button"
            class="flex-1 h-[50px] rounded-[14px] bg-ink text-white font-display font-bold disabled:opacity-60"
            :disabled="savingAttendance"
            @click="submitAttendance"
          >{{ savingAttendance ? "Saving…" : "Save" }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue"
import { call } from "frappe-ui"
import DetailView from "@/components/DetailView.vue"
import StatusPill from "@/components/StatusPill.vue"
import CommentThread from "@/components/CommentThread.vue"

defineProps({ name: { type: String, required: true } })

const attendanceOpen = ref(false)
const attendanceError = ref("")
const savingAttendance = ref(false)
const customerOrders = ref([])
const form = reactive({ sample_distributed: false, feedback_collected: false, follow_up_order: "" })
let attendanceTarget = null

async function openAttendance(doc, reload) {
  attendanceTarget = { doc, reload }
  form.sample_distributed = !!doc.sample_distributed
  form.feedback_collected = !!doc.feedback_collected
  form.follow_up_order = doc.follow_up_order || ""
  attendanceError.value = ""
  attendanceOpen.value = true
  try {
    const page = await call("field_sales.api.catalog.order_list", {
      customer: doc.customer,
      current_page: 1,
      limit: 20,
    })
    customerOrders.value = (page?.records || []).filter((o) => o.docstatus === 1)
  } catch {
    customerOrders.value = []
  }
}

function closeAttendance() {
  attendanceOpen.value = false
  attendanceTarget = null
}

async function submitAttendance() {
  savingAttendance.value = true
  attendanceError.value = ""
  try {
    await call("field_sales.api.trial_plan.update_attendance", {
      name: attendanceTarget.doc.name,
      sample_distributed: form.sample_distributed ? 1 : 0,
      feedback_collected: form.feedback_collected ? 1 : 0,
      follow_up_order: form.follow_up_order || "",
    })
    await attendanceTarget.reload()
    closeAttendance()
  } catch (err) {
    attendanceError.value = err.messages?.[0] || err.message || "Could not save attendance."
  } finally {
    savingAttendance.value = false
  }
}

const config = {
  title: (doc) => (doc ? `Trial · ${doc.item_name || doc.name}` : "Trial Plan"),
  method: "field_sales.api.trial_plan.trial_plan",
  fallback: "/trial-plan",
  statusField: "status",
  sections: [
    {
      title: "Trial Details",
      fields: [
        { key: "customer_name", label: "Customer" },
        { key: "visit_type", label: "Customer Type" },
        { key: "channel_partner", label: "Channel Partner" },
        { key: "item_name", label: "Product" },
        { key: "delivery_date", label: "Delivery Date" },
        { key: "territory", label: "Territory" },
        { key: "sales_person_name", label: "Requested By" },
        { key: "remarks", label: "Remarks" },
      ],
    },
  ],
  actions: [
    {
      label: "Submit plan",
      visible: (doc) => doc.docstatus === 0,
      confirm: "Submit this trial plan? It cannot be edited afterwards.",
      method: "field_sales.api.trial_plan.submit_trial_plan",
    },
    {
      label: "Record attendance",
      visible: (doc) => doc.docstatus === 1 && doc.status !== "Completed",
      handler: openAttendance,
    },
  ],
}
</script>

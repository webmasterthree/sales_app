<template>
  <DetailView :name="name" :config="config">
    <template #extra="{ doc }">
      <!-- The real approval process here is single-stage (Pending, then one
           Approve/Reject decision) - shown honestly as two steps, not the
           three-tier Sales Exec/ASM/RSM chain a reference design mockup
           showed, which has no equivalent in this app's actual workflow. -->
      <div class="bg-surface rounded-2xl border border-rule p-4">
        <p class="font-display font-bold text-sm text-ink mb-3">Status</p>
        <div v-for="(step, i) in statusSteps(doc)" :key="step.role" class="flex gap-3" :class="i < statusSteps(doc).length - 1 ? 'pb-4' : ''">
          <div class="flex flex-col items-center shrink-0 w-[22px]">
            <span
              class="w-5 h-5 rounded-full flex items-center justify-center text-white text-[10px] font-bold"
              :class="step.done ? 'bg-accent' : step.failed ? 'bg-crit' : 'bg-rule'"
            >{{ step.done ? "✓" : step.failed ? "✕" : "" }}</span>
            <span v-if="i < statusSteps(doc).length - 1" class="flex-1 w-0.5 bg-rule mt-0.5" style="min-height: 20px" />
          </div>
          <div class="flex-1 min-w-0 -mt-0.5">
            <p class="text-sm font-display font-semibold text-ink">{{ step.role }}</p>
            <p class="text-xs text-ink-2">{{ step.note }}</p>
          </div>
        </div>
      </div>

      <details v-if="doc.documents?.length" class="bg-surface rounded-2xl border border-rule overflow-hidden">
        <summary class="px-4 py-3 font-display font-semibold cursor-pointer select-none">Documents</summary>
        <div class="px-4 pb-4 space-y-3">
          <div v-for="row in doc.documents" :key="row.name" class="space-y-1">
            <p class="text-sm font-display font-medium text-ink">{{ row.document_type }}<span v-if="row.number" class="text-ink-2 font-normal"> · {{ row.number }}</span></p>
            <a v-if="row.attachment" :href="row.attachment" target="_blank" rel="noopener" class="block">
              <img :src="row.attachment" class="w-full max-h-40 object-cover rounded-xl border border-rule" :alt="row.document_type" />
            </a>
          </div>
        </div>
      </details>

      <CommentThread doctype="Customer Onboarding" :docname="doc.name" />
    </template>
  </DetailView>

  <div
    v-if="rejectOpen"
    class="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40"
    @click.self="closeReject"
  >
    <div class="bg-surface w-full sm:max-w-sm sm:rounded-2xl rounded-t-2xl overflow-hidden pb-safe">
      <div class="flex justify-center pt-2 sm:hidden"><div class="w-10 h-1 rounded-full bg-rule"></div></div>
      <div class="px-5 pt-3 pb-4">
        <p class="text-lg font-display font-bold text-ink mb-3">Reject this request</p>
        <label class="block text-xs font-display font-semibold text-ink-2 mb-1">Reason <span class="text-crit">*</span></label>
        <textarea v-model="rejectRemarks" rows="3" class="w-full rounded-[13px] border border-rule bg-surface px-3 py-2 text-sm" placeholder="Why is this being rejected?" />
        <p v-if="rejectError" class="text-xs text-crit mt-2">{{ rejectError }}</p>
        <div class="flex gap-2 mt-4">
          <button type="button" class="flex-1 h-[48px] rounded-[13px] border border-rule text-ink font-display font-medium" @click="closeReject">Cancel</button>
          <button
            type="button"
            class="flex-1 h-[48px] rounded-[13px] bg-crit text-white font-display font-bold disabled:opacity-60"
            :disabled="rejecting"
            @click="submitReject"
          >
            {{ rejecting ? "Rejecting…" : "Reject" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue"
import { call } from "frappe-ui"
import DetailView from "@/components/DetailView.vue"
import CommentThread from "@/components/CommentThread.vue"

defineProps({ name: { type: String, required: true } })

function formatDate(v) {
  if (!v) return ""
  const d = new Date(v)
  return `${d.getDate()} ${d.toLocaleDateString("en-US", { month: "short" })}`
}

// Two real steps - submitted, then one Approve/Reject decision - matching
// what the backend actually does (see customer_onboarding.py's
// approve_onboarding/reject_onboarding). No fabricated intermediate tiers.
function statusSteps(doc) {
  const submitted = {
    role: "Submitted",
    note: doc.docstatus >= 1
      ? `By ${doc.sales_person_name || "—"} · ${formatDate(doc.request_date)}`
      : "Still a draft",
    done: doc.docstatus >= 1,
    failed: false,
  }
  const decision = { role: "Decision" }
  if (doc.status === "Approved") {
    decision.note = `Approved${doc.decided_on ? " · " + formatDate(doc.decided_on) : ""}`
    decision.done = true
    decision.failed = false
  } else if (doc.status === "Rejected") {
    decision.note = [doc.decision_remarks, doc.decided_on ? formatDate(doc.decided_on) : ""].filter(Boolean).join(" · ") || "Rejected"
    decision.done = false
    decision.failed = true
  } else {
    decision.note = doc.docstatus >= 1 ? "Awaiting review" : "Not submitted yet"
    decision.done = false
    decision.failed = false
  }
  return [submitted, decision]
}

const rejectOpen = ref(false)
const rejectRemarks = ref("")
const rejectError = ref("")
const rejecting = ref(false)
let rejectTarget = null

function openReject(doc, reload) {
  rejectTarget = { doc, reload }
  rejectOpen.value = true
}

function closeReject() {
  rejectOpen.value = false
  rejectRemarks.value = ""
  rejectError.value = ""
  rejectTarget = null
}

async function submitReject() {
  if (!rejectRemarks.value.trim()) {
    rejectError.value = "A reason is required."
    return
  }
  rejecting.value = true
  rejectError.value = ""
  try {
    await call("field_sales.field_sales.doctype.customer_onboarding.customer_onboarding.reject_onboarding", {
      name: rejectTarget.doc.name, remarks: rejectRemarks.value.trim(),
    })
    await rejectTarget.reload()
    closeReject()
  } catch (err) {
    rejectError.value = err.messages?.[0] || err.message || "Could not reject this request."
  } finally {
    rejecting.value = false
  }
}

const config = {
  title: (doc) => doc?.customer_name || doc?.name || "Onboarding",
  method: "field_sales.api.onboarding.onboarding",
  fallback: "/onboarding",
  statusField: "status",
  sections: [
    {
      title: "Business details",
      fields: [
        { key: "business_type", label: "Business type" },
        { key: "gst_category", label: "GST category" },
        { key: "gstin", label: "GSTIN" },
        { key: "pan", label: "PAN" },
        { key: "market_segment", label: "Market segment" },
        { key: "customer_group", label: "Customer group" },
      ],
    },
    {
      title: "Contact & territory",
      fields: [
        { key: "location", label: "Existing address" },
        { key: "address_line1", label: "Address line 1" },
        { key: "address_line2", label: "Address line 2" },
        { key: "city", label: "City" },
        { key: "district", label: "District" },
        { key: "state", label: "State" },
        { key: "pincode", label: "Pincode" },
        { key: "contact_person", label: "Contact person" },
        { key: "contact_number", label: "Contact number" },
        { key: "territory", label: "Territory" },
        { key: "sales_person_name", label: "Filed by" },
      ],
    },
    {
      title: "Credit terms",
      fields: [
        { key: "proposed_credit", label: "Proposed terms" },
        { key: "credit_days", label: "Credit days" },
        { key: "credit_limit", label: "Credit limit" },
      ],
    },
    {
      title: "Decision",
      fields: [
        { key: "decided_on", label: "Decided on" },
        { key: "decision_remarks", label: "Remarks" },
        { key: "customer", label: "Linked customer" },
      ],
    },
  ],
  actions: [
    {
      label: "Submit for approval",
      visible: (doc) => doc.docstatus === 0,
      confirm: "Submit this onboarding request for approval?",
      method: "field_sales.api.onboarding.submit_onboarding",
    },
    {
      label: "Approve",
      visible: (doc) => doc.docstatus === 1 && doc.status === "Pending",
      confirm: "Approve this onboarding request? A customer record will be created.",
      method: "field_sales.field_sales.doctype.customer_onboarding.customer_onboarding.approve_onboarding",
    },
    {
      label: "Reject",
      tone: "crit",
      visible: (doc) => doc.docstatus === 1 && doc.status === "Pending",
      handler: openReject,
    },
  ],
}
</script>

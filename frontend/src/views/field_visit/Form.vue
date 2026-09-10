<template>
  <FormView
    title="New visit"
    fallback="/visits"
    :steps="steps"
    :initial-data="initialData"
    submit-label="Create visit"
    :on-submit="createVisit"
    @saved="onSaved"
  >
    <template #step-0="{ data }">
      <div class="bg-surface rounded-2xl p-4 space-y-4">
        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">
            Party type <span class="text-crit">*</span>
          </label>
          <select v-model="data.party_type" class="w-full h-[52px] rounded-[10px] border border-rule bg-surface text-ink appearance-none px-3 text-sm">
            <option value="">Select…</option>
            <option value="Customer">Customer</option>
            <option value="Prospect">Prospect</option>
          </select>
        </div>

        <!-- Primary/Secondary here only narrows which list the search box
             looks in - unlike the Prospect path's Visit type toggle below,
             it never sets data.visit_type itself. A real Customer's type is
             still read from its own record once picked (see the read-only
             "Customer type" display just below), whichever list it was
             found through. Two lists rather than one combined search
             because a Secondary customer is reached through - and searched
             for via - its own outlet name, not by browsing the same list as
             every distributor. -->
        <div v-if="data.party_type === 'Customer'" class="flex gap-2">
          <button
            v-for="opt in ['Primary', 'Secondary']"
            :key="opt"
            type="button"
            class="flex-1 py-2 rounded-[10px] text-sm font-display border"
            :class="customerSearchScope === opt ? 'bg-accent text-accent-fg border-accent' : 'bg-surface border-rule text-ink-2'"
            @click="onCustomerScopeChanged(data, opt)"
          >
            {{ opt }}
          </button>
        </div>
        <CustomerPicker
          v-if="data.party_type === 'Customer'"
          :multiple="false"
          label="Customer"
          :extra-filters="{ customer_level: customerSearchScope }"
          :model-value="data.customer"
          @update:model-value="onCustomerPicked(data, $event)"
        />
        <div v-else-if="data.party_type === 'Prospect'">
          <label class="block text-sm font-display text-ink-2 mb-1">Prospect name (if new)</label>
          <input v-model="data.prospect_name" class="w-full h-[52px] rounded-[10px] border border-rule bg-surface text-ink appearance-none px-3 text-sm" />
        </div>

        <!-- Visit type sits right after who the visit is for, since it's
             the next thing that decides what the rest of the form needs -
             a Customer's Primary/Secondary status and channel partner are
             fixed on that customer's own master record (Customer.customer_level
             / custom_channel_partner), not something a rep chooses per
             visit. Picking a different channel partner per visit would let
             the same customer end up attributed to different partners across
             visits, which the master data already has one answer for. -->
        <p v-if="customerLoadError" class="text-xs text-crit bg-crit/10 border border-crit/30 rounded-xl p-3">
          {{ customerLoadError }}
        </p>

        <div v-if="data.party_type === 'Customer' && data.customer">
          <label class="block text-sm font-display text-ink-2 mb-1">Customer type</label>
          <div class="rounded-[10px] border border-rule bg-surface-2 px-3 py-2.5 text-sm text-ink">
            {{ data.visit_type || "Primary" }}
            <span v-if="data.visit_type === 'Secondary'" class="text-ink-2">
              · via {{ channelPartnerName || data.channel_partner }}
            </span>
          </div>
          <p class="text-xs text-ink-3 mt-1">From this customer's own record - not editable here.</p>
        </div>

        <div v-if="data.party_type === 'Prospect'">
          <label class="block text-sm font-display text-ink-2 mb-1">Visit type <span class="text-crit">*</span></label>
          <div class="flex gap-2">
            <button
              v-for="opt in ['Primary', 'Secondary']"
              :key="opt"
              type="button"
              class="flex-1 py-2 rounded-[10px] text-sm font-display border"
              :class="data.visit_type === opt ? 'bg-accent text-accent-fg border-accent' : 'bg-surface border-rule text-ink-2'"
              @click="data.visit_type = opt; if (opt === 'Primary') data.channel_partner = ''"
            >
              {{ opt }}
            </button>
          </div>
          <p class="text-xs text-ink-3 mt-1">Primary: a direct call on the prospect above. Secondary: a call made through, or about, a channel partner.</p>
        </div>

        <div v-if="data.party_type === 'Prospect' && data.visit_type === 'Secondary'">
          <CustomerPicker
            label="Channel partner *"
            :multiple="false"
            distributors-only
            :model-value="data.channel_partner"
            @update:model-value="data.channel_partner = $event"
          />
          <p class="text-xs text-ink-3 mt-1">Required for a Secondary visit.</p>
        </div>

        <div v-for="f in beforeGeoFields" :key="f.key">
          <label class="block text-sm font-display text-ink-2 mb-1">
            {{ f.label }}
            <span v-if="f.required" class="text-crit">*</span>
            <span v-else class="text-ink-3 font-normal">(optional)</span>
          </label>
          <select
            v-if="f.type === 'select'"
            v-model="data[f.key]"
            class="w-full h-[52px] rounded-[10px] border border-rule bg-surface text-ink appearance-none px-3 text-sm"
          >
            <option value="">Select…</option>
            <option v-for="opt in f.options" :key="opt" :value="opt">{{ opt }}</option>
          </select>
          <input
            v-else
            v-model="data[f.key]"
            :type="f.type || 'text'"
            class="w-full h-[52px] rounded-[10px] border border-rule bg-surface text-ink appearance-none px-3 text-sm"
          />
        </div>

        <!-- State/District/City as a cascading pick from the real geography
             master (State/District/City doctypes) instead of free text -
             matches the pattern Journey Plan's own trip form already uses,
             and avoids a rep typing "Kolkatta" where the master says "Kolkata". -->
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <div>
            <label class="block text-xs text-ink-3 mb-1">State</label>
            <select
              :value="data.state"
              class="w-full h-[46px] rounded-[10px] border border-rule bg-surface px-2 text-sm"
              @change="onStateChange(data, $event.target.value)"
            >
              <option value="">Select state</option>
              <option v-for="s in states" :key="s.name" :value="s.state">{{ s.state }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-ink-3 mb-1">District</label>
            <select
              :value="data.district"
              class="w-full h-[46px] rounded-[10px] border border-rule bg-surface px-2 text-sm disabled:opacity-50"
              :disabled="!data.state"
              @change="onDistrictChange(data, $event.target.value)"
            >
              <option value="">Select district</option>
              <option v-for="d in districts" :key="d.name" :value="d.district">{{ d.district }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-ink-3 mb-1">City</label>
            <select
              v-model="data.city"
              class="w-full h-[46px] rounded-[10px] border border-rule bg-surface px-2 text-sm disabled:opacity-50"
              :disabled="!data.district"
            >
              <option value="">Select city</option>
              <option v-for="c in cities" :key="c.name" :value="c.city">{{ c.city }}</option>
            </select>
          </div>
        </div>

        <div v-for="f in afterGeoFields" :key="f.key">
          <label class="block text-sm font-display text-ink-2 mb-1">
            {{ f.label }}
            <span v-if="f.required" class="text-crit">*</span>
            <span v-else class="text-ink-3 font-normal">(optional)</span>
          </label>
          <input
            v-model="data[f.key]"
            :type="f.type || 'text'"
            class="w-full h-[52px] rounded-[10px] border border-rule bg-surface text-ink appearance-none px-3 text-sm"
          />
        </div>

        <div v-if="data.party_type === 'Customer' && data.location">
          <label class="block text-sm font-display text-ink-2 mb-1">Pin Location</label>
          <PinDropMap v-model="pinLocation" />
          <p class="text-xs text-ink-3 mt-1">
            Tap to correct exactly where this outlet is - saved when you create the visit.
          </p>
        </div>

        <!-- Mandatory GPS check-in, gating the rest of the wizard - see
             onCheckIn's own comment for why this is where the draft first
             gets created, rather than waiting for the form's final save. -->
        <div
          v-if="canAttemptCheckIn(data)"
          class="rounded-xl border p-4 space-y-2"
          :class="checkedIn ? 'border-accent bg-accent-soft' : 'border-warn/30 bg-warn/10'"
        >
          <p v-if="checkedIn" class="text-sm font-display font-medium text-accent-ink">
            ✓ Checked in{{ checkInTime ? ` at ${checkInTime}` : "" }}
          </p>
          <template v-else>
            <p class="text-xs text-warn font-display font-medium">Check in before you can continue.</p>
            <p v-if="geoError" class="text-xs text-crit">{{ geoError }}</p>
            <button
              type="button"
              class="w-full h-[46px] rounded-[10px] bg-accent text-accent-fg text-sm font-display font-medium disabled:opacity-60"
              :disabled="checkingIn"
              @click="onCheckIn(data)"
            >
              {{ checkingIn ? "Checking in…" : "Check In" }}
            </button>
          </template>
        </div>
      </div>
    </template>

    <template #step-1="{ data }">
      <div class="bg-surface rounded-2xl p-4 space-y-4">
        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Order status <span class="text-crit">*</span></label>
          <div class="flex gap-2">
            <button
              v-for="opt in ['With Order', 'Without Order']"
              :key="opt"
              type="button"
              class="flex-1 py-2 rounded-[10px] text-sm font-display border"
              :class="data.order_status === opt ? 'bg-accent text-accent-fg border-accent' : 'bg-surface border-rule text-ink-2'"
              @click="data.order_status = opt"
            >
              {{ opt }}
            </button>
          </div>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Deal confidence</label>
          <input
            type="range"
            min="1"
            max="5"
            step="1"
            v-model.number="data.deal_confidence"
            class="w-full accent-[var(--fs-accent)]"
          />
          <div class="flex justify-between text-xs text-ink-3 mt-1">
            <span v-for="n in 5" :key="n">{{ n }}</span>
          </div>
          <p class="text-center text-sm font-display mt-1">{{ confidenceLabel(data.deal_confidence) }}</p>
        </div>

        <div v-if="data.order_status === 'Without Order'">
          <label class="block text-sm font-display text-ink-2 mb-1">Reason <span class="text-crit">*</span></label>
          <select v-model="data.reason" class="w-full h-[44px] rounded-[10px] border border-rule bg-surface text-ink appearance-none px-3 text-sm">
            <option value="">Select a reason…</option>
            <option v-for="r in reasons" :key="r.name" :value="r.name">{{ r.reason }}</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Remarks (optional)</label>
          <textarea v-model="data.remarks" rows="3" class="w-full rounded-[10px] border border-rule bg-surface px-3 py-2 text-sm" />
        </div>

        <label class="flex items-center gap-2 text-sm">
          <input type="checkbox" v-model="data.demo_requested" true-value="1" false-value="0" />
          Demo requested at this outlet
        </label>
      </div>
    </template>

    <!-- Products pitched - mirrors the Flutter app's "Added Products" list:
         which items were pitched, in what segment, and who the customer
         currently buys them from. Entirely optional: a visit with no
         pitch (e.g. a pure relationship call) is a normal outcome. -->
    <template #step-2="{ data }">
      <div class="space-y-3">
        <p v-if="!data.pitched_items.length" class="text-sm text-ink-3 px-1">
          No products pitched yet. This is optional - add one below if you showed the customer anything.
        </p>

        <div v-for="(row, i) in data.pitched_items" :key="i" class="bg-surface rounded-2xl border border-rule p-4 space-y-3">
          <div class="flex items-center justify-between pb-1 border-b border-rule-soft">
            <span class="inline-flex items-center gap-2 text-sm font-display font-semibold text-ink">
              <span class="w-6 h-6 rounded-full bg-accent-soft text-accent-ink text-xs font-bold flex items-center justify-center shrink-0">{{ i + 1 }}</span>
              Product
            </span>
            <button
              type="button"
              class="w-8 h-8 rounded-full flex items-center justify-center text-ink-3 active:bg-surface-2"
              aria-label="Remove product"
              @click="data.pitched_items.splice(i, 1)"
            >
              <Icon name="close" :size="14" />
            </button>
          </div>

          <div>
            <label class="block text-xs text-ink-3 mb-1">Segment <span class="text-crit">*</span></label>
            <select
              :value="row.segment"
              class="w-full h-[42px] rounded-[10px] border border-rule bg-surface text-ink appearance-none px-3 text-sm"
              @change="onSegmentChanged(row, $event.target.value)"
            >
              <option value="">Select segment</option>
              <option v-for="s in segments" :key="s.name" :value="s.name">{{ s.name }}</option>
            </select>
          </div>

          <ItemPicker
            label="Item"
            :model-value="row.item_code"
            :display="row.item_code ? `${row.item_name || row.item_code}` : ''"
            :segment="row.segment"
            segment-required
            @update:model-value="row.item_code = $event"
            @picked="onItemPicked(row, $event)"
          />

          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block text-xs text-ink-3 mb-1">Qty</label>
              <input
                v-model.number="row.qty"
                type="number"
                min="0"
                step="0.01"
                class="w-full h-[42px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm"
              />
            </div>
            <div>
              <label class="block text-xs text-ink-3 mb-1">UOM</label>
              <input
                :value="row.uom"
                readonly
                placeholder="From item"
                class="w-full h-[42px] rounded-[10px] border border-rule bg-ground px-3 text-sm text-ink-3"
              />
            </div>
          </div>

          <div>
            <label class="block text-xs text-ink-3 mb-1">Currently using brand (optional)</label>
            <NamePicker
              v-model="row.competitor"
              placeholder="Search competitor…"
              :fetcher="searchCompetitors"
            />
          </div>
        </div>

        <button
          type="button"
          class="w-full py-2.5 rounded-xl border border-dashed border-rule text-sm font-display text-ink-2"
          @click="data.pitched_items.push({ item_code: '', item_name: '', qty: 1, uom: '', segment: '', competitor: '' })"
        >
          + Add pitched product
        </button>
      </div>
    </template>

    <!-- Current consumption - mirrors the Flutter app's per-segment
         "Monthly Consumption" entry. Also optional. -->
    <template #step-3="{ data }">
      <div class="space-y-3">
        <p v-if="!data.consumption.length" class="text-sm text-ink-3 px-1">
          No consumption entries yet. This is optional - add one below if the customer shared what they currently use monthly.
        </p>

        <div v-for="(row, i) in data.consumption" :key="i" class="bg-surface rounded-2xl border border-rule p-4 space-y-3">
          <div class="flex items-center justify-between pb-1 border-b border-rule-soft">
            <span class="inline-flex items-center gap-2 text-sm font-display font-semibold text-ink">
              <span class="w-6 h-6 rounded-full bg-accent-soft text-accent-ink text-xs font-bold flex items-center justify-center shrink-0">{{ i + 1 }}</span>
              Entry
            </span>
            <button
              type="button"
              class="w-8 h-8 rounded-full flex items-center justify-center text-ink-3 active:bg-surface-2"
              aria-label="Remove entry"
              @click="data.consumption.splice(i, 1)"
            >
              <Icon name="close" :size="14" />
            </button>
          </div>

          <div>
            <label class="block text-xs text-ink-3 mb-1">Segment</label>
            <select v-model="row.segment" class="w-full h-[42px] rounded-[10px] border border-rule bg-surface text-ink appearance-none px-3 text-sm">
              <option value="">Select segment</option>
              <option v-for="s in segments" :key="s.name" :value="s.name">{{ s.name }}</option>
            </select>
          </div>

          <div>
            <label class="block text-xs text-ink-3 mb-1">Product <span class="text-crit">*</span></label>
            <input
              v-model="row.product_name"
              class="w-full h-[42px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm"
              placeholder="e.g. Rival Improver"
            />
          </div>

          <div class="grid grid-cols-2 gap-2">
            <div>
              <label class="block text-xs text-ink-3 mb-1">Monthly qty</label>
              <input
                v-model.number="row.monthly_qty"
                type="number"
                min="0"
                step="0.01"
                class="w-full h-[42px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm"
              />
            </div>
            <div>
              <label class="block text-xs text-ink-3 mb-1">UOM</label>
              <select v-model="row.uom" class="w-full h-[42px] rounded-[10px] border border-rule bg-surface text-ink appearance-none px-3 text-sm">
                <option value="">Select…</option>
                <option v-for="u in uoms" :key="u.name" :value="u.name">{{ u.name }}</option>
              </select>
            </div>
          </div>
        </div>

        <button
          type="button"
          class="w-full py-2.5 rounded-xl border border-dashed border-rule text-sm font-display text-ink-2"
          @click="data.consumption.push({ segment: '', product_name: '', monthly_qty: 0, uom: '' })"
        >
          + Add consumption entry
        </button>
      </div>
    </template>

    <!-- Trial - mirrors mohan_impex's CustomerVisitManagement.trial_plan():
         checking this and listing items materialises a Field Trial Plan per
         item once the visit is saved, linked back to this visit. -->
    <template #step-4="{ data }">
      <div class="space-y-3">
        <label class="flex items-center gap-2 text-sm bg-surface rounded-2xl p-4">
          <input type="checkbox" v-model="data.has_trial_plan" true-value="1" false-value="0" />
          This visit included a trial
        </label>

        <template v-if="data.has_trial_plan === '1'">
          <p v-if="!data.trial_items.length" class="text-sm text-ink-3 px-1">
            Add the item(s) left with the customer to try.
          </p>

          <div v-for="(row, i) in data.trial_items" :key="i" class="bg-surface rounded-2xl border border-rule p-4 space-y-3">
            <div class="flex items-center justify-between pb-1 border-b border-rule-soft">
              <span class="inline-flex items-center gap-2 text-sm font-display font-semibold text-ink">
                <span class="w-6 h-6 rounded-full bg-accent-soft text-accent-ink text-xs font-bold flex items-center justify-center shrink-0">{{ i + 1 }}</span>
                Item
              </span>
              <button
                type="button"
                class="w-8 h-8 rounded-full flex items-center justify-center text-ink-3 active:bg-surface-2"
                aria-label="Remove item"
                @click="data.trial_items.splice(i, 1)"
              >
                <Icon name="close" :size="14" />
              </button>
            </div>

            <ItemPicker
              label="Item"
              :model-value="row.item_code"
              :display="row.item_code ? `${row.item_name || row.item_code}` : ''"
              @update:model-value="row.item_code = $event"
              @picked="onItemPicked(row, $event)"
            />

            <div class="grid grid-cols-2 gap-2">
              <div>
                <label class="block text-xs text-ink-3 mb-1">Qty</label>
                <input
                  v-model.number="row.qty"
                  type="number"
                  min="0"
                  step="0.01"
                  class="w-full h-[42px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm"
                />
              </div>
              <div>
                <label class="block text-xs text-ink-3 mb-1">UOM</label>
                <input
                  :value="row.uom"
                  readonly
                  placeholder="From item"
                  class="w-full h-[42px] rounded-[10px] border border-rule bg-ground px-3 text-sm text-ink-3"
                />
              </div>
            </div>
          </div>

          <button
            type="button"
            class="w-full py-2.5 rounded-xl border border-dashed border-rule text-sm font-display text-ink-2"
            @click="data.trial_items.push({ item_code: '', item_name: '', qty: 1, uom: '', segment: '' })"
          >
            + Add trial item
          </button>
        </template>
      </div>
    </template>

    <!-- Shop photo - optional. Uploaded ahead of the visit actually being
         created (there's no docname yet on a new-visit form), then the
         resulting file_url rides along in the create payload like any
         other field. -->
    <template #step-5="{ data }">
      <FileUpload
        v-model="data.shop_photo"
        doctype="Field Visit"
        label="Take a photo of the shop front (optional)"
        @uploading-change="photoUploading = $event"
      />
    </template>
  </FormView>

  <LocationConfirmModal :model-value="locationConfirm" @confirm="onLocationConfirm" @cancel="onLocationCancel" />
</template>

<script setup>
import { onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"
import FormView from "@/components/FormView.vue"
import FileUpload from "@/components/FileUpload.vue"
import CustomerPicker from "@/components/CustomerPicker.vue"
import ItemPicker from "@/components/ItemPicker.vue"
import NamePicker from "@/components/NamePicker.vue"
import PinDropMap from "@/components/PinDropMap.vue"
import Icon from "@/components/Icon.vue"
import LocationConfirmModal from "@/components/LocationConfirmModal.vue"
import { buildLocationConfirm } from "@/utils/locationConfirm"
import { getPosition, setAnchor } from "@/composables/geolocation"
import { queueWrite } from "@/composables/offlineQueue"

const router = useRouter()
const photoUploading = ref(false)
const pinLocation = ref(null) // { lat, lng } | null - see PinDropMap

// A rep must check in - GPS-verified, geofenced against the outlet - before
// the rest of the form unlocks. check_in (the doctype method) operates on
// an existing Field Visit by name, so the draft is created here, the first
// time the rep attempts to check in, rather than waiting for the form's own
// final save. Everything from here to the end of the wizard edits that same
// draft (update_visit), never creating a second one.
const visitName = ref("")
const checkedIn = ref(false)
const checkingIn = ref(false)
const checkInTime = ref("")
const geoError = ref("")
const locationConfirm = ref(null)
let confirmResolve = null

function askLocationConfirm(label, confirmLabel, pos) {
  locationConfirm.value = { ...buildLocationConfirm(label, pos), confirmLabel }
  return new Promise((resolve) => { confirmResolve = resolve })
}
function onLocationConfirm() {
  locationConfirm.value = null
  confirmResolve?.(true)
  confirmResolve = null
}
function onLocationCancel() {
  locationConfirm.value = null
  confirmResolve?.(false)
  confirmResolve = null
}

// The same minimum a visit needs before it can be created at all (see
// steps[0].validate below) - shown as a gate once that much is filled in,
// rather than waiting for the rep to fill in everything else first.
function canAttemptCheckIn(data) {
  if (data.party_type === "Customer") return !!data.customer
  if (data.party_type === "Prospect") {
    return !!data.prospect_name && (data.visit_type !== "Secondary" || !!data.channel_partner)
  }
  return false
}

async function onCheckIn(data) {
  geoError.value = ""
  checkingIn.value = true
  try {
    const args = buildVisitArgs(data)
    if (!visitName.value) {
      const result = await call("field_sales.api.field_visit.create_visit", args)
      visitName.value = result.name
    } else {
      // The rep went Back and changed party/location details after the
      // draft was already created on a first check-in attempt - sync those
      // before checking in against them.
      await call("field_sales.api.field_visit.update_visit", { name: visitName.value, ...args })
    }

    const pos = await getPosition()
    if (!pos) {
      geoError.value = "Location is required to check in. Enable location access and try again."
      return
    }
    const proceed = await askLocationConfirm("Check in here?", "Confirm Check-in", pos)
    if (!proceed) return

    const result = await call("field_sales.field_sales.doctype.field_visit.field_visit.check_in", {
      field_visit: visitName.value, ...pos,
    })
    setAnchor(visitName.value)
    checkedIn.value = true
    checkInTime.value = result.check_in
  } catch (e) {
    geoError.value = e?.messages?.[0] || e?.message || "Could not check in. Try again."
  } finally {
    checkingIn.value = false
  }
}

const initialData = {
  party_type: "Customer",
  visit_type: "Primary",
  customer: "",
  prospect_name: "",
  outlet_name: "",
  channel_partner: "",
  contact_number: "",
  visit_date: new Date().toISOString().slice(0, 10),
  address_line1: "",
  address_line2: "",
  district: "",
  city: "",
  state: "",
  pincode: "",
  order_status: "With Order",
  deal_confidence: "3",
  reason: "",
  remarks: "",
  demo_requested: "0",
  pitched_items: [],
  consumption: [],
  has_trial_plan: "0",
  trial_items: [],
  shop_photo: "",
}

function confidenceLabel(v) {
  return { 1: "Very low", 2: "Low", 3: "Moderate", 4: "High", 5: "Very high" }[v] || "Moderate"
}

// Field Visit's own doctype declares address_line1/2/city/state/pincode as
// fetch_from: location.* - the intent was always "pick a customer, get
// their address" - but nothing in the app ever set `location`, so a rep
// retyped it by hand every time even for a customer already on file.
const channelPartnerName = ref("")

// Which list the Customer search box looks in - a UI-only search scope,
// never sent to the server (visit_type/channel_partner always come from
// the picked customer's own record, in onCustomerPicked below).
const customerSearchScope = ref("Primary")

function onCustomerScopeChanged(data, scope) {
  customerSearchScope.value = scope
  onCustomerPicked(data, "")
}

const customerLoadError = ref("")

async function onCustomerPicked(data, customerName) {
  data.customer = customerName
  pinLocation.value = null
  data.visit_type = "Primary"
  data.channel_partner = ""
  channelPartnerName.value = ""
  customerLoadError.value = ""
  if (!customerName) return
  try {
    const detail = await call("field_sales.api.customers.customer", { name: customerName })
    // Mirrors field_visit.py's set_channel_partner - shown here so the rep
    // sees it before submitting, not decided here. The server derives its
    // own copy from the same Customer record regardless of what this sends.
    data.visit_type = detail.customer_level || "Primary"
    data.channel_partner = detail.custom_channel_partner || ""
    channelPartnerName.value = detail.cp_name || detail.custom_channel_partner || ""
    const address =
      (detail.addresses || []).find((a) => ["Shop", "Billing"].includes(a.address_type)) ||
      (detail.addresses || [])[0]
    if (address) {
      data.location = address.name
      data.address_line1 = address.address_line1 || ""
      data.address_line2 = address.address_line2 || ""
      data.pincode = address.pincode || ""
      // State/District/City are cascading <select>s - each one's own
      // <option> list only ever gets populated by onStateChange/
      // onDistrictChange, fired when a rep interactively picks a value.
      // Setting data.state/district/city directly here (as this used to)
      // left the string correct but the dropdown showing blank, since
      // there were no matching <option> elements yet to select - this
      // fetches the same lists those handlers would, so an existing
      // customer's saved address actually shows up instead of silently
      // looking empty.
      await populateAddressCascade(data, address.state, address.district, address.city)
      if (address.fs_latitude && address.fs_longitude) {
        pinLocation.value = { lat: address.fs_latitude, lng: address.fs_longitude }
      }
    }
    const contact = (detail.contacts || [])[0]
    if (contact?.mobile_no && !data.contact_number) {
      data.contact_number = contact.mobile_no
    }
    // Outlet name means "which of this customer's shops/branches" - the
    // Customer's own Shop Name (custom_shop_name) is the real answer when
    // set; falling back further is still just a starting guess the rep
    // can and should overwrite when a customer has more than one outlet.
    if (!data.outlet_name) {
      data.outlet_name = detail.custom_shop_name || address?.address_title || detail.customer_name || customerName
    }
  } catch (e) {
    // A missing address/contact never lands here - the (detail.addresses ||
    // []) fallbacks above handle that without throwing. This only fires on
    // a genuine failed request (most commonly a Customer whose own
    // territory field has drifted out of the rep's permission scope, the
    // same class of bug fixed for the order-from-visit flow) - it used to
    // fail silently here, leaving the rep looking at a blank, unexplained
    // form with no idea why nothing filled in.
    customerLoadError.value =
      e?.messages?.[0] || e?.message ||
      "Could not load this customer's saved details - fill in the fields below by hand."
  }
}

const reasons = ref([])
onMounted(async () => {
  try {
    reasons.value = (await call("field_sales.api.field_visit.reason_list")) || []
  } catch {
    reasons.value = []
  }
})

const segments = ref([])
const uoms = ref([])

function searchCompetitors(text) {
  return call("field_sales.api.field_visit.competitor_list", { search_text: text || undefined, limit: 8 })
    .then((records) => records || [])
}

onMounted(async () => {
  try {
    segments.value = (await call("field_sales.api.field_visit.segment_list")) || []
  } catch {
    segments.value = []
  }
  try {
    uoms.value = (await call("field_sales.api.field_visit.uom_list")) || []
  } catch {
    uoms.value = []
  }
})

// UOM on a pitched item always comes from the item itself (the doctype
// declares fetch_from: item_code.stock_uom) - never something a rep types.
function onItemPicked(row, item) {
  row.item_name = item?.item_name || ""
  row.uom = item?.stock_uom || ""
}

// Segment drives which items the picker even offers, so a previously-chosen
// item that belonged to the old segment can't silently stay selected once
// the segment changes underneath it.
function onSegmentChanged(row, value) {
  row.segment = value
  row.item_code = ""
  row.item_name = ""
  row.uom = ""
}

// Rendered manually in the #step-0 slot (rather than left to FormView's
// generic renderer) so the customer-type display and Prospect-only
// channel-partner picker can sit alongside the same fields.
// party_type, customer and prospect_name are rendered explicitly at the top
// of step-0 (ahead of Visit type, which depends on whichever of them is
// picked) rather than through this generic loop - see step-0's template.
// State/District/City are rendered as a cascading pick (see step-0's
// template) rather than through this generic loop, so they're split out
// into their own arrays around that block instead of listed here.
const beforeGeoFields = [
  { key: "outlet_name", label: "Outlet name", type: "text", required: true },
  { key: "contact_number", label: "Contact number", type: "text" },
  { key: "visit_date", label: "Visit date", type: "date", required: true },
  { key: "address_line1", label: "Address line 1", type: "text" },
  { key: "address_line2", label: "Address line 2", type: "text" },
]
const afterGeoFields = [
  { key: "pincode", label: "Pincode", type: "text" },
]

const states = ref([])
const districts = ref([])
const cities = ref([])

onMounted(async () => {
  try {
    states.value = (await call("field_sales.api.journey_plan.state_list")) || []
  } catch {
    states.value = []
  }
})

// Same three lookups onStateChange/onDistrictChange do interactively, run
// once for a saved address instead of a rep's own clicks - so an existing
// customer's State/District/City actually show up pre-selected rather than
// leaving data.state/district/city correct but every <option> list empty.
async function populateAddressCascade(data, state, district, city) {
  data.state = state || ""
  data.district = ""
  data.city = ""
  districts.value = []
  cities.value = []
  if (!state) return

  const stateDoc = states.value.find((s) => s.state === state)
  if (!stateDoc) return
  try {
    districts.value = (await call("field_sales.api.journey_plan.district_list", { state: stateDoc.name })) || []
  } catch {
    districts.value = []
  }
  if (!district) return

  data.district = district
  const districtDoc = districts.value.find((d) => d.district === district)
  if (!districtDoc) return
  try {
    cities.value = (await call("field_sales.api.journey_plan.city_list", { district: districtDoc.name })) || []
  } catch {
    cities.value = []
  }
  if (city) data.city = city
}

async function onStateChange(data, value) {
  data.state = value
  data.district = ""
  data.city = ""
  districts.value = []
  cities.value = []
  if (!value) return
  const stateDoc = states.value.find((s) => s.state === value)
  if (!stateDoc) return
  try {
    districts.value = (await call("field_sales.api.journey_plan.district_list", { state: stateDoc.name })) || []
  } catch {
    districts.value = []
  }
}

async function onDistrictChange(data, value) {
  data.district = value
  data.city = ""
  cities.value = []
  if (!value) return
  const districtDoc = districts.value.find((d) => d.district === value)
  if (!districtDoc) return
  try {
    cities.value = (await call("field_sales.api.journey_plan.city_list", { district: districtDoc.name })) || []
  } catch {
    cities.value = []
  }
}

const steps = [
  {
    title: "Party & location",
    fields: [
      { key: "party_type", label: "Party type", type: "select", options: ["Customer", "Prospect"], required: true },
      { key: "customer", label: "Customer (if existing)", type: "text" },
      { key: "prospect_name", label: "Prospect name (if new)", type: "text" },
      { key: "outlet_name", label: "Outlet name", type: "text", required: true },
      { key: "contact_number", label: "Contact number", type: "text" },
      { key: "visit_date", label: "Visit date", type: "date", required: true },
      { key: "address_line1", label: "Address line 1", type: "text" },
      { key: "address_line2", label: "Address line 2", type: "text" },
      { key: "city", label: "City", type: "text" },
      { key: "state", label: "State", type: "text" },
      { key: "pincode", label: "Pincode", type: "text" },
    ],
    validate: (d) => {
      if (d.party_type === "Customer" && !d.customer) return "Select or enter the customer visited."
      if (d.party_type === "Prospect" && !d.prospect_name) return "Enter a name for the prospect visited."
      if (d.visit_type === "Secondary" && !d.channel_partner) return "Select the channel partner for a Secondary visit."
      if (!checkedIn.value) return "Check in before continuing."
      return ""
    },
  },
  {
    title: "Outcome",
    fields: [],
    validate: (d) => {
      if (d.order_status === "Without Order" && !d.reason) return "Give a reason why the visit did not produce an order."
      return ""
    },
  },
  {
    title: "Products pitched",
    fields: [],
  },
  {
    title: "Consumption",
    fields: [],
  },
  {
    title: "Trial",
    fields: [],
    validate: (d) => {
      if (d.has_trial_plan === "1" && !d.trial_items.some((r) => r.item_code)) {
        return "Add at least one item, or uncheck \"This visit included a trial.\""
      }
      return ""
    },
  },
  {
    title: "Photo",
    fields: [],
    validate: () => {
      if (photoUploading.value) return "The photo is still uploading - wait a moment before creating the visit."
      return ""
    },
  },
]

function buildVisitArgs(data) {
  const args = { ...data }
  if (args.party_type === "Customer") delete args.prospect_name
  else delete args.customer
  args.pitched_items = (args.pitched_items || []).filter((r) => r.item_code)
  args.consumption = (args.consumption || []).filter((r) => r.segment || r.product_name)
  return args
}

async function createVisit(data) {
  const args = buildVisitArgs(data)

  // By the time this runs, the draft normally already exists - check-in
  // (onCheckIn above) requires it, and step-0's own validate refuses to
  // advance without a successful check-in first. Finishing the form is
  // therefore really an update, not a fresh create. queueWrite's
  // offline-first path only ever covered create_visit; check-in itself
  // needs a live connection anyway (GPS fix + server-side geofencing), so
  // once a rep has checked in this whole visit is already an online-only
  // flow, and a direct (non-queued) call here loses nothing.
  let result
  if (visitName.value) {
    result = await call("field_sales.api.field_visit.update_visit", { name: visitName.value, ...args })
  } else {
    // Shouldn't be reachable - kept as a fallback so a gap in the check-in
    // gate never turns into a hard failure of the whole form.
    result = await queueWrite({
      method: "field_sales.api.field_visit.create_visit",
      args,
      label: "New field visit",
    })
  }

  // Best-effort: a dropped pin corrects the outlet's own Address record, a
  // side effect distinct from the visit itself - it should never block or
  // fail visit creation (e.g. while offline), just silently not apply yet.
  if (pinLocation.value && data.location) {
    try {
      await call("field_sales.api.field_visit.set_outlet_location", {
        address: data.location, latitude: pinLocation.value.lat, longitude: pinLocation.value.lng,
      })
    } catch {
      // the visit itself already succeeded; the pin can be corrected later
    }
  }
  return result
}

function onSaved(result) {
  if (result?.queued) {
    router.push({ name: "VisitList" })
  } else if (result?.name) {
    router.push({ name: "VisitDetail", params: { name: result.name } })
  }
}
</script>

<template>
  <OrdersTheme>
  <div v-if="!formReady" class="p-6 text-center text-sm text-ink-3">Loading visit details…</div>
  <FormView
    v-else
    title="New order"
    fallback="/orders"
    :steps="steps"
    :initial-data="initialData"
    allow-draft
    submit-label="Submit"
    :on-submit="createOrder"
    @saved="onSaved"
  >
    <!-- Step 1: customer, warehouse, delivery -->
    <template #step-0="{ data, errors }">
      <div class="bg-surface rounded-2xl p-4 space-y-4">
        <p v-if="prefillError" class="text-xs text-warn bg-warn/10 border border-warn/30 rounded-xl p-3">{{ prefillError }}</p>
        <div>
          <CustomerPicker
            label="Customer *"
            :multiple="false"
            :extra-filters="{ customer_level: 'Primary' }"
            :model-value="data.customer"
            @update:model-value="onCustomerPicked(data, $event)"
          />
          <p v-if="errors.customer" class="text-xs text-crit mt-1">{{ errors.customer }}</p>
        </div>

        <!-- Customer type/channel partner are fixed on the customer's own
             master record (Customer.customer_level / custom_channel_partner) -
             the same real fields Field Visit and Trial Plan already derive
             from, not something a rep chooses per order. Shown here so the
             rep can see it before submitting; the server derives its own
             copy from the same Customer record regardless of what's sent. -->
        <div v-if="selectedCustomer">
          <label class="block text-sm font-display text-ink-2 mb-1">Customer type</label>
          <div class="rounded-xl border border-rule bg-surface-2 px-3 py-2 text-sm text-ink">
            {{ selectedCustomer.customer_level || "Primary" }}
            <span v-if="selectedCustomer.customer_level === 'Secondary'" class="text-ink-2">
              · via {{ selectedCustomer.cp_name || selectedCustomer.custom_channel_partner }}
            </span>
          </div>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Shop/Bakery name</label>
          <input :value="selectedCustomer?.customer_name || ''" readonly class="w-full rounded-xl border border-rule bg-surface-2 px-3 py-2 text-sm text-ink-2" placeholder="Auto-filled from customer" />
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Contact <span class="text-crit">*</span></label>
          <select v-if="customerContacts.length" v-model="data.contact_person" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm">
            <option value="">Select contact</option>
            <option v-for="contact in customerContacts" :key="contact.name" :value="contact.name">
              {{ contact.first_name }} {{ contact.last_name || "" }} · {{ contact.mobile_no || "No mobile" }}
            </option>
          </select>
          <input v-else v-model="data.contact_person" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm" placeholder="Contact record name" />
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">My warehouse <span class="text-crit">*</span></label>
          <select v-model="data.set_warehouse" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm" @change="refreshItemPrices(data)">
            <option value="">Select warehouse</option>
            <option v-for="w in warehouses" :key="w.name" :value="w.name">{{ w.warehouse_name }}</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Delivery term <span class="text-crit">*</span></label>
          <select v-model="data.custom_delivery_term" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm">
            <option value="">Select delivery term</option>
            <option v-for="term in deliveryTerms" :key="term.name" :value="term.name">{{ term.delivery_term || term.name }}</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Payment term <span class="text-crit">*</span></label>
          <select v-model="data.payment_terms_template" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm">
            <option value="">Select payment term</option>
            <option v-for="term in paymentTerms" :key="term.name" :value="term.name">{{ term.template_name || term.name }}</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Billing address <span class="text-crit">*</span></label>
          <button
            type="button"
            class="w-full text-left h-[48px] px-3 rounded-xl border border-rule bg-surface text-sm flex items-center justify-between gap-2"
            :class="errors.customer_address ? 'border-crit' : ''"
            @click="addressSheet = 'billing'"
          >
            <span class="truncate" :class="data.customer_address ? 'text-ink' : 'text-ink-3'">
              {{ addressLabelFor(billingAddresses, data.customer_address) || "Select billing address" }}
            </span>
            <span class="text-ink-3 shrink-0">›</span>
          </button>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Shipping address <span class="text-crit">*</span></label>
          <button
            type="button"
            class="w-full text-left h-[48px] px-3 rounded-xl border border-rule bg-surface text-sm flex items-center justify-between gap-2"
            :class="errors.shipping_address_name ? 'border-crit' : ''"
            @click="addressSheet = 'shipping'"
          >
            <span class="truncate" :class="data.shipping_address_name ? 'text-ink' : 'text-ink-3'">
              {{ addressLabelFor(shippingAddresses, data.shipping_address_name) || "Select shipping address" }}
            </span>
            <span class="text-ink-3 shrink-0">›</span>
          </button>
        </div>

        <AddressPickerSheet
          :open="addressSheet === 'billing'"
          title="Billing"
          :addresses="billingAddresses"
          :model-value="data.customer_address"
          @update:model-value="data.customer_address = $event"
          @close="addressSheet = null"
        />
        <AddressPickerSheet
          :open="addressSheet === 'shipping'"
          title="Shipping"
          :addresses="shippingAddresses"
          :model-value="data.shipping_address_name"
          @update:model-value="data.shipping_address_name = $event"
          @close="addressSheet = null"
        />

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Delivery date <span class="text-crit">*</span></label>
          <input
            v-model="data.delivery_date"
            type="date"
            class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
            :class="errors.delivery_date ? 'border-crit' : ''"
          />
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Tag a visit (optional)</label>
          <select v-model="data.fs_field_visit" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm">
            <option value="">Not linked to a visit</option>
            <option v-for="visit in recentVisits" :key="visit.name" :value="visit.name">
              {{ visit.customer_name || visit.prospect_name || visit.name }} · {{ visit.visit_date }}
            </option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">PO number (optional)</label>
          <input v-model="data.po_no" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm" />
        </div>
      </div>
    </template>

    <!-- Step 2: item selection - one row per line item, each with its own
         Product (template) picker and, once a template with variants is
         chosen, its own Variant picker - so several different products can
         be built up on the same page instead of one shared browse list.
         Prices come from the real, priced catalogue (field_sales.api.
         catalog.price_list / item_variants), so what's picked is what the
         order will actually be billed at. -->
    <template #step-1="{ data }">
      <div class="space-y-3">
        <p v-if="!data.items.length" class="text-sm text-ink-3 px-1">
          No items yet. Add a row below and pick a product, then a variant if it has one.
        </p>

        <div v-for="(row, i) in data.items" :key="i" class="bg-surface rounded-2xl border border-rule p-4 space-y-3">
          <div class="flex items-center justify-between pb-1 border-b border-rule-soft">
            <span class="inline-flex items-center gap-2 text-sm font-display font-semibold text-ink">
              <span class="w-6 h-6 rounded-full bg-accent-soft text-accent-ink text-xs font-bold flex items-center justify-center shrink-0">{{ i + 1 }}</span>
              Item
            </span>
            <button
              type="button"
              class="w-8 h-8 rounded-full flex items-center justify-center text-ink-3 active:bg-surface-2"
              aria-label="Remove item"
              @click="data.items.splice(i, 1)"
            >
              <Icon name="close" :size="14" />
            </button>
          </div>

          <ItemPicker
            label="Product"
            :model-value="row.template"
            :display="row.templateLabel"
            :search="(text) => searchTemplates(data, text)"
            @update:model-value="row.template = $event"
            @picked="onTemplatePicked(data, row, $event)"
          />

          <ItemPicker
            v-if="row.isTemplate"
            label="Variant"
            :model-value="row.item_code"
            :display="row.variantLabel"
            :search="(text) => searchVariants(data, row, text)"
            @update:model-value="row.item_code = $event"
            @picked="onVariantPicked(row, $event)"
          />

          <div v-if="row.item_code" class="grid grid-cols-2 gap-2">
            <div>
              <label class="block text-xs text-ink-3 mb-1">Qty</label>
              <input
                v-model.number="row.qty"
                type="number"
                min="0"
                step="1"
                class="w-full h-[42px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm"
              />
            </div>
            <div v-if="itemRate(row) != null">
              <label class="block text-xs text-ink-3 mb-1">Rate</label>
              <input
                :value="`₹${itemRate(row)} / ${row.uom}`"
                readonly
                class="w-full h-[42px] rounded-[10px] border border-rule bg-ground px-3 text-sm text-ink-3"
              />
            </div>
            <div v-else>
              <label class="block text-xs text-ink-3 mb-1">UOM</label>
              <select v-model="row.uom" class="w-full h-[42px] rounded-[10px] border border-rule bg-surface text-ink appearance-none px-3 text-sm">
                <option value="">Select…</option>
                <option v-for="u in uoms" :key="u.name" :value="u.name">{{ u.name }}</option>
              </select>
            </div>
          </div>
          <!-- No Item Price exists for this item at all - Sales Order
               Item.rate is the standard field ERPNext already ships (no
               custom field for this). It can't be used to undercut a price
               that does exist: enforce_sales_order_rates only ever reads it
               once calculate_rate has already raised PriceNotFound for this
               item - see pricing.py. -->
          <div v-if="row.item_code && itemRate(row) == null" class="rounded-xl border border-warn/30 bg-warn/10 p-3 space-y-2">
            <p class="text-xs text-warn font-display font-medium">No price on file for this item. Enter a rate manually.</p>
            <input
              v-model.number="row.manual_rate"
              type="number"
              min="0"
              step="0.01"
              placeholder="Rate per unit"
              class="w-full h-[42px] rounded-[10px] border border-rule bg-surface text-ink px-3 text-sm"
            />
            <p v-if="row.manual_rate" class="text-sm font-display font-semibold text-ink text-right">
              Amount: ₹{{ (row.manual_rate * (row.qty || 0)).toFixed(2) }}
            </p>
          </div>
          <p v-if="appliedRules(row).length" class="text-xs text-accent-ink">
            Scheme applied: {{ appliedRules(row).map((r) => r.title).join(", ") }}
          </p>
        </div>

        <button
          type="button"
          class="w-full py-2.5 rounded-xl border border-dashed border-rule text-sm font-display text-ink-2"
          @click="data.items.push(newItemRow())"
        >
          + Add item
        </button>

        <div v-if="data.items.length" class="bg-surface rounded-2xl p-4 flex justify-between items-center sticky bottom-0">
          <span class="text-sm font-display text-ink-2">{{ data.items.length }} item{{ data.items.length === 1 ? "" : "s" }} selected</span>
          <span class="font-display font-bold text-accent-ink">₹{{ total(data).toFixed(2) }}</span>
        </div>

        <div class="bg-surface rounded-2xl p-4">
          <label class="block text-sm font-display text-ink-2 mb-1">Remarks <span class="text-crit">*</span></label>
          <textarea v-model="data.remarks" rows="3" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm" placeholder="Add your remarks" />
        </div>
      </div>
    </template>

    <!-- Step 3: review - split into cards (items/total, pricing rules,
         sales terms, customer info) rather than one flat list, matching
         the reviewed design's grouping. -->
    <template #step-2="{ data }">
      <div class="space-y-3">
        <div class="bg-surface rounded-2xl p-4 space-y-2">
          <p class="font-display font-bold text-sm text-ink">Preview / Overview</p>
          <div v-for="(row, i) in data.items" :key="i" class="border-b border-rule-soft last:border-0 pb-2 last:pb-0">
            <div class="flex justify-between text-sm">
              <span class="text-ink font-medium">{{ itemLabel(row.item_code) }} × {{ row.qty || 0 }}</span>
              <span class="font-display font-semibold">₹{{ lineTotal(row).toFixed(2) }}</span>
            </div>
            <p v-if="appliedRules(row).length" class="text-xs text-accent-ink mt-0.5">
              Scheme applied: {{ appliedRules(row).map((r) => r.title).join(", ") }}
            </p>
          </div>
          <div class="border-t border-rule-soft pt-2 flex justify-between">
            <span class="font-display font-bold text-ink">Grand Total</span>
            <span class="font-display font-bold text-accent-ink">₹{{ total(data).toFixed(2) }}</span>
          </div>
          <p class="text-xs text-ink-3">
            This is an estimate for your reference. The server recalculates every
            line's rate when the order is created, so the amount actually booked
            may differ if a price or scheme changed since this preview.
          </p>
        </div>

        <div v-if="allAppliedRules(data).length" class="bg-surface rounded-2xl p-4">
          <p class="font-display font-bold text-xs text-ink mb-2">Pricing Rules</p>
          <p v-for="r in allAppliedRules(data)" :key="r.rule" class="text-xs text-ink-2 leading-relaxed">
            {{ r.title }}
          </p>
        </div>

        <div class="bg-surface rounded-2xl p-4 space-y-1.5">
          <p class="font-display font-bold text-xs text-ink mb-1">Sales Terms</p>
          <div class="flex justify-between text-xs">
            <span class="text-ink-2">My Warehouse</span>
            <span class="font-display font-medium text-ink">{{ warehouseLabel(data.set_warehouse) || "—" }}</span>
          </div>
          <div class="flex justify-between text-xs">
            <span class="text-ink-2">Delivery Term</span>
            <span class="font-display font-medium text-ink">{{ data.custom_delivery_term || "—" }}</span>
          </div>
          <div class="flex justify-between text-xs">
            <span class="text-ink-2">Payment Term</span>
            <span class="font-display font-medium text-ink">{{ data.payment_terms_template || "—" }}</span>
          </div>
          <div class="flex justify-between text-xs">
            <span class="text-ink-2">Delivery Date</span>
            <span class="font-display font-medium text-ink">{{ data.delivery_date || "—" }}</span>
          </div>
        </div>

        <div class="bg-surface rounded-2xl p-4 space-y-1">
          <p class="font-display font-bold text-xs text-ink mb-1">Customer Information</p>
          <p class="text-xs text-ink-2 leading-relaxed">
            {{ selectedCustomer?.customer_name || data.customer || "—" }}<br />
            {{ data.contact_person || "—" }}<br />
            {{ selectedCustomer?.customer_level || "Primary" }}
            <template v-if="selectedCustomer?.customer_level === 'Secondary'">
              · via {{ selectedCustomer?.cp_name || selectedCustomer?.custom_channel_partner }}
            </template>
          </p>
        </div>

        <div class="bg-surface rounded-2xl p-4">
          <p class="font-display font-bold text-xs text-ink mb-1">Remarks</p>
          <p class="text-xs text-ink-2">{{ data.remarks || "—" }}</p>
        </div>
      </div>
    </template>
  </FormView>
  </OrdersTheme>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { call } from "frappe-ui"
import FormView from "@/components/FormView.vue"
import CustomerPicker from "@/components/CustomerPicker.vue"
import ItemPicker from "@/components/ItemPicker.vue"
import AddressPickerSheet from "@/components/AddressPickerSheet.vue"
import Icon from "@/components/Icon.vue"
import OrdersTheme from "@/views/orders/OrdersTheme.vue"
import { queueWrite } from "@/composables/offlineQueue"

const router = useRouter()
const route = useRoute()

const initialData = {
  customer: "",
  set_warehouse: "",
  delivery_date: new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10),
  contact_person: "",
  customer_address: "",
  shipping_address_name: "",
  po_no: "",
  custom_delivery_term: "",
  payment_terms_template: "",
  fs_field_visit: "",
  remarks: "",
  items: [],
}

const warehouses = ref([])
const uoms = ref([])
const deliveryTerms = ref([])
const paymentTerms = ref([])
const customerContacts = ref([])
const customerAddresses = ref([])
const recentVisits = ref([])
const billingAddresses = computed(() => customerAddresses.value.filter((a) => !a.address_type || a.address_type === "Billing"))
const shippingAddresses = computed(() => customerAddresses.value.filter((a) => !a.address_type || a.address_type === "Shipping"))

// Every item/variant ever fetched (via either picker, on any row) is kept
// here so the running total and review step can find a row's name/rate
// without needing to know which row or search first surfaced it.
const itemCache = ref({})

function cacheItems(records) {
  for (const r of records) itemCache.value[r.item_code] = r
}

function newItemRow() {
  return {
    template: "", templateLabel: "", isTemplate: false,
    item_code: "", item_name: "", variantLabel: "",
    qty: 1, uom: "", manual_rate: null,
  }
}

// The one rate-shaped value a row itself owns (no custom field - this maps
// straight onto Sales Order Item.rate, the standard field, on submit). Only
// meaningful once itemRate(row) is null - see the "No price on file" card
// in the template - since enforce_sales_order_rates overwrites whatever a
// client sends the moment a real price is found.
function manualRate(row) {
  return row.manual_rate || null
}

// Product search for a row's first picker - the same priced list as the
// Price List screen, which already excludes variants server-side (see
// field_sales.api.catalog.ITEM_CONFIG.base_filters), so only templates and
// standalone items are offered here.
function searchTemplates(data, text) {
  return call("field_sales.api.catalog.item_templates", {
    customer: data.customer || undefined,
    warehouse: data.set_warehouse || undefined,
    search_text: text,
    limit: 15,
  }).then((records) => {
    cacheItems(records || [])
    return records || []
  })
}

// Variant search for a row's second picker, once its template is chosen.
function searchVariants(data, row, text) {
  return call("field_sales.api.catalog.item_variants", {
    template: row.template,
    customer: data.customer || undefined,
    warehouse: data.set_warehouse || undefined,
    search_text: text,
  }).then((result) => {
    cacheItems(result?.records || [])
    return result?.records || []
  })
}

// A template row (has_variants) is never itself sellable - only its
// variants are priced and stocked - so picking one clears any previously
// chosen variant rather than treating the template as the line item.
function onTemplatePicked(data, row, item) {
  row.template = item?.item_code || ""
  row.templateLabel = item?.item_name || item?.item_code || ""
  row.isTemplate = !!item?.has_variants
  row.item_code = ""
  row.item_name = ""
  row.variantLabel = ""
  row.uom = ""
  if (!item) return
  if (row.isTemplate) return
  row.item_code = item.item_code
  row.item_name = item.item_name
  row.uom = item.stock_uom
}

function onVariantPicked(row, item) {
  row.item_code = item?.item_code || ""
  row.variantLabel = item?.item_name || item?.item_code || ""
  row.item_name = item?.item_name || ""
  row.uom = item?.stock_uom || ""
}

function itemRate(row) {
  return catalogItemFor(row.item_code)?.rate ?? null
}

// Pricing Rules already run server-side on every rate (calculate_rate,
// enforced again on save by enforce_sales_order_rates) - this just surfaces
// which ones fired, so a rep can see *why* a rate looks the way it does
// instead of a bare number with no explanation.
function appliedRules(row) {
  return catalogItemFor(row.item_code)?.pricing_rules_applied || []
}

// De-duplicated across every line, for the Review step's single "Pricing
// Rules" summary card - the same rule commonly applies to more than one
// item and shouldn't be listed once per line there.
function allAppliedRules(data) {
  const byRule = new Map()
  for (const row of data.items || []) {
    for (const r of appliedRules(row)) {
      if (!byRule.has(r.rule)) byRule.set(r.rule, r)
    }
  }
  return [...byRule.values()]
}

function warehouseLabel(code) {
  return warehouses.value.find((w) => w.name === code)?.warehouse_name || code
}

// The customer/warehouse chosen on step 1 decide the price list a row's
// rate came from - if either changes after rows already have items picked,
// re-price those rows rather than leaving a stale rate in itemCache.
async function refreshItemPrices(data) {
  const codes = [...new Set((data.items || []).map((r) => r.item_code).filter(Boolean))]
  await Promise.all(codes.map(async (code) => {
    try {
      const result = await call("field_sales.api.catalog.item_price", {
        item_code: code,
        customer: data.customer || undefined,
        warehouse: data.set_warehouse || undefined,
      })
      if (itemCache.value[code]) itemCache.value[code].rate = result.final_rate
    } catch {
      // leave the last known rate rather than blanking it on a transient error
    }
  }))
}

// FormView copies initial-data into its own reactive state once, at setup
// (see its own source - a shallow spread, not a live binding) - so a visit
// prefill fetched asynchronously has to land on initialData BEFORE
// <FormView> ever mounts, or it's silently ignored. Gated behind this
// instead of just always awaiting the prefill first, since the ordinary
// "start a blank order" path has never needed to wait on anything before
// rendering and shouldn't start now.
const formReady = ref(!route.query.from_visit)
const prefillError = ref("")

async function loadVisitPrefill(visitName) {
  try {
    const result = await call("field_sales.api.catalog.visit_order_prefill", { visit_name: visitName })
    cacheItems((result.items || []).map((i) => ({ item_code: i.item_code, item_name: i.item_name, rate: i.rate })))
    initialData.items = (result.items || []).map((i) => ({
      ...newItemRow(),
      // A pitched item is never itself a variant-bearing template (the
      // visit form's own picker only offers real sellable items) - so the
      // Product picker's own "template" field is just this item, matching
      // what onTemplatePicked already does for any other non-template pick.
      template: i.item_code, templateLabel: i.item_name,
      item_code: i.item_code, item_name: i.item_name, qty: i.qty, uom: i.uom || "",
    }))
    initialData.fs_field_visit = result.fs_field_visit || ""
    initialData.remarks = result.remarks || ""
    if (result.delivery_date) initialData.delivery_date = result.delivery_date
    initialData.customer = result.customer
    await loadCustomerContext(initialData, result.fs_field_visit)
    // The visit's own recorded contact (who the rep actually met) beats
    // loadCustomerContext's generic "customer's primary contact" default,
    // but only if it's a real contact on this customer's own list.
    if (result.contact_person && customerContacts.value.some((c) => c.name === result.contact_person)) {
      initialData.contact_person = result.contact_person
    }
  } catch (e) {
    prefillError.value = e?.messages?.[0] || e?.message || "Could not load this visit's details."
  } finally {
    formReady.value = true
  }
}

onMounted(async () => {
  try {
    const [options, visitPage] = await Promise.all([
      call("field_sales.api.catalog.order_options"),
      call("field_sales.api.field_visit.visit_list", { is_self: 1, limit: 20 }),
    ])
    warehouses.value = options?.warehouses || []
    deliveryTerms.value = options?.delivery_terms || []
    paymentTerms.value = options?.payment_terms || []
    recentVisits.value = visitPage?.records || []
  } catch {
    warehouses.value = []
  }
  try {
    uoms.value = (await call("field_sales.api.field_visit.uom_list")) || []
  } catch {
    uoms.value = []
  }
  if (route.query.from_visit) {
    await loadVisitPrefill(route.query.from_visit)
  }
})

// "Shop/Bakery name" mirrors the Flutter app: shown read-only, auto-filled
// once a customer is picked - never a separate input, since it's the same
// customer record's own name, not distinct data to collect. Set inside
// loadCustomerContext (which already fires on customer change) rather than
// a computed, since the step-0 slot's `data` isn't in this script's scope.
const selectedCustomer = ref(null)
const addressSheet = ref(null) // "billing" | "shipping" | null

function onCustomerPicked(data, customerName) {
  data.customer = customerName
  loadCustomerContext(data)
}

async function loadCustomerContext(data, viaVisit) {
  data.contact_person = ""
  data.customer_address = ""
  data.shipping_address_name = ""
  customerContacts.value = []
  customerAddresses.value = []
  selectedCustomer.value = null
  if (!data.customer) return
  // A visit-prefilled customer is authorized through the visit itself, not
  // a plain Customer permission check - see visit_customer_context's own
  // docstring for why those can disagree (the Customer's own territory
  // field can lag behind which rep's territory actually covers them today).
  const customer = viaVisit
    ? await call("field_sales.api.catalog.visit_customer_context", { visit_name: viaVisit })
    : await call("field_sales.api.customers.customer", { name: data.customer })
  customerContacts.value = customer?.contacts || []
  customerAddresses.value = customer?.addresses || []
  selectedCustomer.value = customer

  // Auto-fill the customer's own defaults rather than leaving the rep to
  // re-pick the same contact/address on every order for a customer already
  // on file - customer_primary_contact/customer_primary_address are the
  // real ERPNext fields for exactly this. Falling back to "first on record"
  // still beats a blank field when no primary is set; the rep can always
  // change any of these afterward.
  data.contact_person =
    customerContacts.value.find((c) => c.name === customer?.customer_primary_contact)?.name
    || customerContacts.value[0]?.name
    || ""

  const defaultBilling =
    billingAddresses.value.find((a) => a.name === customer?.customer_primary_address)
    || billingAddresses.value[0]
  data.customer_address = defaultBilling?.name || ""

  const defaultShipping =
    shippingAddresses.value.find((a) => a.name === customer?.customer_primary_address)
    || shippingAddresses.value[0]
    || defaultBilling
  data.shipping_address_name = defaultShipping?.name || ""

  refreshItemPrices(data)
}

function addressLabel(address) {
  return [address.address_title, address.address_line1, address.city, address.state, address.pincode].filter(Boolean).join(", ")
}

function addressLabelFor(list, name) {
  const a = list.find((x) => x.name === name)
  return a ? a.address_title || addressLabel(a) : ""
}

function catalogItemFor(item_code) {
  return itemCache.value[item_code]
}

function itemLabel(item_code) {
  return catalogItemFor(item_code)?.item_name || item_code || "—"
}

function lineTotal(row) {
  const rate = catalogItemFor(row.item_code)?.rate ?? manualRate(row)
  return rate != null ? rate * (row.qty || 0) : 0
}

function total(data) {
  return (data.items || []).reduce((sum, row) => sum + lineTotal(row), 0)
}

const steps = [
  {
    title: "Customer & delivery",
    fields: [],
    validate: (d) => {
      if (!d.customer) return "Select the customer this order is for."
      if (!d.set_warehouse) return "Select your warehouse."
      if (!d.delivery_date) return "Give a delivery date."
      if (!d.contact_person) return "Select a contact."
      if (!d.customer_address) return "Select a billing address."
      if (!d.shipping_address_name) return "Select a shipping address."
      if (!d.custom_delivery_term) return "Select a delivery term."
      if (!d.payment_terms_template) return "Select a payment term."
      return ""
    },
  },
  {
    title: "Items",
    fields: [],
    validate: (d) => {
      const rows = (d.items || []).filter((r) => r.item_code && r.qty)
      if (!rows.length) return "Add at least one item with a quantity."
      if (!String(d.remarks || "").trim()) return "Please add your remarks."
      const unpriced = rows.find((r) => itemRate(r) == null && !r.manual_rate)
      if (unpriced) return `${itemLabel(unpriced.item_code)} has no price - enter a rate manually, or remove it.`
      return ""
    },
  },
  {
    title: "Review",
    fields: [],
  },
]

async function createOrder(data, mode) {
  const items = data.items
    .filter((r) => r.item_code && r.qty)
    .map((r) => ({
      item_code: r.item_code,
      qty: r.qty,
      uom: r.uom || undefined,
      // Only meaningful when this item has no price on file at all - see
      // manualRate()'s own comment. Sent as the standard `rate` field,
      // nothing custom; enforce_sales_order_rates ignores it outright for
      // any item it can actually price.
      rate: manualRate(r) || undefined,
    }))

  const args = {
    customer: data.customer,
    delivery_date: data.delivery_date,
    set_warehouse: data.set_warehouse || undefined,
    contact_person: data.contact_person || undefined,
    customer_address: data.customer_address || undefined,
    shipping_address_name: data.shipping_address_name || undefined,
    po_no: data.po_no || undefined,
    custom_delivery_term: data.custom_delivery_term || undefined,
    payment_terms_template: data.payment_terms_template || undefined,
    fs_field_visit: data.fs_field_visit || undefined,
    remarks: data.remarks.trim(),
    items,
  }

  const created = await queueWrite({
    method: "field_sales.api.catalog.create_order",
    args,
    label: "New sales order",
  })

  if (mode === "submit" && !created.queued && created?.name) {
    await call("field_sales.api.catalog.submit_order", { name: created.name })
  }
  return created
}

function onSaved(result) {
  if (result?.queued) {
    router.push({ name: "OrderList" })
  } else if (result?.name) {
    router.push({ name: "OrderDetail", params: { name: result.name } })
  }
}
</script>

<template>
  <OrdersTheme>
  <FormView
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
        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Customer <span class="text-crit">*</span></label>
          <select
            v-model="data.customer"
            class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
            :class="errors.customer ? 'border-crit' : ''"
            @change="loadCustomerContext(data)"
          >
            <option value="">Select customer</option>
            <option v-for="customer in customers" :key="customer.name" :value="customer.name">
              {{ customer.customer_name || customer.name }}
            </option>
          </select>
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
          <select v-model="data.set_warehouse" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm" @change="loadCatalog(data)">
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
          <select v-model="data.customer_address" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm">
            <option value="">Select billing address</option>
            <option v-for="address in billingAddresses" :key="address.name" :value="address.name">{{ addressLabel(address) }}</option>
          </select>
        </div>

        <div>
          <label class="block text-sm font-display text-ink-2 mb-1">Shipping address <span class="text-crit">*</span></label>
          <select v-model="data.shipping_address_name" class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm">
            <option value="">Select shipping address</option>
            <option v-for="address in shippingAddresses" :key="address.name" :value="address.name">{{ addressLabel(address) }}</option>
          </select>
        </div>

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

    <!-- Step 2: item selection - pick from the real, priced catalogue (the
         same field_sales.api.catalog.price_list a rep sees on the Price
         List screen) rather than typing an item code from memory. Matches
         the Flutter app's item-selection screen: name, rate/unit and a qty
         stepper per row, a running total, no manual code entry. -->
    <template #step-1="{ data }">
      <div class="space-y-3">
        <input
          v-model="catalogSearch"
          class="w-full rounded-xl border border-rule bg-surface px-3 py-2 text-sm"
          placeholder="Search items"
          @input="debouncedLoadCatalog(data)"
        />

        <p v-if="catalogLoading" class="text-xs text-ink-3 text-center py-4">Loading catalogue…</p>
        <p v-else-if="!catalogItems.length" class="text-xs text-ink-3 text-center py-4">No items found.</p>

        <div v-else class="space-y-2">
          <div
            v-for="item in catalogItems"
            :key="item.item_code"
            class="bg-surface rounded-2xl p-3 flex items-center justify-between gap-3"
          >
            <div class="min-w-0">
              <p class="text-sm font-display font-medium text-ink truncate">{{ item.item_name || item.item_code }}</p>
              <p class="text-xs text-ink-3">
                <template v-if="item.rate != null">₹{{ item.rate }} / {{ item.stock_uom }}</template>
                <template v-else>No price available</template>
              </p>
            </div>
            <div v-if="item.rate != null" class="flex items-center gap-2 shrink-0">
              <button
                type="button"
                class="w-8 h-8 rounded-full border border-rule text-ink font-display font-medium flex items-center justify-center disabled:opacity-40"
                :disabled="itemQty(data, item.item_code) <= 0"
                @click="setItemQty(data, item, itemQty(data, item.item_code) - 1)"
              >−</button>
              <span class="w-6 text-center text-sm font-display font-semibold">{{ itemQty(data, item.item_code) }}</span>
              <button
                type="button"
                class="w-8 h-8 rounded-full border border-rule text-ink font-display font-medium flex items-center justify-center"
                @click="setItemQty(data, item, itemQty(data, item.item_code) + 1)"
              >+</button>
            </div>
          </div>
        </div>

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

    <!-- Step 3: review -->
    <template #step-2="{ data }">
      <div class="bg-surface rounded-2xl p-4 space-y-3">
        <div class="flex justify-between text-sm">
          <span class="text-ink-2">Customer</span>
          <span class="font-display font-medium">{{ data.customer || "—" }}</span>
        </div>
        <div class="flex justify-between text-sm">
          <span class="text-ink-2">Delivery date</span>
          <span class="font-display font-medium">{{ data.delivery_date || "—" }}</span>
        </div>
        <div v-if="data.contact_person" class="flex justify-between text-sm">
          <span class="text-ink-2">Contact</span>
          <span class="font-display font-medium">{{ data.contact_person }}</span>
        </div>
        <div v-if="data.custom_delivery_term" class="flex justify-between text-sm">
          <span class="text-ink-2">Delivery term</span>
          <span class="font-display font-medium">{{ data.custom_delivery_term }}</span>
        </div>
        <div v-if="data.payment_terms_template" class="flex justify-between text-sm">
          <span class="text-ink-2">Payment term</span>
          <span class="font-display font-medium">{{ data.payment_terms_template }}</span>
        </div>
        <div class="flex justify-between gap-4 text-sm">
          <span class="text-ink-2">Remarks</span>
          <span class="font-display font-medium text-right">{{ data.remarks || "—" }}</span>
        </div>

        <div class="border-t border-rule-soft pt-2 space-y-2">
          <div v-for="(row, i) in data.items" :key="i" class="flex justify-between text-sm">
            <span class="text-ink-2">{{ itemLabel(row.item_code) }} × {{ row.qty || 0 }}</span>
            <span class="font-display">₹{{ lineTotal(row).toFixed(2) }}</span>
          </div>
        </div>

        <div class="border-t border-rule-soft pt-2 flex justify-between">
          <span class="font-display font-semibold">Estimated total</span>
          <span class="font-display font-bold text-accent-ink">₹{{ total(data).toFixed(2) }}</span>
        </div>

        <p class="text-xs text-ink-3">
          This is an estimate for your reference. The server recalculates every
          line's rate when the order is created, so the amount actually booked
          may differ if a price or scheme changed since this preview.
        </p>
      </div>
    </template>
  </FormView>
  </OrdersTheme>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import { call } from "frappe-ui"
import FormView from "@/components/FormView.vue"
import OrdersTheme from "@/views/orders/OrdersTheme.vue"
import { queueWrite } from "@/composables/offlineQueue"

const router = useRouter()

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
const customers = ref([])
const deliveryTerms = ref([])
const paymentTerms = ref([])
const customerContacts = ref([])
const customerAddresses = ref([])
const recentVisits = ref([])
const billingAddresses = computed(() => customerAddresses.value.filter((a) => !a.address_type || a.address_type === "Billing"))
const shippingAddresses = computed(() => customerAddresses.value.filter((a) => !a.address_type || a.address_type === "Shipping"))

// Catalogue for step 2 - the same priced list a rep sees on the Price List
// screen (field_sales.api.catalog.price_list), so what's picked here is what
// the order will actually be billed at, not a guess from a typed code.
const catalogItems = ref([])
const catalogLoading = ref(false)
const catalogSearch = ref("")
let catalogDebounce = null

onMounted(async () => {
  try {
    const [options, customerPage, visitPage] = await Promise.all([
      call("field_sales.api.catalog.order_options"),
      call("field_sales.api.customers.customer_list", { limit: 500, current_page: 1, disabled: 0 }),
      call("field_sales.api.field_visit.visit_list", { is_self: 1, limit: 20 }),
    ])
    warehouses.value = options?.warehouses || []
    deliveryTerms.value = options?.delivery_terms || []
    paymentTerms.value = options?.payment_terms || []
    customers.value = customerPage?.records || []
    recentVisits.value = visitPage?.records || []
  } catch {
    warehouses.value = []
  }
  // seed the catalogue before a customer is even picked, so step 2 isn't
  // empty on first render - resolve_price_list falls back to the default
  // Standard Selling list when no customer is given.
  loadCatalog({ customer: "", set_warehouse: "" })
})

// "Shop/Bakery name" mirrors the Flutter app: shown read-only, auto-filled
// once a customer is picked - never a separate input, since it's the same
// customer record's own name, not distinct data to collect. Set inside
// loadCustomerContext (which already fires on customer change) rather than
// a computed, since the step-0 slot's `data` isn't in this script's scope.
const selectedCustomer = ref(null)

async function loadCustomerContext(data) {
  data.contact_person = ""
  data.customer_address = ""
  data.shipping_address_name = ""
  customerContacts.value = []
  customerAddresses.value = []
  selectedCustomer.value = null
  if (!data.customer) return
  const customer = await call("field_sales.api.customers.customer", { name: data.customer })
  customerContacts.value = customer?.contacts || []
  customerAddresses.value = customer?.addresses || []
  selectedCustomer.value = customer
  loadCatalog(data)
}

function addressLabel(address) {
  return [address.address_title, address.address_line1, address.city, address.state, address.pincode].filter(Boolean).join(", ")
}

async function loadCatalog(data) {
  catalogLoading.value = true
  try {
    const page = await call("field_sales.api.catalog.price_list", {
      customer: data.customer || undefined,
      warehouse: data.set_warehouse || undefined,
      search_text: catalogSearch.value || undefined,
      limit: 50,
    })
    catalogItems.value = page?.records || []
  } catch {
    catalogItems.value = []
  } finally {
    catalogLoading.value = false
  }
}

function debouncedLoadCatalog(data) {
  clearTimeout(catalogDebounce)
  catalogDebounce = setTimeout(() => loadCatalog(data), 300)
}

function itemQty(data, item_code) {
  return data.items.find((r) => r.item_code === item_code)?.qty || 0
}

function setItemQty(data, item, qty) {
  const existing = data.items.find((r) => r.item_code === item.item_code)
  if (qty <= 0) {
    if (existing) data.items.splice(data.items.indexOf(existing), 1)
    return
  }
  if (existing) {
    existing.qty = qty
  } else {
    data.items.push({ item_code: item.item_code, qty, uom: item.stock_uom })
  }
}

function catalogItemFor(item_code) {
  return catalogItems.value.find((c) => c.item_code === item_code)
}

function itemLabel(item_code) {
  return catalogItemFor(item_code)?.item_name || item_code || "—"
}

function lineTotal(row) {
  const rate = catalogItemFor(row.item_code)?.rate
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
    .map((r) => ({ item_code: r.item_code, qty: r.qty, uom: r.uom || undefined }))

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

// Icon lookup for the server-driven module grid (field_sales.api.home.module_grid).
// The grid itself is entirely server-driven - this maps the icon name the
// server sends to a canonical name understood by <Icon> (src/components/Icon.vue),
// with a safe fallback for anything we don't recognise yet. This is the one
// place the mapping lives - views ask for `iconFor(tile.icon)` and pass the
// result straight to <Icon :name="..."/>, never inlining SVG themselves.
export const ICONS = {
  visit: "visit",
  order: "order",
  customer: "customer",
  kyc: "kyc",
  price: "price",
  requisitions: "requisitions",
  sample: "sample",
  collateral: "collateral",
  demo: "demo",
  scheme: "scheme",
  complaint: "complaint",
  digital: "digital",
  report: "report",
}

export function iconFor(name) {
  return ICONS[name] || "square"
}

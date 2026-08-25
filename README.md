## Field Sales

A field-sales, beat-planning and customer-visit module for Frappe/ERPNext v15
— visits, sample and collateral requests, product demos with a typed scorecard,
onboarding of new outlets, and server-enforced pricing for a mobile sales
team.

Built as the productized replacement for a bespoke client app. Every write
path is server-authoritative: a client can request a rate, a check-in, a
territory or an approval, but the server always recomputes and enforces the
number that actually gets stored.

### Requires

- Frappe v15 (`version-15` branch)
- ERPNext v15 (`version-15` branch) — Customer, Item, Territory, Sales Order,
  Pricing Rule
- Frappe HR (`version-15` branch — **not** `develop`, which is v16 and will
  not install against ERPNext v15)

### Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app --branch version-15 hrms
bench get-app https://github.com/edubild/field_sales --branch version-15
bench --site your-site install-app field_sales
```

`required_apps` in `hooks.py` declares `erpnext` and `hrms`, so `bench
install-app` pulls them in if they are not already on the site.

After install, the site needs:

- A **Field Sales Settings** single configured — at minimum
  `geofence_radius` and `geofence_behaviour` (Warn is the safer default; GPS
  drifts and indoor stock rooms have no signal, so Block generates support
  calls).
- At least one **Field Sales Module** record per home-screen tile you want
  visible — the grid is data-driven, not hardcoded, so a fresh install starts
  with an empty home screen until these are seeded. See
  `field_sales/api/home.py` for the shape.
- Reps need the **Sales Executive App** role (and a linked, active
  **Employee** record with `user_id` set) before any write endpoint will
  accept a request from them.
- Approvers (Customer Onboarding, complaints) need **Sales Manager** or
  **System Manager** — the doctype's own `submit` permission is not enough,
  since the rep who files a request already holds that.

### What's here

| Module | Doctypes | Notes |
|---|---|---|
| Field Visit | Field Visit (+ Item, Consumption) | Geofenced check-in/out; duration is always server-derived |
| Requisitions | Sample Request, Collateral Request, Sales Collateral | |
| Product Demo | Product Demo, Demo Evaluation (+ lines), Demo Parameter | Typed scorecard — a parameter is either rated or measured, never both |
| Onboarding | Customer Onboarding, Onboarding Document | Approval creates the real `Customer`; the rep never can |
| Pricing | `field_sales/pricing.py` | Replaces ad-hoc client-side pricing; enforced server-side on Sales Order `before_validate` |
| Home | Field Sales Module, `field_sales/api/home.py` | Data-driven module grid, scoreboard, attendance, notifications |
| Everything else | Customers, Complaints, Catalogue, Orders, Schemes | Thin wrappers over native ERPNext doctypes — no new schema |

Not included: beat/journey planning. It ships separately once a name
collision with an unrelated app on the reference deployment is resolved by a
clean install.

### Testing

```bash
bench --site your-site run-tests --skip-before-tests --app field_sales
```

`--skip-before-tests` matters here: the default `before_tests` hook (from
ERPNext/india_compliance, if installed) wipes seeded Item Price and Company
data that several tests depend on.

### License

MIT

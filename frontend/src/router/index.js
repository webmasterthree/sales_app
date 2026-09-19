import { createRouter, createWebHistory } from "vue-router"
import { session } from "@/data/session"

const routes = [
  { path: "/login", name: "Login", component: () => import("@/views/Login.vue"), meta: { guest: true } },

  { path: "/", name: "Home", component: () => import("@/views/Home.vue") },
  { path: "/performance", name: "Performance", component: () => import("@/views/Performance.vue") },
  { path: "/notifications", name: "Notifications", component: () => import("@/views/Notifications.vue") },
  { path: "/profile", name: "Profile", component: () => import("@/views/Profile.vue") },
  { path: "/settings", name: "Settings", component: () => import("@/views/Settings.vue") },

  // Field Visit
  { path: "/visits", name: "VisitList", component: () => import("@/views/field_visit/List.vue") },
  { path: "/visits/new", name: "VisitNew", component: () => import("@/views/field_visit/Form.vue") },
  { path: "/visits/:name", name: "VisitDetail", component: () => import("@/views/field_visit/Detail.vue"), props: true },
  { path: "/visits/:name/edit", name: "VisitEdit", component: () => import("@/views/field_visit/Form.vue"), props: true },

  // Journey Plan - a hub bundling Trip Plan alongside the other travel-
  // adjacent requests (Sample Requisition, Visit Plan, Marketing Collaterals),
  // matching the Requisitions hub pattern below.
  { path: "/journey-plan", name: "JourneyPlanHub", component: () => import("@/views/journey_plan/Hub.vue") },
  { path: "/journey-plan/trips", name: "JourneyPlanList", component: () => import("@/views/journey_plan/List.vue") },
  { path: "/journey-plan/new", name: "JourneyPlanNew", component: () => import("@/views/journey_plan/Form.vue") },
  { path: "/journey-plan/expense-claim/new", name: "ExpenseClaimNew", component: () => import("@/views/expense_claim/Form.vue") },
  { path: "/journey-plan/report", name: "JourneyPlanVisitReport", component: () => import("@/views/journey_plan/Report.vue") },
  { path: "/journey-plan/:name", name: "JourneyPlanDetail", component: () => import("@/views/journey_plan/Detail.vue"), props: true },

  // Trial Plan
  { path: "/trial-plan", name: "TrialPlanList", component: () => import("@/views/trial_plan/List.vue") },
  { path: "/trial-plan/new", name: "TrialPlanNew", component: () => import("@/views/trial_plan/Form.vue") },
  { path: "/trial-plan/:name", name: "TrialPlanDetail", component: () => import("@/views/trial_plan/Detail.vue"), props: true },

  // Complaints
  { path: "/complaints", name: "ComplaintList", component: () => import("@/views/complaints/List.vue") },
  { path: "/complaints/new", name: "ComplaintNew", component: () => import("@/views/complaints/Form.vue") },
  { path: "/complaints/:name", name: "ComplaintDetail", component: () => import("@/views/complaints/Detail.vue"), props: true },

  // Requisitions hub (Sample Request, Collateral Request, Product Demo)
  { path: "/requisitions", name: "RequisitionsHub", component: () => import("@/views/requests/Hub.vue") },
  { path: "/requisitions/samples", name: "SampleRequestList", component: () => import("@/views/requests/SampleList.vue") },
  { path: "/requisitions/samples/new", name: "SampleRequestNew", component: () => import("@/views/requests/SampleForm.vue") },
  { path: "/requisitions/samples/:name", name: "SampleRequestDetail", component: () => import("@/views/requests/SampleDetail.vue"), props: true },
  { path: "/requisitions/collateral", name: "CollateralRequestList", component: () => import("@/views/requests/CollateralList.vue") },
  { path: "/requisitions/collateral/new", name: "CollateralRequestNew", component: () => import("@/views/requests/CollateralForm.vue") },
  { path: "/requisitions/collateral/:name", name: "CollateralRequestDetail", component: () => import("@/views/requests/CollateralDetail.vue"), props: true },
  { path: "/requisitions/demos", name: "DemoList", component: () => import("@/views/demo/List.vue") },
  { path: "/requisitions/demos/new", name: "DemoNew", component: () => import("@/views/demo/Form.vue") },
  { path: "/requisitions/demos/:name", name: "DemoDetail", component: () => import("@/views/demo/Detail.vue"), props: true },
  { path: "/requisitions/demos/:name/evaluate/:item_code", name: "DemoEvaluate", component: () => import("@/views/demo/Evaluation.vue"), props: true },
  { path: "/collateral", name: "CollateralLibrary", component: () => import("@/views/requests/Library.vue") },

  // Customers
  { path: "/customers", name: "CustomerList", component: () => import("@/views/customers/List.vue") },
  { path: "/customers/:name", name: "CustomerDetail", component: () => import("@/views/customers/Detail.vue"), props: true },
  { path: "/customers/:name/ledger", name: "CustomerLedger", component: () => import("@/views/customers/Ledger.vue"), props: true },

  // Onboarding / KYC
  { path: "/onboarding", name: "OnboardingList", component: () => import("@/views/onboarding/List.vue") },
  { path: "/onboarding/new", name: "OnboardingNew", component: () => import("@/views/onboarding/Form.vue") },
  { path: "/onboarding/:name", name: "OnboardingDetail", component: () => import("@/views/onboarding/Detail.vue"), props: true },

  // Price list / catalogue
  { path: "/prices", name: "Catalogue", component: () => import("@/views/catalog/List.vue") },

  // Orders - one entry point ("New order") with a Direct Customer / Channel
  // Partner chooser, matching Flutter's single "New Sales Order" screen with
  // its Primary/Secondary toggle. The two flows book genuinely different
  // doctypes (native Sales Order vs fmcg's Channel Partner Sales Order), so
  // beyond that shared entry point they're separate wizards/details/routes.
  { path: "/orders", name: "OrderList", component: () => import("@/views/orders/List.vue") },
  { path: "/orders/new", name: "OrderNew", component: () => import("@/views/orders/New.vue") },
  { path: "/orders/new/direct", name: "OrderNewDirect", component: () => import("@/views/orders/Form.vue") },
  { path: "/orders/new/channel-partner", name: "OrderNewChannelPartner", component: () => import("@/views/orders/ChannelPartnerForm.vue") },
  { path: "/orders/channel-partner/:name", name: "ChannelPartnerOrderDetail", component: () => import("@/views/orders/ChannelPartnerDetail.vue"), props: true },
  { path: "/orders/:name", name: "OrderDetail", component: () => import("@/views/orders/Detail.vue"), props: true },

  // Schemes (read-only - native Pricing Rules)
  { path: "/schemes", name: "SchemeList", component: () => import("@/views/schemes/List.vue") },
  { path: "/schemes/:name", name: "SchemeDetail", component: () => import("@/views/schemes/Detail.vue"), props: true },

  // Reports
  { path: "/reports", name: "Reports", component: () => import("@/views/Reports.vue") },
  { path: "/reports/sales-target", name: "SalesTargetReport", component: () => import("@/views/reports/SalesTargetReport.vue") },
  { path: "/reports/coverage", name: "CustomerCoverageReport", component: () => import("@/views/reports/CustomerCoverageReport.vue") },
  { path: "/reports/collections", name: "CollectionsReport", component: () => import("@/views/reports/CollectionsReport.vue") },
  { path: "/reports/collections/:customer/collect", name: "CollectPayment", component: () => import("@/views/reports/CollectPayment.vue"), props: true },
  { path: "/reports/onboarding-funnel", name: "OnboardingFunnelReport", component: () => import("@/views/reports/OnboardingFunnelReport.vue") },

  // Approval queue (for managers)
  { path: "/approvals", name: "ApprovalQueue", component: () => import("@/views/approvals/Queue.vue") },

  { path: "/:pathMatch(.*)*", name: "NotFound", component: () => import("@/views/NotFound.vue") },
]

const router = createRouter({
  history: createWebHistory("/field_sales_app"),
  routes,
})

router.beforeEach((to) => {
  if (!to.meta.guest && !session.isLoggedIn) {
    return { name: "Login", query: { redirect: to.fullPath } }
  }
  if (to.name === "Login" && session.isLoggedIn) {
    return { path: "/" }
  }
  return true
})

export default router

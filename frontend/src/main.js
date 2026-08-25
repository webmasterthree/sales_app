import { createApp } from "vue"
import App from "./App.vue"
import router from "./router"
import { setConfig, frappeRequest, resourcesPlugin } from "frappe-ui"

import "./theme/tokens.css"
import "./main.css"

import { initTheme } from "@/composables/theme"
import { replayQueue } from "@/composables/offlineQueue"

setConfig("resourceFetcher", frappeRequest)

initTheme()

const app = createApp(App)
app.use(resourcesPlugin)
app.use(router)

router.isReady().then(async () => {
  if (import.meta.env.DEV) {
    await frappeRequest({
      url: "/api/method/field_sales.www.field_sales_app.get_context_for_dev",
    })
      .then((values) => {
        if (!window.frappe) window.frappe = {}
        window.frappe.boot = values
      })
      .catch(() => {
        // Not developer_mode, or not logged in yet - fall back to whatever
        // the server-rendered index.html already set on window.frappe.boot.
      })
  }

  app.mount("#app")
  if (navigator.onLine) replayQueue()

  if ("serviceWorker" in navigator && import.meta.env.PROD) {
    navigator.serviceWorker.register("/assets/field_sales/frontend/sw.js").catch(() => {
      // PWA install still works without the service worker; just no offline shell caching
    })
  }
})

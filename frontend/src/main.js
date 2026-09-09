import { createApp } from "vue"
import App from "./App.vue"
import router from "./router"
import { setConfig, frappeRequest, resourcesPlugin } from "frappe-ui"

import "./theme/tokens.css"
import "./main.css"

import { initTheme } from "@/composables/theme"
import { replayQueue } from "@/composables/offlineQueue"
// Imported for its side effect: registers the beforeinstallprompt/appinstalled
// listeners as early as possible, so they're already in place whenever the
// browser actually fires beforeinstallprompt - the Settings screen's own
// Install button (the only place that prompt now surfaces) may not be open
// yet, or ever, before that happens.
import "@/composables/installPrompt"
import FrappePushNotification from "../public/frappe-push-notification"

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
    registerServiceWorker()
  }
})

// Registers the same service worker for both offline shell caching (Workbox)
// and push notifications (Firebase Messaging's background handler) - one
// worker, not two, since only one can control a given scope. The Firebase
// web config is fetched from this site's own notification_relay app and
// appended to the worker's own URL so the worker (which has no access to
// this page's JS state) can initialize Firebase itself.
//
// Registered from api/service_worker.py's endpoint, not the built
// /assets/field_sales/frontend/sw.js file directly - that URL's default
// scope is its own directory, which never covers /field_sales_app, so the
// app could never pass Chrome's installability check (no controlling SW =
// no "Install app"). That endpoint re-serves the exact same file with a
// Service-Worker-Allowed: / header, which is what makes the explicit
// scope: "/" below actually legal to request.
async function registerServiceWorker() {
  window.frappePushNotification = new FrappePushNotification("field_sales")

  // A device that installed the app before this fix still has the old,
  // wrongly-scoped registration sitting alongside whatever registers below -
  // harmless in principle (scopes are allowed to overlap), but two workers
  // both trying to control the same pages is exactly the kind of thing
  // that's worth not leaving around once there's a correct one to replace it.
  const existing = await navigator.serviceWorker.getRegistrations()
  for (const registration of existing) {
    if (registration.scope !== window.location.origin + "/") {
      registration.unregister()
    }
  }

  let serviceWorkerURL = "/api/method/field_sales.api.service_worker.script"
  let config = ""

  if (window.frappe?.boot?.push_relay_server_url) {
    try {
      config = await window.frappePushNotification.fetchWebConfig()
      serviceWorkerURL = `${serviceWorkerURL}?config=${encodeURIComponent(JSON.stringify(config))}`
    } catch (err) {
      console.error("Failed to fetch FCM config", err)
    }
  }

  navigator.serviceWorker
    .register(serviceWorkerURL, { type: "classic", scope: "/" })
    .then((registration) => {
      if (config) {
        window.frappePushNotification.initialize(registration).then(() => {
          console.log("Frappe Push Notification initialized")
        })
      }
    })
    .catch(() => {
      // PWA install still works without the service worker; just no offline shell caching
    })
}

import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import { VitePWA } from "vite-plugin-pwa"
import frappeui from "frappe-ui/vite"
import path from "path"
import fs from "fs"

export default defineConfig({
  server: {
    port: 8090,
    proxy: getProxyOptions(),
    allowedHosts: true,
  },
  plugins: [
    vue(),
    frappeui(),
    VitePWA({
      registerType: "autoUpdate",
      // injectManifest (not generateSW) because push notifications need a
      // service worker that also runs Firebase Messaging's own
      // onBackgroundMessage handler (public/sw.js) - generateSW only ever
      // produces a plain Workbox precache worker with no room for that.
      // injectRegister: null because main.js registers the worker itself
      // (it needs the fetched Firebase config appended to the SW's own
      // URL), not the plugin's auto-injected registration snippet.
      strategies: "injectManifest",
      injectRegister: null,
      // devOptions.enabled stays off for the same reason it was turned off
      // under generateSW: running the build step inside the dev server hit
      // a real crash there (dynamic require of a CJS package from an ESM
      // context) - production's `bench build` uses a different, working
      // code path, so this only ever cost local `yarn dev`, never a deploy.
      devOptions: { enabled: false },
      // The web app manifest is served dynamically instead (api/branding.py's
      // manifest(), linked directly from index.html) so a name/icon changed
      // in the Field Sales Branding doctype reaches "Add to Home Screen"
      // without a rebuild - manifest: false stops this plugin from also
      // generating its own static manifest.webmanifest and injecting a
      // second, conflicting <link rel="manifest"> tag.
      manifest: false,
      // Workbox's precache manifest lists every asset as a URL *relative to
      // the service worker script's own location* ("assets/xyz.js", no
      // leading slash) - fine as long as the SW is served from where it's
      // built (/assets/field_sales/frontend/sw.js), but that location's
      // default scope never covers /field_sales_app, which is why the app
      // could never actually be installed (see api/service_worker.py,
      // which re-serves this exact file from a URL with scope "/" instead).
      // Rewriting every entry to an absolute path here means precaching
      // still resolves correctly no matter which URL the SW is served from.
      injectManifest: {
        modifyURLPrefix: { "": "/assets/field_sales/frontend/" },
      },
    }),
  ],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  build: {
    outDir: "../field_sales/public/frontend",
    emptyOutDir: true,
    target: "es2015",
    commonjsOptions: { include: [/tailwind.config.js/, /node_modules/] },
    sourcemap: true,
  },
  optimizeDeps: {
    include: ["frappe-ui > feather-icons", "showdown", "tailwind.config.js", "engine.io-client", "socket.io-client", "debug"],
  },
})

function getProxyOptions() {
  const config = getCommonSiteConfig()
  const webserver_port = config ? config.webserver_port : 8000
  return {
    "^/(app|login|api|assets|files|private)": {
      target: "http://127.0.0.1:" + webserver_port,
      ws: true,
      router: function (req) {
        const site_name = req.headers.host.split(":")[0]
        return "http://" + site_name + ":" + webserver_port
      },
    },
  }
}

function getCommonSiteConfig() {
  let currentDir = path.resolve(".")
  while (currentDir !== "/") {
    if (fs.existsSync(path.join(currentDir, "sites")) && fs.existsSync(path.join(currentDir, "apps"))) {
      let configPath = path.join(currentDir, "sites", "common_site_config.json")
      if (fs.existsSync(configPath)) return JSON.parse(fs.readFileSync(configPath))
      return null
    }
    currentDir = path.resolve(currentDir, "..")
  }
  return null
}

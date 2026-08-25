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
      strategies: "generateSW",
      workbox: { globPatterns: ["**/*.{js,css,html,ico,png,svg}"] },
      devOptions: { enabled: true },
      manifest: {
        display: "standalone",
        name: "Field Sales",
        short_name: "Field Sales",
        start_url: "/field_sales_app",
        description: "Field sales, beat planning and customer visit management",
        theme_color: "#8EC641",
        background_color: "#FAFAFB",
        icons: [
          { src: "/assets/field_sales/manifest/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
          { src: "/assets/field_sales/manifest/icon-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
          { src: "/assets/field_sales/manifest/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
          { src: "/assets/field_sales/manifest/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
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

import { ref } from "vue"
import { get, set, del, keys } from "idb-keyval"
import { call } from "frappe-ui"

// A small durable queue for writes made while offline. Each entry is a
// whitelisted method call {id, method, args, label, createdAt}. Entries are
// replayed in order as soon as the browser reports it is back online, and
// the status ref lets any part of the UI show a persistent sync indicator -
// the original app had no such indicator at all, which is the single
// biggest missing capability called out in the productization review.

const PREFIX = "field_sales:queue:"

export const syncState = ref("synced") // synced | pending | syncing | failed
export const pendingCount = ref(0)
export const lastError = ref(null)

async function allKeys() {
  const all = await keys()
  return all.filter((k) => typeof k === "string" && k.startsWith(PREFIX))
}

async function refreshCount() {
  const ks = await allKeys()
  pendingCount.value = ks.length
  if (pendingCount.value === 0 && syncState.value !== "syncing") {
    syncState.value = "synced"
  } else if (pendingCount.value > 0 && syncState.value === "synced") {
    syncState.value = "pending"
  }
}

/**
 * Queue a whitelisted-method write. If online, it is attempted immediately;
 * on failure (network error) it falls back to the durable queue instead of
 * surfacing a dead-end error, so a rep on a bad connection can keep working.
 */
export async function queueWrite({ method, args = {}, label = method }) {
  if (navigator.onLine) {
    try {
      return await call(method, args)
    } catch (err) {
      // Only queue genuine connectivity failures - a validation error from
      // the server (400/403/417) should surface immediately, not vanish into
      // a queue that will just fail again on replay.
      if (!isNetworkError(err)) throw err
    }
  }

  const id = `${PREFIX}${Date.now()}:${Math.random().toString(36).slice(2)}`
  await set(id, { method, args, label, createdAt: Date.now() })
  await refreshCount()
  return { queued: true, id }
}

function isNetworkError(err) {
  return !err?.response && !err?.exc_type
}

export async function replayQueue() {
  const ks = await allKeys()
  if (!ks.length) {
    await refreshCount()
    return
  }
  syncState.value = "syncing"
  ks.sort()
  for (const k of ks) {
    const entry = await get(k)
    if (!entry) continue
    try {
      await call(entry.method, entry.args)
      await del(k)
    } catch (err) {
      if (isNetworkError(err)) {
        // still offline / server unreachable - stop and try again later
        syncState.value = "failed"
        lastError.value = "Waiting for a connection to sync pending changes."
        await refreshCount()
        return
      }
      // a genuine server-side rejection - drop it, it will never succeed,
      // but tell the user rather than silently losing their entry
      lastError.value = `A queued change (${entry.label}) was rejected: ${err.messages?.[0] || err.message || "unknown error"}`
      await del(k)
    }
  }
  await refreshCount()
}

window.addEventListener("online", () => {
  replayQueue()
})

window.addEventListener("offline", () => {
  refreshCount()
})

refreshCount()

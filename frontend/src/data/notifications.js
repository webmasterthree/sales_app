import { ref } from "vue"
import { call } from "frappe-ui"

export const unreadCount = ref(0)

export async function refreshUnreadCount() {
  try {
    const res = await call("field_sales.api.home.notifications", { unread_only: 1, limit: 1 })
    unreadCount.value = res?.unread_count || 0
  } catch (e) {
    // silent - the badge is a nicety, not core functionality
  }
}

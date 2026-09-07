import { computed, reactive } from "vue"
import { createResource, call } from "frappe-ui"
import router from "@/router"

export function sessionUser() {
  const cookies = new URLSearchParams(document.cookie.split("; ").join("&"))
  let user = cookies.get("user_id")
  if (!user || user === "Guest") user = null
  return user ? decodeURIComponent(user) : null
}

export const userResource = createResource({
  url: "field_sales.api.auth.session",
  cache: "field_sales:session",
  onError(error) {
    if (error && (error.exc_type === "AuthenticationError" || error.httpStatus === 403)) {
      session.user = null
    }
  },
})

function handleLogin(response) {
  if (response && response.message === "Logged In") {
    session.user = sessionUser()
    userResource.reload()
    router.replace({ path: "/" })
    return true
  }
  return false
}

export const session = reactive({
  login: async (email, password) => {
    const response = await call("login", { usr: email, pwd: password })
    handleLogin(response)
    return response
  },
  requestOtp: (email) => call("field_sales.api.auth.request_login_otp", { email }),
  loginWithOtp: async (email, otp) => {
    const response = await call("field_sales.api.auth.verify_login_otp", { email, otp })
    if (response && response.user) {
      session.user = sessionUser()
      userResource.reload()
      router.replace({ path: "/" })
    }
    return response
  },
  forgotPassword: (email) =>
    call("frappe.core.doctype.user.user.reset_password", { user: email }),
  logout: createResource({
    url: "logout",
    onSuccess() {
      userResource.reset()
      session.user = sessionUser()
      router.replace({ name: "Login" })
      window.location.reload()
    },
  }),
  user: sessionUser(),
  isLoggedIn: computed(() => !!session.user),
})

// Shared file-upload path for the whole app - shop photos on a Field Visit,
// KYC document images on Customer Onboarding, complaint photos. One place
// wrapping Frappe's own native /api/method/upload_file endpoint (multipart,
// session-authenticated, permission-checked against doctype+docname) rather
// than three modules each inventing their own upload logic.
//
// Deliberately does NOT go through the offline queue: a file blob can't be
// serialized into the IndexedDB write-queue the way a plain JSON write can.
// A rep who's offline sees a clear "you're offline" error rather than a
// silently-dropped photo - queueing binary uploads is real scope, not
// something to fake here.

export async function uploadFile({ file, doctype, docname, fieldname, isPrivate = 1, onProgress }) {
  if (!navigator.onLine) {
    throw new Error("You're offline - photo uploads need a connection. Try again once you're back online.")
  }

  const form = new FormData()
  form.append("file", file, file.name)
  form.append("is_private", isPrivate ? "1" : "0")
  // Frappe's own upload_file checks doctype-level "write" permission the
  // moment `doctype` is set, even with no `docname` - and that check runs
  // without any document to test territory/ownership restrictions against,
  // so it fails closed for a scoped role even though the same role can
  // write its own records fine. On a create form (no docname yet - the
  // parent record doesn't exist), the safe and actually-working thing is a
  // loose, unattached private file: the resulting file_url still slots
  // into an Attach/Attach Image field just fine once the parent saves.
  if (docname) {
    form.append("doctype", doctype)
    form.append("docname", docname)
    if (fieldname) form.append("fieldname", fieldname)
  }

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open("POST", "/api/method/upload_file")
    xhr.setRequestHeader("X-Frappe-CSRF-Token", window.csrf_token || "")
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100))
    }
    xhr.onload = () => {
      try {
        const body = JSON.parse(xhr.responseText)
        if (xhr.status >= 200 && xhr.status < 300 && body.message) {
          resolve(body.message) // { file_url, name, file_name, ... }
        } else {
          reject(new Error(body.exception || body.message || "Upload failed."))
        }
      } catch {
        reject(new Error("Upload failed - the server didn't return a valid response."))
      }
    }
    xhr.onerror = () => reject(new Error("Upload failed - check your connection."))
    xhr.send(form)
  })
}

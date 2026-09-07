// Shared shape for LocationConfirmModal.vue's popup, built from wherever a
// GPS fix was just captured (visit check-in/out, attendance punch).
export function buildLocationConfirm(label, pos) {
  const at = new Date()
  return {
    label,
    time: at.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true }).toLowerCase(),
    date: `${at.getDate()} ${at.toLocaleDateString("en-US", { month: "short" })}, ${at.getFullYear()}`,
    lat: pos.latitude,
    lon: pos.longitude,
  }
}

// Shared geolocation/check-in helpers for Field Visit - used by both the
// New Visit form (which now requires check-in before the rest of the form
// unlocks) and the visit Detail page (check-in/out actions on an existing
// draft). Pulled out to one place rather than duplicated across both.

function requestPosition(options) {
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
      () => resolve(null),
      options
    )
  })
}

// Resolves to coordinates, or null if no fix could be obtained. Geofencing
// is always on server-side, so a caller should treat null as a hard stop
// rather than proceeding with a blank position.
//
// The device usually already has a recent network/cell fix cached from the
// OS - accepting one up to a minute old (maximumAge) makes this resolve
// almost instantly in the common case, instead of always forcing a fresh
// GPS lock. Only when nothing cached is available does this fall back to a
// slower, dedicated high-accuracy GPS request.
export async function getPosition() {
  if (!navigator.geolocation) return null
  const quick = await requestPosition({ enableHighAccuracy: false, timeout: 5000, maximumAge: 60000 })
  if (quick) return quick
  return requestPosition({ enableHighAccuracy: true, timeout: 15000, maximumAge: 0 })
}

// The server stamps check_in/check_out with a naive datetime in the site's
// own timezone, with no offset attached. Parsing that string as if it were
// in the *client's* timezone (as `new Date(str)` does) silently produces a
// wrong, sometimes-future instant whenever a rep's device timezone differs
// from the site's configured one - which then freezes a running timer at
// 00:00:00 forever. Anchoring on the client's own clock at the moment
// check-in actually succeeds (recorded in sessionStorage so a reload during
// the same visit keeps ticking from the same anchor) avoids that.
export function anchorKey(visitName) {
  return `field_sales:checkin_anchor:${visitName}`
}

export function setAnchor(visitName) {
  sessionStorage.setItem(anchorKey(visitName), String(Date.now()))
}

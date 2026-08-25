# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Distance and geofencing.

Straight-line (haversine) distance, computed locally.

The implementation this replaces called Google's Distance Matrix API on every
check-in. That is the wrong measure for "is the rep standing at the shop" -
Distance Matrix returns *driving* distance, so an outlet across the road can
come back as 300 metres - and it costs a billed API call plus a network round
trip on the critical path of a rep starting a visit. It also took both the
origin and the destination from the client, which makes the check advisory
rather than enforced.
"""

import math

import frappe
from frappe.utils import cint, flt

EARTH_RADIUS_M = 6371008.8


def haversine_metres(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two points, in metres."""
    lat1, lon1, lat2, lon2 = flt(lat1), flt(lon1), flt(lat2), flt(lon2)

    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def is_valid_position(latitude, longitude) -> bool:
    """Reject nulls and the (0, 0) that devices report when they have no fix."""
    if latitude in (None, "") or longitude in (None, ""):
        return False
    lat, lon = flt(latitude), flt(longitude)
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return False
    # Null Island: almost always a failed fix rather than a real position
    return not (abs(lat) < 0.0001 and abs(lon) < 0.0001)


def settings():
    return frappe.get_cached_doc("Field Sales Settings")


def address_position(address: str | None):
    """The stored coordinates of an outlet, or None."""
    if not address:
        return None
    row = frappe.db.get_value(
        "Address", address, ["fs_latitude", "fs_longitude"], as_dict=True
    )
    if not row or not is_valid_position(row.fs_latitude, row.fs_longitude):
        return None
    return flt(row.fs_latitude), flt(row.fs_longitude)


def anchor_address(address: str, latitude, longitude) -> None:
    """Record where an outlet is, from the first check-in that reaches it."""
    frappe.db.set_value(
        "Address",
        address,
        {"fs_latitude": flt(latitude), "fs_longitude": flt(longitude)},
        update_modified=False,
    )


def evaluate(address: str | None, latitude, longitude) -> dict:
    """Compare a captured position against an outlet.

    Returns ``{"status", "distance", "radius", "blocked", "message"}``.
    ``status`` is Inside, Outside or Not Checked. A missing anchor or a missing
    fix is Not Checked - it is never silently treated as Inside.
    """
    cfg = settings()
    radius = cint(cfg.geofence_radius) or 0
    behaviour = cfg.geofence_behaviour or "Warn"

    result = {
        "status": "Not Checked",
        "distance": None,
        "radius": radius,
        "blocked": False,
        "message": "",
    }

    if not cint(cfg.enforce_geofence):
        return result

    if not is_valid_position(latitude, longitude):
        result["message"] = frappe._("No usable location fix was supplied.")
        return result

    target = address_position(address)
    if not target:
        # First visit to this outlet: adopt the position as its anchor.
        if address and cint(cfg.anchor_on_first_visit):
            anchor_address(address, latitude, longitude)
            result["status"] = "Inside"
            result["distance"] = 0
            result["message"] = frappe._("Outlet location recorded from this visit.")
        else:
            result["message"] = frappe._("This outlet has no recorded location.")
        return result

    distance = int(round(haversine_metres(latitude, longitude, target[0], target[1])))
    result["distance"] = distance

    if distance <= radius:
        result["status"] = "Inside"
        return result

    result["status"] = "Outside"
    result["message"] = frappe._(
        "You are {0} m from the outlet; the allowed radius is {1} m."
    ).format(distance, radius)
    result["blocked"] = behaviour == "Block"
    return result


@frappe.whitelist()
def check_position(address: str, latitude: float, longitude: float) -> dict:
    """Let the client preview the geofence before committing to a check-in.

    Advisory only - the authoritative check runs server-side inside check_in.
    """
    return evaluate(address, latitude, longitude)

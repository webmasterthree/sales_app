# Copyright (c) 2026, Edubild Technologies and contributors
# For license information, please see license.txt
"""Authentication for the field sales client.

The client is served from the same origin as the Frappe site, so it signs in
with an ordinary Frappe session cookie by POSTing to the framework's own
``/api/method/login``. Nothing here re-implements password checking, account
lockout, two-factor or session expiry - Frappe already does all of that, and
the app this was derived from got into trouble by rebuilding it.

What this module adds is an email one-time-code flow, for password-less
sign-in and recovery. It is deliberately strict:

* the code is never returned to the caller, only emailed,
* it is stored as a keyed digest under a per-user key,
* verification is constant-time and attempt-limited with an atomic counter,
* and asking for a code for an unknown address is indistinguishable from
  asking for one for a real account.
"""

import hashlib
import hmac
import secrets

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

OTP_LENGTH = 6
OTP_TTL_SECONDS = 5 * 60
OTP_MAX_ATTEMPTS = 5


# ---------------------------------------------------------------- cache
#
# These use the Redis client directly rather than frappe.cache().get_value /
# set_value. Those helpers keep a per-process copy in frappe.local.cache, but
# a write carrying expires_in_sec does not refresh it - so a read-modify-write
# counter silently keeps reading the first value it ever saw. For an attempt
# limiter that is the difference between five guesses and unlimited ones.


def _redis():
    return frappe.cache()


def _key(kind: str, user: str) -> str:
    """Scope every artefact to one user.

    The implementation this replaces kept a single global ``otp`` key, so two
    people resetting a password at the same time overwrote each other, and
    whoever called last could verify against the other person's code.
    """
    digest = hashlib.sha256(user.strip().lower().encode()).hexdigest()[:32]
    return _redis().make_key(f"field_sales:{kind}:{digest}")


def _hash_otp(otp: str, user: str) -> str:
    """Keep only a keyed digest of the code, never the code itself."""
    secret = (
        frappe.local.conf.get("encryption_key")
        or frappe.local.conf.get("secret")
        or frappe.local.site
    )
    msg = f"{user.strip().lower()}:{otp}".encode()
    return hmac.new(str(secret).encode(), msg, hashlib.sha256).hexdigest()


def _store_otp(user: str, otp: str) -> None:
    r = _redis()
    r.set(_key("otp", user), _hash_otp(otp, user).encode(), ex=OTP_TTL_SECONDS)
    r.delete(_key("attempts", user))


def _read_otp(user: str) -> str | None:
    raw = _redis().get(_key("otp", user))
    if raw is None:
        return None
    return raw.decode() if isinstance(raw, bytes) else str(raw)


def _bump_attempts(user: str) -> int:
    """Atomically count a failed guess and return the new total."""
    r = _redis()
    key = _key("attempts", user)
    count = int(r.incrby(key, 1))
    if count == 1:
        r.expire(key, OTP_TTL_SECONDS)
    return count


def clear_otp(user: str) -> None:
    r = _redis()
    r.delete(_key("otp", user))
    r.delete(_key("attempts", user))


def _generate_otp() -> str:
    return str(secrets.randbelow(10**OTP_LENGTH)).zfill(OTP_LENGTH)


# ---------------------------------------------------------------- users


def _resolve_user(email: str) -> str | None:
    """Return the enabled User for an address, or None. Never raises."""
    if not email:
        return None
    return frappe.db.get_value(
        "User", {"name": (email or "").strip().lower(), "enabled": 1}, "name"
    )


def session_payload(user: str) -> dict:
    """The profile the client needs immediately after signing in."""
    employee = (
        frappe.db.get_value(
            "Employee",
            {"user_id": user, "status": "Active"},
            ["name", "employee_name", "designation"],
            as_dict=True,
        )
        or frappe._dict()
    )

    return {
        "user": user,
        "full_name": frappe.db.get_value("User", user, "full_name"),
        "employee": employee.get("name"),
        "employee_name": employee.get("employee_name"),
        "designation": employee.get("designation"),
        "roles": frappe.get_roles(user),
        "territories": frappe.get_all(
            "User Permission",
            filters={"user": user, "allow": "Territory"},
            pluck="for_value",
        ),
    }


@frappe.whitelist()
def session() -> dict:
    """Who am I? Called by the client on boot to decide whether to show login.

    Sign-in itself goes to Frappe's own ``/api/method/login``; this only
    reports on the session that produced.
    """
    if frappe.session.user == "Guest":
        raise frappe.AuthenticationError(_("Not signed in"))
    return session_payload(frappe.session.user)


# ---------------------------------------------------------------- otp


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="email", limit=5, seconds=60 * 60)
def request_login_otp(email: str) -> dict:
    """Email a one-time code.

    Responds identically whether or not the address belongs to an account, so
    the endpoint cannot be used to enumerate users.
    """
    user = _resolve_user(email)
    if user:
        otp = _generate_otp()
        _store_otp(user, otp)
        # A delivery failure must not become an oracle. It can only ever fire
        # for an address that exists, which is precisely what the generic
        # response below is there to hide - and Frappe surfaces anything added
        # to the message log in `_server_messages`, so the log has to be put
        # back exactly as we found it.
        messages_before = list(frappe.local.message_log or [])
        try:
            send_otp_email(user, otp)
        except Exception:
            frappe.log_error(
                title="Field Sales: sign-in code delivery failed",
                message=frappe.get_traceback(),
            )
        finally:
            frappe.local.message_log = messages_before

    return {
        "message": _("If that address has an account, a code is on its way."),
        "expires_in": OTP_TTL_SECONDS,
    }


def send_otp_email(user: str, otp: str) -> None:
    frappe.sendmail(
        recipients=[user],
        subject=_("Your sign-in code"),
        message=_(
            "<p>Your sign-in code is <b>{0}</b>.</p>"
            "<p>It expires in {1} minutes. If you did not ask for it, ignore this email.</p>"
        ).format(otp, OTP_TTL_SECONDS // 60),
        now=True,
        retry=1,
    )


def consume_otp(email: str, otp: str) -> str:
    """Validate a code and return the user it belongs to.

    Raises AuthenticationError on any failure, with the same message and
    roughly the same cost whatever went wrong. Separated from the endpoint so
    it can be tested without a live request context.
    """
    invalid = _("That code is not valid.")
    too_many = _("Too many incorrect attempts. Please request a new code.")

    user = _resolve_user(email)
    if not user:
        raise frappe.AuthenticationError(invalid)

    stored = _read_otp(user)
    if not stored:
        raise frappe.AuthenticationError(invalid)

    if not hmac.compare_digest(stored, _hash_otp(str(otp or ""), user)):
        if _bump_attempts(user) >= OTP_MAX_ATTEMPTS:
            # Burn the code the moment the limit is reached, rather than
            # letting one more request spend it.
            clear_otp(user)
            raise frappe.AuthenticationError(too_many)
        raise frappe.AuthenticationError(invalid)

    clear_otp(user)
    return user


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(key="email", limit=10, seconds=60 * 60)
def verify_login_otp(email: str, otp: str) -> dict:
    """Exchange a valid code for a session."""
    user = consume_otp(email, otp)
    frappe.local.login_manager.login_as(user)
    frappe.local.login_manager.post_login()
    frappe.db.commit()
    return session_payload(user)

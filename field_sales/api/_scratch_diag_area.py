"""Read-only: diagnose the 'linked to Territory KOLAR CITY TT in field Area'
permission error on Customer A & B ENTERPRISES for sales.east@mohanimpex.com."""

import frappe


def run():
    customer = "A & B ENTERPRISES"
    se_user = "sales.east@mohanimpex.com"

    meta = frappe.get_meta("Customer")
    territory_link_fields = [
        f.fieldname for f in meta.fields if f.fieldtype == "Link" and f.options == "Territory"
    ]
    print("Customer fields linking to Territory:", territory_link_fields)

    doc = frappe.db.get_value("Customer", customer, territory_link_fields, as_dict=True)
    print("Customer's values in those fields:", doc)

    perms = frappe.get_all(
        "User Permission", filters={"user": se_user, "allow": "Territory"},
        fields=["for_value", "applicable_for", "apply_to_all_doctypes"],
    )
    print(f"\n{se_user}'s Territory User Permissions:", perms)

    # Is there any User Permission scoped specifically to Customer that would
    # narrow which link field it applies to?
    print("\nCan sales.east read this Customer via frappe.has_permission?")
    frappe.set_user(se_user)
    try:
        can_read = frappe.has_permission("Customer", "read", doc=customer)
        print("has_permission result:", can_read)
    except Exception as e:
        print("has_permission raised:", repr(e))
    finally:
        frappe.set_user("Administrator")

    # Does the visit's own territory field actually match customer.territory?
    fv = frappe.db.get_value(
        "Field Visit", "FV-2026-08-00019", ["territory", "customer"], as_dict=True
    )
    print("\nField Visit FV-2026-08-00019's own territory:", fv)

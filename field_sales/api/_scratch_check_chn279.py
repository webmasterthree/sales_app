import frappe


def run():
    name = "SO-CHN-0279-26-27"
    if not frappe.db.exists("Sales Order", name):
        print("Sales Order does not exist:", name)
        return

    doc = frappe.db.get_value(
        "Sales Order", name,
        ["docstatus", "customer", "contact_person", "contact_mobile", "grand_total", "delivery_date"],
        as_dict=True,
    )
    print("Order:", doc)

    logs = frappe.get_all(
        "WhatsApp Message Log",
        filters={"reference_doctype": "Sales Order", "reference_name": name},
        fields=["name", "to_number", "template_name", "status", "error", "creation"],
    )
    print("\nWhatsApp Message Log entries:", logs)

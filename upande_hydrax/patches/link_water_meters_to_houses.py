import frappe

from upande_hydrax.upande_hydrax.tasks import ensure_house


def execute():
    """Give every Water Meter without a house the House named after its Calin
    customer ID (VV034, Yamin26), so staff can find meters by house number."""
    meters = frappe.get_all(
        "Water Meter",
        filters={"house_number": ["is", "not set"], "calin_customer_id": ["is", "set"]},
        fields=["name", "calin_customer_id", "site"],
    )
    for meter in meters:
        house = ensure_house(meter.calin_customer_id, meter.site)
        if house:
            frappe.db.set_value("Water Meter", meter.name, "house_number", house, update_modified=False)

    # Customize Form had hidden these columns; property setters override the
    # doctype, so drop them and let the doctype show the house in the list
    frappe.db.delete("Property Setter", {
        "doc_type": "Water Meter",
        "field_name": ["in", ["house_number", "calin_customer_id"]],
        "property": "in_list_view",
    })
    frappe.clear_cache(doctype="Water Meter")

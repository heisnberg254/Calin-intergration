import frappe


def execute():
    """Give every existing Token Record the house of its meter, so token
    history can be read and filtered by house number."""
    frappe.db.sql(
        """
        UPDATE `tabToken Record` tr
        JOIN `tabWater Meter` wm ON wm.name = tr.meter
        SET tr.house = wm.house_number
        WHERE IFNULL(wm.house_number, '') != ''
            AND IFNULL(tr.house, '') != wm.house_number
        """
    )

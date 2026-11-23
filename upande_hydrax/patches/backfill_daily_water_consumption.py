import frappe

from upande_hydrax.upande_hydrax.consumption import rebuild


def execute():
    """Estimate daily water use for every day since the first token."""
    first = frappe.db.sql("SELECT MIN(DATE(created_date)) FROM `tabToken Record`")[0][0]
    if first:
        rebuild(first)

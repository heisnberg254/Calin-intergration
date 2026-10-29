import frappe
from frappe.utils import get_first_day, get_last_day, getdate, nowdate

# Error Log title for anything the monthly billing couldn't invoice
BILLING_ERROR_TITLE = "Service Charge Billing"


@frappe.whitelist()
def raise_monthly_service_charges(posting_date: str | None = None):
    """Raise one submitted Sales Invoice per customer for the month's service
    charge, a line per water meter, at the rate URL Setup Settings sets for the
    meter's tariff and site. Safe to run again: a customer already invoiced for
    the month is skipped. Runs on the 1st of every month."""
    frappe.only_for("System Manager")

    settings = frappe.get_single("URL Setup Settings")
    if not (settings.service_charge_company and settings.service_charge_item and settings.service_charge_rates):
        return

    posting_date = getdate(posting_date or nowdate())
    month_start, month_end = get_first_day(posting_date), get_last_day(posting_date)
    month_label = posting_date.strftime("%B %Y")

    # Meters reach a Customer through the Calin customer ID both carry
    customers = {
        _normalise(c.calin_customer_id): c.name
        for c in frappe.get_all(
            "Customer",
            filters={"calin_customer_id": ["is", "set"], "disabled": 0},
            fields=["name", "calin_customer_id"],
        )
    }

    charges, no_customer = {}, []
    for meter in frappe.get_all(
        "Water Meter",
        filters={"status": ["!=", "Inactive"]},
        fields=["name", "calin_customer_id", "tariff_id", "site"],
    ):
        amount = _monthly_rate(meter, settings.service_charge_rates)
        if not amount:
            continue

        customer = customers.get(_normalise(meter.calin_customer_id))
        if not customer:
            no_customer.append(meter.name)
            continue

        charges.setdefault(customer, []).append((meter.name, amount))

    created = 0
    for customer, lines in charges.items():
        if _already_invoiced(customer, settings.service_charge_item, month_start, month_end):
            continue

        try:
            invoice = frappe.get_doc({
                "doctype": "Sales Invoice",
                "customer": customer,
                "company": settings.service_charge_company,
                "set_posting_time": 1,
                "posting_date": posting_date,
                "due_date": posting_date,
                "remarks": f"Water service charge for {month_label}",
                "items": [
                    {
                        "item_code": settings.service_charge_item,
                        "qty": 1,
                        "rate": amount,
                        "description": f"Water service charge for {month_label}, meter {meter_id}",
                    }
                    for meter_id, amount in lines
                ],
            })
            invoice.insert(ignore_permissions=True)
            invoice.submit()
            frappe.db.commit()
            created += 1
        except Exception:
            frappe.db.rollback()
            frappe.log_error(
                f"Service charge for {month_label} not invoiced to {customer}\n{frappe.get_traceback()}",
                BILLING_ERROR_TITLE,
            )

    if no_customer:
        frappe.log_error(
            f"{len(no_customer)} meters have a {month_label} service charge but no Customer carries their "
            f"Calin customer ID, so they were not invoiced: {', '.join(no_customer)}",
            BILLING_ERROR_TITLE,
        )

    return {"invoices_created": created, "meters_without_customer": len(no_customer)}


def outstanding_service_charge(customer, item_code):
    """Unpaid service charge across a customer's submitted invoices."""
    if not customer or not item_code:
        return 0

    return frappe.db.sql(
        """SELECT COALESCE(SUM(si.outstanding_amount), 0) FROM `tabSales Invoice` si
        WHERE si.customer = %s AND si.docstatus = 1 AND si.outstanding_amount > 0
            AND EXISTS (SELECT 1 FROM `tabSales Invoice Item` sii
                WHERE sii.parent = si.name AND sii.item_code = %s)""",
        (customer, item_code),
    )[0][0]


def _monthly_rate(meter, rates):
    """The rate of the row matching the meter most closely: tariff and site,
    then tariff alone, then site alone, then a row with neither as a catch-all.
    Case and spaces are ignored, since Calin's site names vary ("Valley View",
    "ValleyView")."""
    best, best_score = None, -1
    for rate in rates:
        if rate.tariff_id and _normalise(rate.tariff_id) != _normalise(meter.tariff_id):
            continue
        if rate.site and _normalise(rate.site) != _normalise(meter.site):
            continue

        score = 2 * bool(rate.tariff_id) + bool(rate.site)
        if score > best_score:
            best, best_score = rate, score

    return best.monthly_amount if best else 0


def _already_invoiced(customer, item_code, month_start, month_end):
    return frappe.db.sql(
        """SELECT si.name FROM `tabSales Invoice` si
        JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
        WHERE si.customer = %s AND si.docstatus < 2 AND sii.item_code = %s
            AND si.posting_date BETWEEN %s AND %s
        LIMIT 1""",
        (customer, item_code, month_start, month_end),
    )


def _normalise(value):
    return (value or "").replace(" ", "").lower()

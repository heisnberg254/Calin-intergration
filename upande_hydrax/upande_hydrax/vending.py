import frappe
import requests
from frappe.core.doctype.sms_settings.sms_settings import send_sms

from upande_hydrax.upande_hydrax.tasks import token_record_fields

# Error Log titles; the "M-Pesa Payment Failed" Notification alerts staff on these
VEND_ERROR_TITLE = "Calin Token Vend Error"
SMS_ERROR_TITLE = "Calin Token SMS Not Sent"


def queue_token_vend(doc, method=None):
    """doc_events hook: once an M-Pesa C2B payment is submitted, vend its token
    in the background so a slow or failing Calin call never blocks the payment."""
    frappe.enqueue(
        "upande_hydrax.upande_hydrax.vending.vend_token",
        queue="short",
        job_id=f"calin_vend::{doc.name}",
        deduplicate=True,
        enqueue_after_commit=True,
        c2b_name=doc.name,
    )


@frappe.whitelist()
def retry_token_vend(c2b_name: str):
    frappe.has_permission("Mpesa C2B Payment Register", "write", c2b_name, throw=True)
    vend_token(c2b_name)


def vend_token(c2b_name):
    """Buy a Calin water token for an M-Pesa C2B payment, save it as a Token
    Record and SMS it to the customer. The paybill account number is the Calin
    customer ID."""
    c2b = frappe.get_doc("Mpesa C2B Payment Register", c2b_name)

    # Only a submitted payment has been accepted against a customer; a draft
    # one is still waiting for someone to sort it out
    if c2b.docstatus != 1:
        return

    # One token per M-Pesa transaction, however many times this runs
    existing = frappe.db.exists("Token Record", {"mpesa_receipt_number": c2b.transid})
    if existing:
        return existing

    meter_id = _find_meter(c2b.billrefnumber)
    if not meter_id:
        return

    settings = frappe.get_single("URL Setup Settings")
    vending_password = settings.get_password("vending_password", raise_exception=False)
    if not vending_password:
        _log_vend_error(c2b, "Vending Authorization Password is not set in URL Setup Settings")
        return

    headers = {"Authorization": f"Bearer {settings.get_password('api_token')}"}
    url = f"{settings.base_url}/API/Token/CreditWaterToken/Generate"
    body = {
        "meterId": meter_id,
        "amount": c2b.transamount,
        "isVendByTotalPaid": True,
        "isPreview": False,
        "authorizationPassword": vending_password,
        "company": settings.company,
    }

    try:
        response = requests.post(url, json=body, headers=headers, timeout=60)
        payload = response.json()
    except Exception:
        # The request may still have reached Calin, so never auto-retry here:
        # staff must check Calin before vending again
        _log_vend_error(c2b, f"No response from Calin; check Calin before retrying\n{frappe.get_traceback()}")
        return

    if payload.get("code") != 0 or not (payload.get("result") or {}).get("token"):
        _log_vend_error(c2b, f"Calin refused the token: {payload}")
        return

    row = payload["result"]
    try:
        fields = token_record_fields(row)
        fields.update({
            "doctype": "Token Record",
            "receipt_id": str(row["receiptId"]),
            "meter": meter_id,
            "mpesa_receipt_number": c2b.transid,
            "type": "Top Up",
        })
        token_record = frappe.get_doc(fields).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        # Calin has issued the token; keep everything needed to record it by hand
        _log_vend_error(c2b, f"Token issued by Calin but not saved: {row}\n{frappe.get_traceback()}")
        return

    _send_token_sms(c2b, token_record, settings, headers)
    return token_record.name


def _find_meter(bill_ref):
    """Return the Water Meter for a Calin customer ID typed as the paybill account
    number, ignoring case and spaces ("upande 1" finds "Upande1")."""
    ref = (bill_ref or "").replace(" ", "")
    if not ref:
        return None

    meters = frappe.db.sql(
        """SELECT name FROM `tabWater Meter`
        WHERE REPLACE(calin_customer_id, ' ', '') = %s AND status != 'Inactive'""",
        (ref,),
        pluck=True,
    )
    if len(meters) == 1:
        return meters[0]

    # Unknown ID, or one ID on several meters - a person has to pick the meter
    reason = "no Water Meter" if not meters else f"{len(meters)} Water Meters ({', '.join(meters)})"
    frappe.log_error(f"Account number {bill_ref!r} matches {reason}", VEND_ERROR_TITLE)
    return None


def _log_vend_error(c2b, message):
    frappe.log_error(
        f"C2B {c2b.name}, M-Pesa {c2b.transid}, KES {c2b.transamount}, account {c2b.billrefnumber}\n{message}",
        VEND_ERROR_TITLE,
    )


def _send_token_sms(c2b, token_record, settings, headers):
    phone = _customer_phone(c2b, token_record.customer_id, settings, headers)
    if not phone:
        frappe.log_error(
            f"No phone for Calin customer {token_record.customer_id}; token {token_record.token} "
            f"(Token Record {token_record.name}) must be given to the customer another way",
            SMS_ERROR_TITLE,
        )
        return

    msg = (
        f"Hydrax Water: your token for meter {token_record.meter} is {token_record.token}. "
        f"KES {c2b.transamount}, {token_record.total_unit} units. M-Pesa ref {c2b.transid}."
    )
    send_sms([phone], msg, success_msg=False)


def _customer_phone(c2b, calin_customer_id, settings, headers):
    """The payer's number is masked by Safaricom, so use the phone on the ERPNext
    Customer, falling back to the one held in Calin."""
    if c2b.customer:
        phone = frappe.db.get_value("Customer", c2b.customer, "mobile_no")
        if phone:
            return phone

    try:
        response = requests.post(
            f"{settings.base_url}/API/Customer/Read",
            json={"customerId": calin_customer_id, "pageNumber": 1, "pageSize": 1, "company": settings.company},
            headers=headers,
            timeout=30,
        )
        rows = response.json()["result"]["data"]
    except Exception:
        return None

    return rows[0].get("phone") if rows else None

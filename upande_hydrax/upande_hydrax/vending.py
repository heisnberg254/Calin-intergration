import hashlib
import re

import frappe
import requests
from frappe.utils import flt, nowdate
from frappe.core.doctype.sms_settings.sms_settings import send_sms
from frappe_mpsa_payments.frappe_mpsa_payments.api.payment_entry import (
    create_and_reconcile_payment_reconciliation,
)

from upande_hydrax.upande_hydrax.billing import outstanding_service_charge
from upande_hydrax.upande_hydrax.tasks import token_record_fields

# Error Log titles; the "M-Pesa Payment Failed" Notification alerts staff on these
VEND_ERROR_TITLE = "Calin Token Vend Error"
SMS_ERROR_TITLE = "Calin Token SMS Not Sent"
INVOICE_ERROR_TITLE = "Water Sale Not Invoiced"

# Safaricom hides the payer's number in C2B callbacks behind a SHA-256 hex digest
HASHED_MSISDN = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
# Africa's Talking per-recipient codes meaning the message was accepted:
# 100 Processed, 101 Sent, 102 Queued
AT_ACCEPTED = {100, 101, 102}


def queue_token_vend(doc, method=None):
    """doc_events hook: once an M-Pesa C2B payment is submitted, vend its token
    in the background so a slow or failing Calin call never blocks the payment."""
    # frappe_mpsa_payments submits the payment from its after_insert, so Frappe
    # runs on_submit twice in the same request; deduplicate can't catch that
    # because neither job is in the queue until the request commits
    if doc.flags.calin_vend_queued:
        return
    doc.flags.calin_vend_queued = True

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
    # Hold the payment row until this run commits, so two runs for the same
    # payment can't both pass the check below and each buy a token
    frappe.db.get_value("Mpesa C2B Payment Register", c2b_name, "name", for_update=True)
    c2b = frappe.get_doc("Mpesa C2B Payment Register", c2b_name)

    # Only a submitted payment has been accepted against a customer; a draft
    # one is still waiting for someone to sort it out
    if c2b.docstatus != 1:
        return

    # One token per M-Pesa transaction, however many times this runs. A locking
    # read, because a plain one sees this transaction's snapshot, taken before
    # the lock was granted, and misses a Token Record another run just saved
    existing = frappe.db.get_value(
        "Token Record", {"mpesa_receipt_number": c2b.transid}, "name", for_update=True
    )
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

    # Any unpaid service charge comes out of the payment before water is bought
    water_amount = _water_amount(c2b)
    if water_amount <= 0:
        _send_charge_only_sms(c2b, meter_id, settings, headers)
        return

    url = f"{settings.base_url}/API/Token/CreditWaterToken/Generate"
    body = {
        "meterId": meter_id,
        "amount": water_amount,
        "isVendByTotalPaid": True,
        "isPreview": True,
        "company": settings.company,
    }

    # Preview first: Calin applies the meter's tariff and any debt repayment and
    # says how much water the payment buys, without issuing anything. Vending by
    # the amount paid (not by units) keeps the token in line with the money,
    # since vending by units makes Calin add debt on top.
    try:
        preview = requests.post(url, json=body, headers=headers, timeout=60).json()
    except Exception:
        _log_vend_error(c2b, f"Calin preview failed; nothing was issued, safe to retry\n{frappe.get_traceback()}")
        return

    if preview.get("code") != 0:
        _log_vend_error(c2b, f"Calin preview refused; nothing was issued: {preview}")
        return

    unit_price = _tariff_price(preview["result"].get("tariffId"), settings, headers)

    body.update({"isPreview": False, "authorizationPassword": vending_password})
    try:
        response = requests.post(url, json=body, headers=headers, timeout=60)
        payload = response.json()
    except Exception:
        # The request may still have reached Calin, so never auto-retry here:
        # staff must check Calin before vending again
        _log_vend_error(c2b, f"No response from Calin; check Calin before retrying\n{frappe.get_traceback()}")
        return

    # code 0 means Calin has recorded the sale, even with no token: a payment too
    # small for a whole unit is credited to the meter, and must still be saved
    # here so the payment is never sold twice
    if payload.get("code") != 0 or not payload.get("result"):
        _log_vend_error(c2b, f"Calin refused the token: {payload}")
        return

    row = payload["result"]
    try:
        # Calin's generate reply carries receiptId 0; the real receipt number is
        # only on the stored record, and Token Records are named by it
        receipt_id = row.get("receiptId") or _find_receipt_id(meter_id, row, settings, headers)
        fields = token_record_fields(row)
        fields.update({
            "doctype": "Token Record",
            "receipt_id": str(receipt_id),
            "meter": meter_id,
            "mpesa_receipt_number": c2b.transid,
            "type": "Top Up",
            "unit_price": unit_price,
        })
        if row.get("totalUnit") != preview["result"].get("totalUnit"):
            fields["remark"] = (
                f"Calin previewed {preview['result'].get('totalUnit')} units but issued {row.get('totalUnit')}"
            )
        token_record = frappe.get_doc(fields).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        # Calin has issued the token; keep everything needed to record it by hand
        _log_vend_error(c2b, f"Token issued by Calin but not saved: {row}\n{frappe.get_traceback()}")
        return

    _invoice_water(c2b, token_record, water_amount, settings)
    _send_token_sms(c2b, token_record, settings, headers)
    return token_record.name


def _invoice_water(c2b, token_record, water_amount, settings):
    """Bill the water just sold and settle the bill from the M-Pesa payment, so
    the sale is booked as revenue instead of sitting on the Payment Entry as an
    unallocated advance."""
    if not settings.water_item or not c2b.customer:
        return

    try:
        invoice = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": c2b.customer,
            "company": c2b.company,
            "set_posting_time": 1,
            "posting_date": c2b.posting_date,
            "due_date": c2b.posting_date,
            "remarks": f"Water for meter {token_record.meter}, M-Pesa {c2b.transid}",
            "items": [{
                "item_code": settings.water_item,
                "qty": 1,
                "rate": water_amount,
                "description": (
                    f"{token_record.total_unit} units of water for meter {token_record.meter}, "
                    f"Calin receipt {token_record.receipt_id}"
                ),
            }],
        })
        invoice.insert(ignore_permissions=True)
        invoice.submit()

        if c2b.payment_entry:
            create_and_reconcile_payment_reconciliation(
                outstanding_invoices=[invoice.name],
                customer=c2b.customer,
                company=c2b.company,
                payment_entries=[c2b.payment_entry],
            )

        frappe.db.set_value("Token Record", token_record.name, "sales_invoice", invoice.name)
        frappe.db.commit()
    except Exception:
        # The token is already sold and saved; only the bookkeeping is missing
        frappe.db.rollback()
        frappe.log_error(
            f"C2B {c2b.name}, M-Pesa {c2b.transid}, Token Record {token_record.name}: "
            f"KES {water_amount} of water sold but not invoiced\n{frappe.get_traceback()}",
            INVOICE_ERROR_TITLE,
        )


def _water_amount(c2b):
    """What's left of a payment to buy water with. On submit, frappe_mpsa_payments
    has already applied the payment to the customer's unpaid invoices, oldest
    first (the monthly service charge), leaving the rest unallocated on its
    Payment Entry."""
    if not c2b.payment_entry:
        return c2b.transamount

    unallocated = frappe.db.get_value("Payment Entry", c2b.payment_entry, "unallocated_amount")
    return c2b.transamount if unallocated is None else unallocated


def _find_receipt_id(meter_id, row, settings, headers):
    """Look up Calin's receipt number for a sale it has just recorded, matching
    the meter's newest records on token (or, for a sale with no token, on time
    and amount). Raises if it can't be found, so the sale is logged for staff
    rather than saved under a made-up number."""
    response = requests.post(
        f"{settings.base_url}/API/Token/CreditWaterTokenRecord/Read",
        json={"meterId": meter_id, "status": True, "orderBy": "receiptId desc",
            "pageNumber": 1, "pageSize": 10, "company": settings.company},
        headers=headers,
        timeout=30,
    )
    for record in response.json()["result"]["data"]:
        if row.get("token"):
            if record.get("token") == row["token"]:
                return record["receiptId"]
        elif record.get("createDate") == row.get("createDate") and record.get("totalPaid") == row.get("totalPaid"):
            return record["receiptId"]

    raise LookupError(f"No Calin record for meter {meter_id} matches the sale just made")


def _tariff_price(tariff_id, settings, headers):
    """Price per unit of water for a Calin tariff, for the record; None if Calin
    can't say, which never stops a vend."""
    try:
        response = requests.post(
            f"{settings.base_url}/API/Tariff/Read",
            json={"tariffId": tariff_id, "pageNumber": 1, "pageSize": 1, "company": settings.company},
            headers=headers,
            timeout=30,
        )
        rows = response.json()["result"]["data"]
    except Exception:
        return None

    return rows[0].get("price") if rows else None


def meters_for_account(bill_ref):
    """Return the active Water Meters whose Calin customer ID is the paybill account
    number, ignoring case and spaces ("upande 1" finds "Upande1")."""
    ref = (bill_ref or "").replace(" ", "")
    if not ref:
        return []

    return frappe.db.sql(
        """SELECT name FROM `tabWater Meter`
        WHERE REPLACE(calin_customer_id, ' ', '') = %s AND status != 'Inactive'""",
        (ref,),
        pluck=True,
    )


def _find_meter(bill_ref):
    """Return the one Water Meter the paybill account number points to, or None."""
    if not (bill_ref or "").replace(" ", ""):
        return None

    meters = meters_for_account(bill_ref)
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
    # Calin's closing balance is the debt left on the meter after this sale
    msg = (
        f"Token: {token_record.token or 'none'}\n"
        f"Customer: {token_record.customer_name or c2b.customer}\n"
        f"Amount paid: {_amount(c2b.transamount)}\n"
        f"Units: {_amount(token_record.total_unit)}\n"
        f"Outstanding debt: {_amount(token_record.closing_balance)}"
    )
    if _sms_payer(c2b, msg):
        return

    phone = _customer_phone(c2b, token_record.customer_id, settings, headers)
    if not phone:
        # Only worth chasing when there is a token the customer needs to enter
        if token_record.token:
            frappe.log_error(
                f"No phone for Calin customer {token_record.customer_id}; token {token_record.token} "
                f"(Token Record {token_record.name}) must be given to the customer another way",
                SMS_ERROR_TITLE,
            )
        return

    send_sms([phone], msg, success_msg=False)


def _amount(value):
    """100 rather than 100.0, but 0.1 and 12.5 as they are."""
    return f"{flt(value):,.2f}".rstrip("0").rstrip(".")


def _send_charge_only_sms(c2b, meter_id, settings, headers):
    still_owed = outstanding_service_charge(c2b.customer, settings.service_charge_item)
    owed_note = f"KES {still_owed} is still owed. " if still_owed > 0 else ""
    msg = (
        f"Hydrax Water: KES {c2b.transamount} received for meter {meter_id} and applied to your monthly "
        f"service charge, so no water was bought this time. {owed_note}M-Pesa ref {c2b.transid}."
    )
    if _sms_payer(c2b, msg):
        return

    calin_customer_id = frappe.db.get_value("Water Meter", meter_id, "calin_customer_id")
    phone = _customer_phone(c2b, calin_customer_id, settings, headers)
    if not phone:
        return

    send_sms([phone], msg, success_msg=False)


def _sms_payer(c2b, msg):
    """SMS whoever paid, so the token reaches the payer even when they aren't the
    meter's registered customer. M-Pesa only gives us a hash of the payer's
    number: Africa's Talking can text the hash directly, which reaches any payer;
    if that fails, text a saved number whose hash matches. Returns False when
    neither works, so the caller can fall back to the customer's number on file."""
    msisdn = (c2b.msisdn or "").strip().lower()
    if not HASHED_MSISDN.match(msisdn):
        return False

    if _sms_hashed_number(c2b, msisdn, msg):
        return True

    known = _number_for_hash(msisdn)
    if known:
        send_sms([known], msg, success_msg=False)
        return True

    return False


def _number_for_hash(msisdn_hash):
    """The saved phone number whose hash is the one M-Pesa sent, or None.
    Safaricom hashes the number as 2547XXXXXXXX (SHA-256, no + or leading 0), so
    every number on a Contact or Customer is put in that form before hashing.
    Hashing them all per payment is cheap and always reflects current Contacts."""
    numbers = frappe.db.sql(
        """SELECT phone FROM `tabContact Phone` WHERE IFNULL(phone, '') != ''
        UNION SELECT mobile_no FROM `tabContact` WHERE IFNULL(mobile_no, '') != ''
        UNION SELECT phone FROM `tabContact` WHERE IFNULL(phone, '') != ''
        UNION SELECT mobile_no FROM `tabCustomer` WHERE IFNULL(mobile_no, '') != ''""",
        pluck=True,
    )
    for number in numbers:
        kenyan = _kenyan_msisdn(number)
        if kenyan and hashlib.sha256(kenyan.encode()).hexdigest() == msisdn_hash:
            # Africa's Talking wants international format
            return f"+{kenyan}"
    return None


def _kenyan_msisdn(number):
    """0712345678, 712345678, +254712345678 and 254 712 345 678 all become
    254712345678; anything that isn't a Kenyan mobile number becomes None."""
    digits = re.sub(r"\D", "", number or "")
    if len(digits) == 12 and digits.startswith("254"):
        local = digits[3:]
    elif len(digits) == 10 and digits.startswith("0"):
        local = digits[1:]
    elif len(digits) == 9:
        local = digits
    else:
        return None
    return f"254{local}" if local[0] in "17" else None


def _sms_hashed_number(c2b, msisdn, msg):
    """Have Africa's Talking text the Safaricom hash itself. The plain messaging
    endpoint refuses a hash in "to" (403 InvalidPhoneNumber); hashes go to the
    bulk endpoint as maskedNumber with telco Safaricom, as in AT's own SDK
    (SMSService.send_hashed)."""
    gateway = frappe.get_single("SMS Settings")
    params = {p.parameter: p.value for p in gateway.parameters if not p.header}
    api_key = next((p.value for p in gateway.parameters if p.header and p.parameter.lower() == "apikey"), None)
    if not gateway.sms_gateway_url or not api_key:
        return False

    # https://api.africastalking.com/version1/messaging -> .../messaging/bulk
    url = gateway.sms_gateway_url.rstrip("/")
    if not url.endswith("/bulk"):
        url += "/bulk"

    body = {
        "username": params.get("username"),
        "maskedNumber": msisdn,
        "telco": "Safaricom",
        "message": msg,
        "phoneNumbers": [],
    }
    if params.get("from"):
        body["senderId"] = params["from"]

    try:
        response = requests.post(
            url,
            json=body,
            headers={"apiKey": api_key, "Accept": "application/json"},
            timeout=30,
        )
        reply = response.json()
        recipients = reply["SMSMessageData"]["Recipients"]
    except Exception:
        frappe.log_error(
            f"C2B {c2b.name}: SMS to the payer's hashed number failed; falling back to the customer's "
            f"number\n{frappe.get_traceback()}",
            SMS_ERROR_TITLE,
        )
        return False

    # Africa's Talking answers 201 even when every recipient was refused, so the
    # per-recipient status is what says whether it went
    if not any(r.get("statusCode") in AT_ACCEPTED for r in recipients):
        frappe.log_error(
            f"C2B {c2b.name}: the SMS gateway refused the payer's hashed number; trying saved numbers, "
            f"then the customer's. Reply: {reply}",
            SMS_ERROR_TITLE,
        )
        return False

    frappe.get_doc({
        "doctype": "SMS Log",
        "sent_on": nowdate(),
        "message": msg,
        "no_of_requested_sms": 1,
        "requested_numbers": msisdn,
        "no_of_sent_sms": 1,
        "sent_to": msisdn,
    }).insert(ignore_permissions=True)
    return True


def _customer_phone(c2b, calin_customer_id, settings, headers):
    """Fallback for when the payer's number isn't known: the phone on
    one of the Customer's Contacts, then the Customer itself, falling back to the one held in
    Calin. The Contact comes first because the Customer's mobile_no is only a copy
    taken when the primary contact was picked, and goes stale when the Contact is
    edited."""
    if c2b.customer:
        phone = _contact_phone(c2b.customer) or frappe.db.get_value("Customer", c2b.customer, "mobile_no")
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


def _contact_phone(customer):
    """Mobile (or else phone) of a Contact linked to the Customer, the primary
    contact first, then the most recently changed."""
    numbers = frappe.db.sql(
        """SELECT COALESCE(NULLIF(c.mobile_no, ''), c.phone)
        FROM `tabDynamic Link` dl
        JOIN `tabContact` c ON c.name = dl.parent
        WHERE dl.parenttype = 'Contact' AND dl.link_doctype = 'Customer' AND dl.link_name = %s
            AND (c.mobile_no != '' OR c.phone != '')
        ORDER BY c.is_primary_contact DESC, c.modified DESC
        LIMIT 1""",
        (customer,),
        pluck=True,
    )
    return numbers[0] if numbers else None

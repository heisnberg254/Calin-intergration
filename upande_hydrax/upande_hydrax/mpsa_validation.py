import json

import frappe
from frappe.utils import flt
from werkzeug.wrappers import Response

from upande_hydrax.upande_hydrax.vending import meters_for_account

HYDRAX_SHORTCODE = "4166061"
REJECTED_TITLE = "C2B Validation rejected"
ERROR_TITLE = "C2B Validation error"


@frappe.whitelist(allow_guest=True, methods=["POST"])
def validation(**kwargs) -> Response:
    """Replaces frappe_mpsa_payments' C2B validation URL (see override_whitelisted_methods).

    Safaricom asks this before completing a paybill payment; rejecting it stops the
    customer paying to an account number we can't turn into a token. Any bug here
    accepts, so it can never block payments."""
    try:
        payload = dict(frappe.form_dict)
        payload.pop("cmd", None)

        if str(payload.get("BusinessShortCode") or "").strip() != HYDRAX_SHORTCODE:
            return _reply("0", "Accepted")

        account = str(payload.get("BillRefNumber") or "").strip()
        if not account:
            return _reject("C2B00012", "No account number", payload)
        if not meters_for_account(account):
            return _reject("C2B00012", f"No Water Meter has Calin customer ID {account!r}", payload)
        if flt(payload.get("TransAmount")) <= 0:
            return _reject("C2B00013", f"Invalid amount {payload.get('TransAmount')!r}", payload)

        return _reply("0", "Accepted")
    except Exception:
        frappe.log_error(f"Accepted after an error\n\n{frappe.get_traceback()}", ERROR_TITLE)
        return _reply("0", "Accepted")


def _reject(code, reason, payload):
    frappe.log_error(f"{reason}\n\n{json.dumps(payload, indent=2, default=str)}", REJECTED_TITLE)
    return _reply(code, "Rejected")


def _reply(code, desc):
    # A Response skips Frappe's {"message": ...} wrapper; Safaricom wants top-level keys
    return Response(json.dumps({"ResultCode": code, "ResultDesc": desc}), mimetype="application/json")

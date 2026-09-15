import frappe
import requests


def _fetch_all_pages(url, headers, base_body, log_title, page_size=500):
    """POST to a Calin `/read` endpoint, following pageNumber until every row
    reported in result.total has been collected. Returns None (after logging
    and notifying) if the API reports a non-zero code on any page."""
    rows = []
    page_number = 1

    while True:
        body = {**base_body, "pageNumber": page_number, "pageSize": page_size}
        response = requests.post(url, json=body, headers=headers, timeout=30)
        payload = response.json()

        if payload.get("code") != 0:
            frappe.log_error(payload, log_title)
            frappe.msgprint(f"Sync failed: {payload.get('reason')}")
            return None

        page_rows = payload["result"]["data"]
        rows.extend(page_rows)

        total = payload["result"].get("total") or 0
        if not page_rows or len(rows) >= total:
            break
        page_number += 1

    return rows


@frappe.whitelist()
def sync_all_dcus():
    settings = frappe.get_single("URL Setup Settings")
    headers = {"Authorization": f"Bearer {settings.get_password('api_token')}"}

    loc_url = f"{settings.base_url}/api/concentrator/read"
    loc_rows = _fetch_all_pages(loc_url, headers, {
        "concentratorId": None, "name": None, "lat": None, "lng": None, "remark": None,
        "createDateRange": None, "updateDateRange": None, "orderBy": "concentratorId asc",
        "searchTerm": None, "Company": settings.company
    }, "DCU Location Fetch Failed")
    if loc_rows is None:
        return

    locations = {}
    for row in loc_rows:
        locations[row["concentratorId"]] = {
            "dcu_name": row.get("name"),
            "latitude": row.get("lat"),
            "longitude": row.get("lng")
        }

    status_url = f"{settings.base_url}/api/concentratorOnlineStatus/read"
    status_rows = _fetch_all_pages(status_url, headers, {
        "lang": "en", "concentratorId": None, "status": None, "remark": None,
        "orderBy": "concentratorId asc", "searchTerm": None, "Company": settings.company
    }, "DCU Status Fetch Failed")
    if status_rows is None:
        return

    statuses = {}
    for row in status_rows:
        statuses[row["concentratorId"]] = {
            "status": "Online" if row.get("status") else "Offline",
            "last_seen": frappe.utils.get_datetime(row["statusUpdateDate"]) if row.get("statusUpdateDate") else None
        }

    all_ids = set(locations.keys()) | set(statuses.keys())
    created, updated = 0, 0

    for dcu_id in all_ids:
        loc = locations.get(dcu_id, {})
        stat = statuses.get(dcu_id, {})
        has_location = loc.get("latitude") and loc.get("longitude")
        exists = frappe.db.exists("DCU", dcu_id)

        if not exists:
            doc = frappe.get_doc({
                "doctype": "DCU",
                "dcu_id": dcu_id,
                "dcu_name": loc.get("dcu_name") or dcu_id,
                "latitude": loc.get("latitude"),
                "longitude": loc.get("longitude"),
                "status": stat.get("status") or "Offline",
                "last_seen": stat.get("last_seen")
            })
            doc.insert(ignore_permissions=True)
            created += 1
        else:
            if has_location:
                doc = frappe.get_doc("DCU", dcu_id)
                doc.dcu_name = loc.get("dcu_name") or doc.dcu_name
                doc.latitude = loc.get("latitude")
                doc.longitude = loc.get("longitude")
                if stat:
                    doc.status = stat.get("status")
                    doc.last_seen = stat.get("last_seen")
                doc.save(ignore_permissions=True)
            elif stat:
                frappe.db.set_value("DCU", dcu_id, {
                    "status": stat.get("status"),
                    "last_seen": stat.get("last_seen")
                })
            updated += 1

    frappe.db.commit()
    frappe.msgprint(f"DCU sync complete: {created} created, {updated} updated")


@frappe.whitelist()
def sync_all_water_meters():
    settings = frappe.get_single("URL Setup Settings")
    headers = {"Authorization": f"Bearer {settings.get_password('api_token')}"}

    url = f"{settings.base_url}/api/account/read"
    rows = _fetch_all_pages(url, headers, {
        "customerId": None, "meterId": None, "tariffId": None, "remark": None,
        "createDateRange": None, "updateDateRange": None, "orderBy": "customerId asc",
        "searchTerm": None, "Company": settings.company
    }, "Water Meter Sync Failed")
    if rows is None:
        return

    created, updated = 0, 0

    for row in rows:
        meter_id = row.get("meterId")
        if not meter_id:
            continue

        concentrator_id = row.get("concentratorId")
        dcu_link = concentrator_id if concentrator_id and frappe.db.exists("DCU", concentrator_id) else None

        updated_date = frappe.utils.get_datetime(row["updateDate"]) if row.get("updateDate") else None
        created_date = frappe.utils.get_datetime(row["createDate"]) if row.get("createDate") else None

        fields = {
            "calin_customer_id": row.get("customerId"),
            "customer_name": row.get("customerName"),
            "tariff_id": row.get("tariffId"),
            "meter_type": row.get("meterType"),
            "protocol_version": row.get("protocolVersion"),
            "site": row.get("site"),
            "remark": row.get("remark"),
            "updated_date": updated_date,
            "created_date": created_date,
            "dcu": dcu_link
        }

        if not frappe.db.exists("Water Meter", meter_id):
            fields["doctype"] = "Water Meter"
            fields["meter_id"] = meter_id
            doc = frappe.get_doc(fields)
            doc.insert(ignore_permissions=True)
            created += 1
        else:
            frappe.db.set_value("Water Meter", meter_id, fields)
            updated += 1

    frappe.db.commit()
    frappe.msgprint(f"Water Meter sync complete: {created} created, {updated} updated")


@frappe.whitelist()
def sync_all_meter_readings():
    settings = frappe.get_single("URL Setup Settings")
    headers = {"Authorization": f"Bearer {settings.get_password('api_token')}"}

    url = f"{settings.base_url}/api/dailydatawater/read"
    rows = _fetch_all_pages(url, headers, {
        "lang": "en", "meterId": None, "remark": None, "createDateRange": None,
        "updateDateRange": None, "orderBy": None, "searchTerm": None,
        "Company": settings.company
    }, "Meter Reading Sync Failed")
    if rows is None:
        return

    created, updated, skipped = 0, 0, 0

    for row in rows:
        meter_id = row.get("meterId")
        if not meter_id:
            skipped += 1
            continue

        if not frappe.db.exists("Water Meter", meter_id):
            skipped += 1
            continue

        reading_date = frappe.utils.get_datetime(row["currentDate"]) if row.get("currentDate") else None
        updated_date = frappe.utils.get_datetime(row["updateDate"]) if row.get("updateDate") else None

        fields = {
            "customer_name": row.get("customerName"),
            "cumulative_reading": row.get("total"),
            "recharge_balance": row.get("currentRechargeBalance"),
            "total_recharge_balance": row.get("totalRechargeBalance"),
            "concentrator_id": row.get("concentratorId"),
            "remark": row.get("remark"),
            "valve_status": 1 if row.get("valveStatus") else 0,
            "magnetic_interference": 1 if row.get("magneticInterference") else 0,
            "battery_status": 1 if row.get("batteryStatus") else 0,
            "updated_date": updated_date
        }

        existing = frappe.db.exists("Meter Reading", {"meter": meter_id, "reading_date": reading_date})

        if not existing:
            fields["doctype"] = "Meter Reading"
            fields["meter"] = meter_id
            fields["reading_date"] = reading_date
            doc = frappe.get_doc(fields)
            doc.insert(ignore_permissions=True)
            created += 1
        else:
            frappe.db.set_value("Meter Reading", existing, fields)
            updated += 1

    frappe.db.commit()

    # Water Meter's "Last Synced" should reflect the newest reading we actually
    # hold for that meter, not just that its account record was touched - that's
    # what lets a stale value flag a meter as no longer reporting.
    latest_readings = frappe.db.sql("""
        SELECT meter, MAX(reading_date) AS last_reading
        FROM `tabMeter Reading`
        GROUP BY meter
    """, as_dict=True)
    for row in latest_readings:
        frappe.db.set_value("Water Meter", row.meter, "datetime_zrga", row.last_reading, update_modified=False)

    frappe.db.commit()
    frappe.msgprint(f"Meter Reading sync complete: {created} created, {updated} updated, {skipped} skipped")


@frappe.whitelist()
def sync_all_token_records():
    settings = frappe.get_single("URL Setup Settings")
    headers = {"Authorization": f"Bearer {settings.get_password('api_token')}"}

    url = f"{settings.base_url}/api/token/creditWaterTokenRecord/read"
    rows = _fetch_all_pages(url, headers, {
        "receiptId": None, "status": True, "customerId": None, "customerName": None,
        "meterId": None, "meterType": None, "tariffId": None, "remark": None, "token": None,
        "createDateRange": None, "updateDateRange": None, "orderBy": "receiptId desc",
        "searchTerm": None, "Company": settings.company
    }, "Token Record Sync Failed")
    if rows is None:
        return

    created, updated, skipped = 0, 0, 0

    for row in rows:
        receipt_id = str(row.get("receiptId"))
        meter_id = row.get("meterId")

        if not receipt_id or not meter_id:
            skipped += 1
            continue

        if not frappe.db.exists("Water Meter", meter_id):
            skipped += 1
            continue

        created_date = frappe.utils.get_datetime(row["createDate"]) if row.get("createDate") else None
        update_date = frappe.utils.get_datetime(row["updateDate"]) if row.get("updateDate") else None

        fields = {
            "customer_id": row.get("customerId"),
            "customer_name": row.get("customerName"),
            "tariff_id": row.get("tariffId"),
            "amount_paid": row.get("totalPaid"),
            "token": row.get("token"),
            "token_first": row.get("tokenFirst"),
            "token_second": row.get("tokenSecond"),
            "total_unit": row.get("totalUnit"),
            "repayment_amount": row.get("repaymentAmount"),
            "debt_remaining": row.get("debtRemaining"),
            "closing_balance": row.get("closingBalance"),
            "remark": row.get("remark"),
            "created_date": created_date,
            "updated_dat": update_date
        }

        if not frappe.db.exists("Token Record", receipt_id):
            fields["doctype"] = "Token Record"
            fields["receipt_id"] = receipt_id
            fields["meter"] = meter_id
            doc = frappe.get_doc(fields)
            doc.insert(ignore_permissions=True)
            created += 1
        else:
            skipped += 1
            continue

    frappe.db.commit()
    frappe.msgprint(f"Token Record sync complete: {created} created, {updated} updated, {skipped} skipped")

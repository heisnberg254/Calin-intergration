import frappe


@frappe.whitelist()
def get_dashboard_summary():
    total_dcu = frappe.db.count("DCU")
    online_dcu = frappe.db.count("DCU", {"status": "Online"})
    offline_dcu = total_dcu - online_dcu
    total_meters = frappe.db.count("Water Meter")
    faulty_meters = frappe.db.count("Water Meter", {"status": "Faulty"})

    today = frappe.utils.nowdate()
    yesterday = frappe.utils.add_days(today, -1)
    month_start = frappe.utils.get_first_day(today)

    active_meters = frappe.db.sql("""
        SELECT COUNT(DISTINCT meter) FROM `tabMeter Reading`
        WHERE DATE(reading_date) >= %s
    """, (yesterday,))[0][0] or 0

    total_consumption_today = frappe.db.sql("""
        SELECT SUM(curr.cumulative_reading - prev.cumulative_reading)
        FROM `tabMeter Reading` curr
        LEFT JOIN `tabMeter Reading` prev
            ON prev.meter = curr.meter
            AND prev.reading_date = (
                SELECT MAX(r2.reading_date)
                FROM `tabMeter Reading` r2
                WHERE r2.meter = curr.meter
                AND r2.reading_date < curr.reading_date
            )
        WHERE DATE(curr.reading_date) = %s
            AND curr.cumulative_reading IS NOT NULL AND curr.cumulative_reading != -1
            AND prev.cumulative_reading IS NOT NULL AND prev.cumulative_reading != -1
    """, (today,))[0][0] or 0

    revenue_today = frappe.db.sql("""
        SELECT SUM(amount_paid) FROM `tabToken Record` WHERE DATE(created_date) = %s
    """, (today,))[0][0] or 0

    revenue_month = frappe.db.sql("""
        SELECT SUM(amount_paid) FROM `tabToken Record` WHERE DATE(created_date) >= %s
    """, (month_start,))[0][0] or 0

    return {
        "total_dcu": total_dcu,
        "online_dcu": online_dcu,
        "offline_dcu": offline_dcu,
        "total_meters": total_meters,
        "faulty_meters": faulty_meters,
        "active_meters": active_meters,
        "total_consumption_today": round(total_consumption_today, 1),
        "revenue_today": round(revenue_today, 2),
        "revenue_month": round(revenue_month, 2)
    }


@frappe.whitelist()
def get_map_points(site: str = None):
    dcus_raw = frappe.db.get_all(
        "DCU",
        fields=["dcu_id", "dcu_name", "latitude", "longitude", "status", "last_seen"],
        filters={"latitude": ["is", "set"], "longitude": ["is", "set"]}
    )
    dcus = [
        d for d in dcus_raw
        if str(d.get("latitude")).replace("°", "").strip() not in ("0", "0.0", "")
        and str(d.get("longitude")).replace("°", "").strip() not in ("0", "0.0", "")
    ]

    meter_filters = {"latitude": ["is", "set"], "longitude": ["is", "set"]}
    if site:
        meter_filters["site"] = site

    meters_raw = frappe.db.get_all(
        "Water Meter",
        fields=["meter_id", "latitude", "longitude", "house_number", "site", "status"],
        filters=meter_filters
    )
    meters = [
        m for m in meters_raw
        if m.get("latitude") not in (0, 0.0)
        and m.get("longitude") not in (0, 0.0)
    ]

    return {"dcus": dcus, "meters": meters}


@frappe.whitelist()
def get_site_list():
    return frappe.db.sql("""
        SELECT DISTINCT site FROM `tabWater Meter`
        WHERE site IS NOT NULL AND site != ''
        ORDER BY site ASC
    """, as_dict=True)


@frappe.whitelist()
def get_consumption_trend(days: int = 14):
    start_date = frappe.utils.add_days(frappe.utils.nowdate(), -(int(days) - 1))
    rows = frappe.db.sql("""
        SELECT DATE(curr.reading_date) AS day,
            SUM(curr.cumulative_reading - prev.cumulative_reading) AS consumption
        FROM `tabMeter Reading` curr
        LEFT JOIN `tabMeter Reading` prev
            ON prev.meter = curr.meter
            AND prev.reading_date = (
                SELECT MAX(r2.reading_date)
                FROM `tabMeter Reading` r2
                WHERE r2.meter = curr.meter
                AND r2.reading_date < curr.reading_date
            )
        WHERE DATE(curr.reading_date) >= %s
            AND curr.cumulative_reading IS NOT NULL AND curr.cumulative_reading != -1
            AND prev.cumulative_reading IS NOT NULL AND prev.cumulative_reading != -1
        GROUP BY DATE(curr.reading_date)
        ORDER BY day ASC
    """, (start_date,), as_dict=True)

    return {
        "labels": [str(row["day"]) for row in rows],
        "values": [round(row["consumption"] or 0, 1) for row in rows]
    }


@frappe.whitelist()
def get_revenue_trend(days: int = 14, token_type: str = None):
    start_date = frappe.utils.add_days(frappe.utils.nowdate(), -(int(days) - 1))
    conditions = "created_date IS NOT NULL AND DATE(created_date) >= %s"
    params = [start_date]
    if token_type:
        conditions += " AND type = %s"
        params.append(token_type)

    rows = frappe.db.sql(f"""
        SELECT DATE(created_date) AS day, SUM(amount_paid) AS revenue
        FROM `tabToken Record`
        WHERE {conditions}
        GROUP BY DATE(created_date)
        ORDER BY day ASC
    """, params, as_dict=True)

    return {
        "labels": [str(row["day"]) for row in rows],
        "values": [round(row["revenue"] or 0, 2) for row in rows]
    }


@frappe.whitelist()
def get_recent_token_records(limit: int = 10, token_type: str = None, search: str = None):
    filters = {"type": token_type} if token_type else {}
    or_filters = {}
    if search:
        like = f"%{search}%"
        or_filters = {
            "customer_name": ["like", like],
            "meter": ["like", like],
            "receipt_id": ["like", like]
        }
    return frappe.db.get_all(
        "Token Record",
        filters=filters,
        or_filters=or_filters,
        fields=["receipt_id", "customer_name", "meter", "amount_paid", "token", "type", "created_date"],
        order_by="created_date desc",
        limit_page_length=int(limit)
    )


@frappe.whitelist()
def assign_house_number(meter_id: str, house_number: str):
    house_number = (house_number or "").strip()
    if not house_number:
        frappe.throw("House number is required")

    meter = frappe.get_doc("Water Meter", meter_id)

    existing_house = frappe.db.exists("House", {"house_number": house_number})
    if existing_house and existing_house != meter.house_number:
        frappe.throw(f"House number '{house_number}' is already assigned to another house")

    if existing_house:
        house_name = existing_house
    else:
        house = frappe.get_doc({
            "doctype": "House",
            "house_number": house_number,
            "calin_customer_id": meter.calin_customer_id,
            "site": meter.site,
            "status": "Active"
        })
        house.insert()
        house_name = house.name

    meter.house_number = house_name
    meter.save()

    return {"house": house_name}

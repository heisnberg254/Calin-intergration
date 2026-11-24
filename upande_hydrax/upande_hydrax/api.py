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

    # Estimated from tokens (see consumption.py); the meters send no readings
    total_consumption_today = frappe.db.sql("""
        SELECT SUM(daily_consumption) FROM `tabDaily Water Consumption` WHERE date = %s
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
    # Estimated from tokens (see consumption.py); the meters send no readings
    rows = frappe.db.sql("""
        SELECT date AS day, SUM(daily_consumption) AS consumption
        FROM `tabDaily Water Consumption`
        WHERE date >= %s AND date <= %s
        GROUP BY date
        ORDER BY day ASC
    """, (start_date, frappe.utils.nowdate()), as_dict=True)

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
            "house": ["like", like],
            "meter": ["like", like],
            "receipt_id": ["like", like]
        }
    return frappe.db.get_all(
        "Token Record",
        filters=filters,
        or_filters=or_filters,
        fields=["receipt_id", "customer_name", "house", "meter", "amount_paid", "token", "type", "created_date"],
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


@frappe.whitelist()
def get_bought_vs_used(days: int = 30, site: str = None, house: str = None):
    """Water bought (m3 loaded by tokens, on the day of purchase) against water
    used (the daily estimate in Daily Water Consumption), per day and per house."""
    days = int(days)
    end_date = frappe.utils.nowdate()
    start_date = frappe.utils.add_days(end_date, -(days - 1))

    token_cond, use_cond = "", ""
    params = {"start": start_date, "end": end_date, "site": site, "house": house}
    if site:
        token_cond += " AND wm.site = %(site)s"
        use_cond += " AND site = %(site)s"
    if house:
        token_cond += " AND tr.house = %(house)s"
        use_cond += " AND house = %(house)s"

    bought_by_day = {
        str(r.day): r.m3 or 0
        for r in frappe.db.sql(f"""
            SELECT DATE(tr.created_date) AS day, SUM(tr.total_unit) AS m3
            FROM `tabToken Record` tr
            LEFT JOIN `tabWater Meter` wm ON wm.name = tr.meter
            WHERE tr.is_preview = 0 AND DATE(tr.created_date) BETWEEN %(start)s AND %(end)s {token_cond}
            GROUP BY DATE(tr.created_date)
        """, params, as_dict=True)
    }
    used_by_day = {
        str(r.day): r.m3 or 0
        for r in frappe.db.sql(f"""
            SELECT date AS day, SUM(units_m3) AS m3
            FROM `tabDaily Water Consumption`
            WHERE date BETWEEN %(start)s AND %(end)s {use_cond}
            GROUP BY date
        """, params, as_dict=True)
    }
    labels = [str(frappe.utils.add_days(start_date, i)) for i in range(days)]

    bought_by_house = {
        r.house: r
        for r in frappe.db.sql(f"""
            SELECT IFNULL(tr.house, '') AS house, SUM(tr.total_unit) AS m3,
                SUM(tr.amount_paid) AS paid, COUNT(*) AS tokens, MAX(tr.created_date) AS last_token
            FROM `tabToken Record` tr
            LEFT JOIN `tabWater Meter` wm ON wm.name = tr.meter
            WHERE tr.is_preview = 0 AND DATE(tr.created_date) BETWEEN %(start)s AND %(end)s {token_cond}
            GROUP BY IFNULL(tr.house, '')
        """, params, as_dict=True)
    }
    used_by_house = {
        r.house: r.m3 or 0
        for r in frappe.db.sql(f"""
            SELECT IFNULL(house, '') AS house, SUM(units_m3) AS m3
            FROM `tabDaily Water Consumption`
            WHERE date BETWEEN %(start)s AND %(end)s {use_cond}
            GROUP BY IFNULL(house, '')
        """, params, as_dict=True)
    }
    houses = []
    for name in set(bought_by_house) | set(used_by_house):
        b = bought_by_house.get(name) or frappe._dict()
        houses.append({
            "house": name or None,
            "bought": round(b.m3 or 0, 3),
            "used": round(used_by_house.get(name, 0), 3),
            "paid": round(b.paid or 0, 2),
            "tokens": b.tokens or 0,
            "last_token": b.last_token,
        })
    houses.sort(key=lambda h: (h["used"], h["bought"]), reverse=True)

    return {
        "labels": labels,
        "bought": [round(bought_by_day.get(d, 0), 3) for d in labels],
        "used": [round(used_by_day.get(d, 0), 3) for d in labels],
        "houses": houses,
    }

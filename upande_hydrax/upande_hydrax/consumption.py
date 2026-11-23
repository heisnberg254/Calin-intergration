"""Estimate each meter's daily water use from the tokens it bought.

The meters send Calin no readings (they come back as -1), so tokens are the only
record of water. A token's total_unit is the whole m3 Calin loaded after applying
the tariff; change is kept as credit for the next token. Each day's purchase is
spread evenly over the days until the meter's next purchase. The latest one is
spread over the meter's usual gap and is corrected once the next token arrives,
so the last few days are provisional."""

from collections import defaultdict
from datetime import timedelta
from statistics import median

import frappe
from frappe.utils import add_days, getdate, now, nowdate

DOCTYPE = "Daily Water Consumption"
LITRES_PER_M3 = 1000
# Recomputed every run, because a new token changes how the previous one spreads
RECOMPUTE_DAYS = 30
# A meter with no gap of its own yet; the median across all meters is 5 days
DEFAULT_GAP_DAYS = 5
# A longer gap means the house stood empty, not that it used water slowly
MAX_SPREAD_DAYS = 30
# Purchases this far before the window still spread into it, and give each
# meter enough history to know its usual gap
LOOKBACK_DAYS = 120


def rebuild_recent():
    """Scheduler job: rebuild the last RECOMPUTE_DAYS days."""
    rebuild(add_days(nowdate(), -RECOMPUTE_DAYS))


def rebuild(start_date, end_date=None):
    """Replace the Daily Water Consumption rows from start_date to end_date
    (default today) with estimates from Token Records."""
    start = getdate(start_date)
    end = getdate(end_date or nowdate())

    purchases = defaultdict(list)
    for row in frappe.db.sql(
        """SELECT meter, DATE(created_date) AS day, SUM(total_unit) AS m3
        FROM `tabToken Record`
        WHERE meter IS NOT NULL AND total_unit > 0 AND created_date >= %s AND DATE(created_date) <= %s
        GROUP BY meter, DATE(created_date)
        ORDER BY meter, day""",
        (start - timedelta(days=LOOKBACK_DAYS), end),
        as_dict=True,
    ):
        purchases[row.meter].append((getdate(row.day), float(row.m3)))

    meters = {
        m.name: m
        for m in frappe.get_all("Water Meter", fields=["name", "house_number", "site"])
    }

    daily = defaultdict(float)  # (meter, day) -> m3
    for meter, buys in purchases.items():
        for (day, m3), days in zip(buys, _spread_days(buys)):
            per_day = m3 / days
            for offset in range(days):
                d = day + timedelta(days=offset)
                if start <= d <= end:
                    daily[(meter, d)] += per_day

    frappe.db.delete(DOCTYPE, {"date": ["between", [start, end]]})

    stamp, user = now(), frappe.session.user or "Administrator"
    values = []
    for (meter, d), m3 in sorted(daily.items()):
        info = meters.get(meter) or frappe._dict()
        values.append((
            frappe.generate_hash(length=12), stamp, stamp, user, user,
            d, meter, info.house_number, info.site,
            round(m3, 3), round(m3 * LITRES_PER_M3, 1),
        ))

    frappe.db.bulk_insert(
        DOCTYPE,
        fields=[
            "name", "creation", "modified", "owner", "modified_by",
            "date", "meter_id", "house", "site", "units_m3", "daily_consumption",
        ],
        values=values,
        chunk_size=5000,
    )
    frappe.db.commit()
    return len(values)


def _spread_days(buys):
    """How many days each purchase lasts: until the next purchase, or the
    meter's usual gap for the latest one, capped at MAX_SPREAD_DAYS."""
    gaps = [(b[0] - a[0]).days for a, b in zip(buys, buys[1:])]
    usual = round(median(gaps)) if gaps else DEFAULT_GAP_DAYS
    return [
        max(1, min(gap, MAX_SPREAD_DAYS))
        for gap in gaps + [usual]
    ]

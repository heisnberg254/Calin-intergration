# Copyright (c) 2026, edwin@upande.com and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class DailyWaterConsumption(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		daily_consumption: DF.Float
		date: DF.Date
		house: DF.Link | None
		meter_id: DF.Link | None
		site: DF.Data | None
		units_m3: DF.Float
	# end: auto-generated types

	_DOCTYPE_NAME = "Daily Water Consumption"

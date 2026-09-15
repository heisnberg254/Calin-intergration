# Copyright (c) 2026, edwin@upande.com and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class WaterMeter(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		calin_customer_id: DF.Data | None
		cumulative_reading: DF.Float
		customer_name: DF.Data | None
		datetime_zrga: DF.Datetime | None
		dcu: DF.Link | None
		geolocation_uhoo: DF.Geolocation | None
		house_number: DF.Link | None
		latitude: DF.Float
		longitude: DF.Float
		meter_id: DF.Data | None
		meter_type: DF.Data | None
		protocol_version: DF.Data | None
		site: DF.Data | None
		status: DF.Literal["Active", "Inactive", "Faulty"]
		tariff_id: DF.Data | None
		token_balance: DF.Float
	# end: auto-generated types

	_DOCTYPE_NAME = "Water Meter ID"

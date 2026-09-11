# Copyright (c) 2026, edwin@upande.com and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MpesaPayment(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		bill_ref_number: DF.Data | None
		business_short_code: DF.Data | None
		first_name: DF.Data | None
		house: DF.Link | None
		invoice_number: DF.Data | None
		last_name: DF.Data | None
		middle_name: DF.Data | None
		org_account_balance: DF.Currency
		phone_number: DF.Data | None
		remarks: DF.SmallText | None
		status: DF.Literal["Pending", "Matched", "Unmatched", "Credited", "Failed"]
		third_party_transaction_id: DF.Data | None
		token_record: DF.Link | None
		transaction_amount: DF.Currency
		transaction_id: DF.Data | None
		transaction_time: DF.Datetime | None
		transaction_type: DF.Data | None
		water_meter: DF.Link | None
	# end: auto-generated types

	def validate(self):
		self.match_house()

	def match_house(self):
		if self.house or not self.bill_ref_number:
			return

		house_name = frappe.db.exists("House", {"house_number": self.bill_ref_number.strip()})
		if not house_name:
			if self.status == "Pending":
				self.status = "Unmatched"
			return

		self.house = house_name
		self.water_meter = frappe.db.get_value("Water Meter", {"house_number": house_name}, "name")
		if self.status == "Pending":
			self.status = "Matched"

# Copyright (c) 2026, edwin@upande.com and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class URLSetupSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from upande_hydrax.upande_hydrax.doctype.service_charge_rate.service_charge_rate import ServiceChargeRate

		api_token: DF.Password | None
		base_url: DF.Data | None
		company: DF.Data | None
		service_charge_company: DF.Link | None
		service_charge_item: DF.Link | None
		service_charge_rates: DF.Table[ServiceChargeRate]
		sync_frequency: DF.Literal[None]
		vending_password: DF.Password | None
	# end: auto-generated types

	_DOCTYPE_NAME = "Calin Settings"

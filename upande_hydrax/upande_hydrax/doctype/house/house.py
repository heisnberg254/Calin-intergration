import json
from frappe.model.document import Document

class House(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        calin_customer_id: DF.Data | None
        customer: DF.Link | None
        geolocation_dvks: DF.Geolocation | None
        house_number: DF.Data | None
        latitude: DF.Data | None
        longitude: DF.Data | None
        site: DF.Data | None
        status: DF.Literal["Active", "Inactive", "Suspended"]
    # end: auto-generated types

    def validate(self):
        self.update_geolocation()

    def update_geolocation(self):
        if self.latitude and self.longitude:
            try:
                lat = float(str(self.latitude).replace("°", "").strip())
                lng = float(str(self.longitude).replace("°", "").strip())
            except (ValueError, TypeError):
                frappe.throw("Latitude and Longitude must be valid numbers")
                return

            self.geolocation_dvks = json.dumps({
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lng, lat]
                        }
                    }
                ]
            })
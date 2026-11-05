import erpnext

# HRMS already overrides Payment Entry, and Frappe only uses the override of the
# last app installed, so build on HRMS's class to keep its employee logic
try:
    from hrms.overrides.employee_payment_entry import EmployeePaymentEntry as BasePaymentEntry
except ImportError:
    from erpnext.accounts.doctype.payment_entry.payment_entry import PaymentEntry as BasePaymentEntry


class HydraxPaymentEntry(BasePaymentEntry):
    def set_amounts(self):
        """frappe_mpsa_payments builds its Payment Entry and calls set_amounts()
        before validate has set the exchange rates. Newer ERPNext divides by the
        rate inside set_amounts, so every M-Pesa payment failed with
        "unsupported operand type(s) for /: 'float' and 'NoneType'". Set the
        rates first, the same way validate would."""
        if not self.source_exchange_rate or not self.target_exchange_rate:
            if not self.company_currency:
                self.company_currency = erpnext.get_company_currency(self.company)
            self.set_exchange_rate()
        super().set_amounts()

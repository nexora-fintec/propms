import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, today

from propms.property_management_solution.billing_utils import (
	is_cheque_mode,
	settle_billing_with_invoice_and_payment,
)
from propms.api.pdc import create_pdc_from_billing


@frappe.whitelist()
def send_billing_entry(docname):
	doc = frappe.get_doc("Agreement Billing Entry", docname)
	if doc.status not in ["Pending", "Sent"]:
		frappe.throw("Only Pending or Sent entries can be re-sent")
	doc.status = "Sent"
	doc.save()
	frappe.db.commit()
	return {"status": "ok"}


@frappe.whitelist()
def pay_billing_entry(docname):
	doc = frappe.get_doc("Agreement Billing Entry", docname)
	if doc.status in ["Paid", "Cancelled"]:
		frappe.throw("This entry cannot be paid")
	doc.status = "Paid"
	doc.save()
	frappe.db.commit()
	return {"status": "ok"}


@frappe.whitelist()
def pay_billing_entry_with_invoice(billing_entry_name):
	"""Immediate payment (cash/bank). Cheque rent must use PDC flow."""
	billing = frappe.get_doc("Agreement Billing Entry", billing_entry_name)

	if billing.status == "Paid":
		frappe.throw("Billing Entry already paid.")

	if is_cheque_mode(billing.mode_of_payment):
		frappe.throw(
			_(
				"Cheque payments use the PDC flow. Click <b>Create PDC</b> to hold the cheque, "
				"then <b>Present Cheque</b> on the due date (or wait for auto-present)."
			)
		)

	if billing.post_dated_cheque:
		frappe.throw(
			_("This billing is linked to PDC {0}. Present the cheque from the PDC form.").format(
				billing.post_dated_cheque
			)
		)

	result = settle_billing_with_invoice_and_payment(billing)
	frappe.db.commit()
	return result


@frappe.whitelist()
def mark_cheque_bounced(billing_entry):
	"""Bounce handling for billing entries paid without PDC (legacy) or via PDC link."""
	be = frappe.get_doc("Agreement Billing Entry", billing_entry)

	if not is_cheque_mode(be.mode_of_payment):
		frappe.throw("Only Cheque payments allowed.")

	if be.post_dated_cheque:
		from propms.api.pdc import mark_pdc_bounced

		return mark_pdc_bounced(be.post_dated_cheque)

	if be.status != "Paid":
		frappe.throw("Only Paid entries can be bounced.")

	if not be.payment_entry:
		frappe.throw("No Payment Entry linked.")

	pe = frappe.get_doc("Payment Entry", be.payment_entry)
	if pe.docstatus == 1:
		pe.cancel()

	from propms.property_management_solution.billing_utils import mark_billing_overdue_after_bounce

	mark_billing_overdue_after_bounce(be, payment_entry=pe.name)
	frappe.db.commit()
	return "Cheque marked as Bounced and history recorded successfully."

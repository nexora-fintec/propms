import frappe
from frappe import _
from frappe.utils import today

from propms.property_management_solution.billing_utils import (
	append_agreement_cheque_history,
	create_payment_entry_for_billing,
	create_sales_invoice_for_billing,
	is_cheque_mode,
	mark_billing_overdue_after_bounce,
	mark_billing_paid,
	settle_billing_with_invoice_and_payment,
)
from propms.pdc.doctype.post_dated_cheque.post_dated_cheque import _append_pdc_history


@frappe.whitelist()
def present_pdc(pdc_name, posting_date=None):
	"""Present a held PDC: create Sales Invoice + Payment Entry when linked to billing."""
	pdc = frappe.get_doc("Post Dated Cheque", pdc_name)
	pdc.check_permission("write")

	if pdc.docstatus != 1:
		frappe.throw(_("Submit the PDC before presenting."))

	if pdc.status not in ("Held", "Presented"):
		frappe.throw(_("Only Held PDCs can be presented."))

	if pdc.payment_entry and pdc.status == "Cleared":
		frappe.throw(_("Payment Entry already exists for this PDC."))

	posting_date = posting_date or today()
	sales_invoice = pdc.sales_invoice
	payment_entry = None

	if pdc.agreement_billing_entry:
		billing = frappe.get_doc("Agreement Billing Entry", pdc.agreement_billing_entry)
		agreement = frappe.get_doc("Agreement", billing.agreement)

		sales_invoice = create_sales_invoice_for_billing(billing, agreement, posting_date)
		payment_entry = create_payment_entry_for_billing(
			billing, agreement, sales_invoice, posting_date
		)

		append_agreement_cheque_history(
			billing.agreement,
			billing,
			"Deposited",
			payment_entry=payment_entry,
			presenting_date=posting_date,
			remarks=_("PDC {0} presented").format(pdc.name),
		)
		mark_billing_paid(billing, sales_invoice, payment_entry)
	else:
		company = pdc.company
		party_account = frappe.db.get_value(
			"Party Account",
			{"parent": pdc.customer, "company": company},
			"account",
		) or frappe.get_cached_value("Company", company, "default_receivable_account")

		paid_to_account = frappe.db.get_value(
			"Mode of Payment Account",
			{"parent": pdc.mode_of_payment, "company": company},
			"default_account",
		)

		if not paid_to_account:
			frappe.throw(
				_("Default account not set for Mode of Payment {0}").format(pdc.mode_of_payment)
			)

		pe = frappe.new_doc("Payment Entry")
		pe.payment_type = "Receive"
		pe.company = company
		pe.party_type = "Customer"
		pe.party = pdc.customer
		pe.posting_date = posting_date
		pe.mode_of_payment = pdc.mode_of_payment
		pe.paid_from = party_account
		pe.paid_to = paid_to_account
		pe.paid_amount = pdc.amount
		pe.received_amount = pdc.amount
		pe.reference_no = pdc.cheque_no
		pe.reference_date = pdc.cheque_date
		pe.remarks = _("PDC {0} presented").format(pdc.name)

		if sales_invoice:
			pe.append(
				"references",
				{
					"reference_doctype": "Sales Invoice",
					"reference_name": sales_invoice,
					"allocated_amount": pdc.amount,
				},
			)

		pe.insert(ignore_permissions=True)
		pe.submit()
		payment_entry = pe.name

	pdc.db_set(
		{
			"status": "Cleared",
			"payment_entry": payment_entry,
			"sales_invoice": sales_invoice,
			"presenting_date": posting_date,
		}
	)
	_append_pdc_history(pdc, "Cleared", _("Cheque presented"), payment_entry)

	frappe.db.commit()
	return {
		"sales_invoice": sales_invoice,
		"payment_entry": payment_entry,
		"status": "Cleared",
	}


@frappe.whitelist()
def mark_pdc_bounced(pdc_name):
	"""Mark a cleared PDC as bounced and revert linked billing."""
	pdc = frappe.get_doc("Post Dated Cheque", pdc_name)
	pdc.check_permission("write")

	if pdc.status != "Cleared":
		frappe.throw(_("Only Cleared PDCs can be marked as bounced."))

	if not pdc.payment_entry:
		frappe.throw(_("No Payment Entry linked."))

	pe = frappe.get_doc("Payment Entry", pdc.payment_entry)
	if pe.docstatus == 1:
		pe.cancel()

	pdc.db_set({"status": "Bounced", "payment_entry": None, "sales_invoice": None})
	_append_pdc_history(pdc, "Bounced", _("Cheque bounced"), pe.name)

	if pdc.agreement_billing_entry:
		billing = frappe.get_doc("Agreement Billing Entry", pdc.agreement_billing_entry)
		mark_billing_overdue_after_bounce(billing, payment_entry=pe.name)

	frappe.db.commit()
	return _("Cheque marked as bounced.")


@frappe.whitelist()
def create_pdc_from_billing(billing_entry_name, auto=0):
	"""Create a held PDC from an Agreement Billing Entry (cheque payments)."""
	billing = frappe.get_doc("Agreement Billing Entry", billing_entry_name)

	if billing.post_dated_cheque:
		return {"pdc": billing.post_dated_cheque, "existing": 1}

	if billing.status in ("Paid", "Cancelled"):
		frappe.throw(_("Cannot create PDC for a {0} billing entry.").format(billing.status))

	if not is_cheque_mode(billing.mode_of_payment):
		frappe.throw(_("PDC can only be created for Cheque mode of payment."))

	if not billing.cheque_no or not billing.cheque_date:
		frappe.throw(_("Cheque No and Cheque Date are required on the billing entry."))

	agreement = frappe.get_doc("Agreement", billing.agreement)
	company = agreement.company or frappe.defaults.get_global_default("company")

	pdc = frappe.get_doc(
		{
			"doctype": "Post Dated Cheque",
			"company": company,
			"customer": billing.customer,
			"agreement": billing.agreement,
			"property": agreement.property,
			"mode_of_payment": billing.mode_of_payment or "Cheque",
			"receiving_date": today(),
			"cheque_no": billing.cheque_no,
			"cheque_date": billing.cheque_date,
			"presenting_date": billing.cheque_date,
			"amount": billing.amount,
			"agreement_billing_entry": billing.name,
			"remarks": _("Created from Agreement Billing Entry {0}").format(billing.name),
		}
	)
	pdc.insert(ignore_permissions=True)
	pdc.submit()

	append_agreement_cheque_history(
		billing.agreement,
		billing,
		"Held",
		remarks=_("PDC {0} received — held until {1}").format(pdc.name, billing.cheque_date),
	)

	frappe.db.set_value(
		"Agreement Billing Entry",
		billing.name,
		{"post_dated_cheque": pdc.name, "status": "Sent"},
	)

	frappe.db.commit()
	return {"pdc": pdc.name, "auto": bool(frappe.utils.cint(auto))}


@frappe.whitelist()
def create_pdcs_for_agreement(agreement):
	"""Create PDC for all cheque billing entries on an agreement that lack PDC."""
	created = []
	billings = frappe.get_all(
		"Agreement Billing Entry",
		filters={
			"agreement": agreement,
			"status": ["in", ["Pending", "Sent", "Overdue"]],
			"post_dated_cheque": ["is", "not set"],
		},
		pluck="name",
	)

	for name in billings:
		billing = frappe.get_doc("Agreement Billing Entry", name)
		if not is_cheque_mode(billing.mode_of_payment):
			continue
		if not billing.cheque_no or not billing.cheque_date:
			continue
		try:
			result = create_pdc_from_billing(name)
			if result.get("pdc"):
				created.append(result["pdc"])
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"PDC create failed for {name}")

	return {
		"created": created,
		"message": _("Created {0} PDC(s).").format(len(created)) if created else _("No cheque billings pending PDC."),
	}


def auto_create_pdc_for_billing(billing_entry_name):
	"""Called after billing generation when payment mode is Cheque."""
	try:
		billing = frappe.get_doc("Agreement Billing Entry", billing_entry_name)
		if not is_cheque_mode(billing.mode_of_payment):
			return None
		if not billing.cheque_no or not billing.cheque_date:
			return None
		if billing.post_dated_cheque:
			return billing.post_dated_cheque
		result = create_pdc_from_billing(billing_entry_name, auto=1)
		return result.get("pdc")
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Auto PDC failed for {billing_entry_name}")
		return None


def present_due_pdcs():
	"""Daily job: auto-present PDCs whose presenting date is today or earlier."""
	due_pdcs = frappe.get_all(
		"Post Dated Cheque",
		filters={
			"docstatus": 1,
			"status": "Held",
			"presenting_date": ["<=", today()],
		},
		pluck="name",
	)

	for name in due_pdcs:
		try:
			present_pdc(name)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"PDC auto-present failed: {name}")

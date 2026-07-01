import frappe
from frappe import _
from frappe.utils import flt, today


def is_cheque_mode(mode_of_payment):
	return (mode_of_payment or "").strip().lower() == "cheque"


def create_sales_invoice_for_billing(billing, agreement, posting_date=None):
	"""Create and submit Sales Invoice for an Agreement Billing Entry."""
	if billing.sales_invoice and frappe.db.exists("Sales Invoice", billing.sales_invoice):
		return billing.sales_invoice

	if not agreement.sales_order:
		frappe.throw(_("Sales Order not found for Agreement {0}.").format(agreement.name))

	posting_date = posting_date or today()
	si = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"customer": billing.customer,
			"posting_date": posting_date,
			"due_date": billing.due_date or posting_date,
			"items": [
				{
					"item_code": agreement.room,
					"qty": 1,
					"rate": billing.amount,
					"sales_order": agreement.sales_order,
				}
			],
			"agreement": agreement.name,
			"agreement_billing_entry": billing.name,
		}
	)
	si.insert(ignore_permissions=True)
	si.submit()
	return si.name


def create_payment_entry_for_billing(billing, agreement, sales_invoice, posting_date=None):
	"""Create and submit Payment Entry against billing / sales invoice."""
	posting_date = posting_date or today()
	company = agreement.company or frappe.defaults.get_global_default("company")

	party_account = frappe.db.get_value(
		"Party Account",
		{"parent": billing.customer, "company": company},
		"account",
	) or frappe.get_cached_value("Company", company, "default_receivable_account")

	paid_to_account = frappe.db.get_value(
		"Mode of Payment Account",
		{"parent": billing.mode_of_payment, "company": company},
		"default_account",
	)

	if not paid_to_account:
		frappe.throw(
			_("Default account not set for Mode of Payment {0}").format(billing.mode_of_payment)
		)

	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.company = company
	pe.party_type = "Customer"
	pe.party = billing.customer
	pe.posting_date = posting_date
	pe.mode_of_payment = billing.mode_of_payment
	pe.paid_from = party_account
	pe.paid_to = paid_to_account
	pe.paid_amount = flt(billing.amount)
	pe.received_amount = flt(billing.amount)

	if sales_invoice:
		pe.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": sales_invoice,
				"allocated_amount": flt(billing.amount),
			},
		)

	if is_cheque_mode(billing.mode_of_payment):
		pe.reference_no = billing.cheque_no
		pe.reference_date = billing.cheque_date

	pe.insert(ignore_permissions=True)
	pe.submit()
	return pe.name


def append_agreement_cheque_history(
	agreement_name,
	billing,
	status,
	payment_entry=None,
	presenting_date=None,
	remarks=None,
):
	"""Add a row to Agreement cheque history child table."""
	frappe.get_doc(
		{
			"doctype": "Agreement Cheque History",
			"parent": agreement_name,
			"parenttype": "Agreement",
			"parentfield": "cheque_history",
			"billing_entry": billing.name,
			"cheque_no": billing.cheque_no,
			"cheque_date": billing.cheque_date,
			"presenting_date": presenting_date or today(),
			"amount": billing.amount,
			"status": status,
			"payment_entry": payment_entry,
			"remarks": remarks or "",
		}
	).insert(ignore_permissions=True)


def mark_billing_paid(billing, sales_invoice, payment_entry):
	"""Update billing entry, payment schedule, and return names."""
	frappe.db.set_value(
		"Agreement Billing Entry",
		billing.name,
		{
			"status": "Paid",
			"sales_invoice": sales_invoice,
			"payment_entry": payment_entry,
		},
	)

	if billing.cheque_row_id:
		update_data = {"status": "Paid", "payment_entry": payment_entry}
		if is_cheque_mode(billing.mode_of_payment):
			update_data.update(
				{
					"cheque_no": billing.cheque_no,
					"cheque_date": billing.cheque_date,
				}
			)
		frappe.db.set_value("Agreement Payment Schedule", billing.cheque_row_id, update_data)


def mark_billing_overdue_after_bounce(billing, payment_entry=None):
	"""Revert billing / schedule after a bounced cheque."""
	frappe.db.set_value(
		"Agreement Billing Entry",
		billing.name,
		{"status": "Overdue", "payment_entry": None},
	)

	if billing.cheque_row_id:
		frappe.db.set_value(
			"Agreement Payment Schedule",
			billing.cheque_row_id,
			{"status": "Overdue", "payment_entry": None},
		)

	append_agreement_cheque_history(
		billing.agreement,
		billing,
		"Bounced",
		payment_entry=payment_entry,
		remarks=_("Cheque bounced"),
	)


def settle_billing_with_invoice_and_payment(billing, posting_date=None):
	"""Full immediate settlement: Sales Invoice + Payment Entry (non-PDC / cash)."""
	posting_date = posting_date or today()
	agreement = frappe.get_doc("Agreement", billing.agreement)

	if billing.status == "Paid":
		frappe.throw(_("Billing Entry already paid."))

	sales_invoice = create_sales_invoice_for_billing(billing, agreement, posting_date)
	payment_entry = create_payment_entry_for_billing(
		billing, agreement, sales_invoice, posting_date
	)

	if is_cheque_mode(billing.mode_of_payment):
		append_agreement_cheque_history(
			billing.agreement,
			billing,
			"Deposited",
			payment_entry=payment_entry,
			presenting_date=posting_date,
			remarks=_("Cheque presented and payment recorded"),
		)

	mark_billing_paid(billing, sales_invoice, payment_entry)

	return {"sales_invoice": sales_invoice, "payment_entry": payment_entry}

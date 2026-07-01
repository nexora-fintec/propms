"""Ensure workspace-linked doctypes/reports are readable by common roles."""

import frappe

WORKSPACE_ROLES = (
	"System Manager",
	"Property Manager",
	"Accounts Manager",
	"Accounts User",
)

WORKSPACE_DOCTYPES = (
	"Property",
	"Room",
	"Agreement",
	"Lease",
	"Agreement Billing Entry",
	"Post Dated Cheque",
	"Property Management Settings",
	"Furniture Master",
	"Feature Master",
	"Feature Category Master",
	"Issue",
	"Daily Checklist",
	"Meter Reading",
)

WORKSPACE_REPORTS = (
	"Debtors Report",
	"Security Deposit",
	"Rent Invoices Details",
	"PDC Due Report",
)


def after_migrate():
	ensure_workspace_permissions()


def ensure_workspace_permissions():
	for doctype in WORKSPACE_DOCTYPES:
		_add_read_permissions("DocType", doctype)

	for report in WORKSPACE_REPORTS:
		_add_report_roles(report)

	frappe.db.commit()


def _add_read_permissions(doctype, name):
	if not frappe.db.exists(doctype, name):
		return

	doc = frappe.get_doc(doctype, name)
	existing_roles = {row.role for row in doc.permissions}
	changed = False

	for role in WORKSPACE_ROLES:
		if role in existing_roles:
			continue
		doc.append(
			"permissions",
			{
				"role": role,
				"read": 1,
				"print": 1,
				"email": 1,
				"export": 1,
				"report": 1,
				"share": 1,
			},
		)
		changed = True

	if changed:
		doc.save(ignore_permissions=True)


def _add_report_roles(report_name):
	if not frappe.db.exists("Report", report_name):
		return

	doc = frappe.get_doc("Report", report_name)
	existing_roles = {row.role for row in doc.roles}
	changed = False

	for role in WORKSPACE_ROLES:
		if role in existing_roles:
			continue
		doc.append("roles", {"role": role})
		changed = True

	if changed:
		doc.save(ignore_permissions=True)

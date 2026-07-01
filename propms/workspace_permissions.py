"""Ensure workspace-linked doctypes/reports are readable by common roles.

Uses Custom DocPerm / Has Role inserts so migrate works on Frappe Cloud
(production sites without developer_mode).
"""

import frappe
from frappe.permissions import add_permission, update_permission_property

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

EXTRA_DOCTYPE_PERMS = ("print", "email", "export", "report", "share")


def after_migrate():
	ensure_workspace_permissions()


def ensure_workspace_permissions():
	for doctype in WORKSPACE_DOCTYPES:
		_add_doctype_read_permissions(doctype)

	for report in WORKSPACE_REPORTS:
		_add_report_role(report)

	frappe.db.commit()
	frappe.clear_cache()


def _role_has_doctype_read(doctype, role):
	if frappe.db.get_value("DocPerm", {"parent": doctype, "role": role, "permlevel": 0}, "read"):
		return True
	if frappe.db.get_value(
		"Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0}, "read"
	):
		return True
	return False


def _add_doctype_read_permissions(doctype):
	if not frappe.db.exists("DocType", doctype):
		return

	changed = False
	for role in WORKSPACE_ROLES:
		if _role_has_doctype_read(doctype, role):
			continue

		try:
			add_permission(doctype, role, 0, "read")
			for ptype in EXTRA_DOCTYPE_PERMS:
				update_permission_property(doctype, role, 0, ptype, 1, validate=False)
			changed = True
		except Exception:
			frappe.log_error(
				title=f"propms workspace permission failed: {doctype} / {role}",
				message=frappe.get_traceback(),
			)

	if changed:
		from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype

		validate_permissions_for_doctype(doctype)


def _report_has_role(report_name, role):
	return frappe.db.exists(
		"Has Role",
		{"parent": report_name, "parenttype": "Report", "role": role},
	)


def _add_report_role(report_name):
	if not frappe.db.exists("Report", report_name):
		return

	for role in WORKSPACE_ROLES:
		if _report_has_role(report_name, role):
			continue

		try:
			frappe.get_doc(
				{
					"doctype": "Has Role",
					"parent": report_name,
					"parenttype": "Report",
					"parentfield": "roles",
					"role": role,
				}
			).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(
				title=f"propms report role failed: {report_name} / {role}",
				message=frappe.get_traceback(),
			)

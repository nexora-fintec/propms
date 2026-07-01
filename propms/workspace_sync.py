"""Re-sync propms workspace layout from app JSON files."""

import json
import os

import frappe


def after_migrate():
	sync_propms_workspaces()


def sync_propms_workspaces():
	app_path = frappe.get_app_path("propms")
	workspace_files = (
		(
			"Property Management Solution",
			os.path.join(
				app_path,
				"property_management_solution",
				"workspace",
				"property_management_solution",
				"property_management_solution.json",
			),
		),
		(
			"PDC",
			os.path.join(app_path, "pdc", "workspace", "pdc", "pdc.json"),
		),
	)

	for workspace_name, json_path in workspace_files:
		if not os.path.exists(json_path):
			continue
		if not frappe.db.exists("Workspace", workspace_name):
			continue

		with open(json_path) as handle:
			data = json.load(handle)

		doc = frappe.get_doc("Workspace", workspace_name)
		doc.content = data.get("content") or doc.content
		doc.public = 1
		doc.is_hidden = 0
		doc.module = data.get("module") or doc.module
		doc.flags.ignore_links = True

		doc.set("links", [])
		doc.set("shortcuts", [])
		for row in data.get("links") or []:
			doc.append("links", row)
		for row in data.get("shortcuts") or []:
			doc.append("shortcuts", row)

		doc.save(ignore_permissions=True)

	frappe.db.commit()
	frappe.clear_cache()

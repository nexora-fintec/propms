frappe.query_reports["PDC Due Report"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nHeld\nPresented\nCleared\nBounced",
			default: "Held",
		},
		{
			fieldname: "from_date",
			label: __("Presenting From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("Presenting To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
	],
};

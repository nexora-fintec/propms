frappe.ui.form.on("Post Dated Cheque", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.docstatus === 1 && ["Held", "Presented"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Present Cheque"), () => {
				frappe.confirm(
					__("Create Sales Invoice, Payment Entry, and clear this cheque?"),
					() => {
						frappe.call({
							method: "propms.api.pdc.present_pdc",
							args: { pdc_name: frm.doc.name },
							freeze: true,
							freeze_message: __("Presenting cheque..."),
							callback(r) {
								if (!r.exc) {
									const msg = [
										r.message.sales_invoice
											? `${__("Sales Invoice")}: ${r.message.sales_invoice}`
											: null,
										r.message.payment_entry
											? `${__("Payment Entry")}: ${r.message.payment_entry}`
											: null,
									]
										.filter(Boolean)
										.join("<br>");
									frappe.msgprint({
										title: __("Cheque Presented"),
										indicator: "green",
										message: msg,
									});
									frm.reload_doc();
								}
							},
						});
					}
				);
			}, __("Actions"));
		}

		if (
			frm.doc.docstatus === 1 &&
			frm.doc.status === "Cleared" &&
			frm.doc.payment_entry
		) {
			frm.add_custom_button(__("Mark as Bounced"), () => {
				frappe.confirm(
					__("Cancel Payment Entry and mark cheque as bounced?"),
					() => {
						frappe.call({
							method: "propms.api.pdc.mark_pdc_bounced",
							args: { pdc_name: frm.doc.name },
							freeze: true,
							freeze_message: __("Processing bounce..."),
							callback(r) {
								if (!r.exc) {
									frappe.msgprint({
										title: __("Cheque Bounced"),
										indicator: "orange",
										message: r.message,
									});
									frm.reload_doc();
								}
							},
						});
					}
				);
			}, __("Actions"));
		}

		if (frm.doc.payment_entry) {
			frm.add_custom_button(__("Payment Entry"), () => {
				frappe.set_route("Form", "Payment Entry", frm.doc.payment_entry);
			}, __("View"));
		}
    if (frm.doc.sales_invoice) {
      frm.add_custom_button(__("Sales Invoice"), () => {
        frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice);
      }, __("View"));
    }
    if (frm.doc.agreement_billing_entry) {
      frm.add_custom_button(__("Billing Entry"), () => {
        frappe.set_route("Form", "Agreement Billing Entry", frm.doc.agreement_billing_entry);
      }, __("View"));
    }

    if (frm.doc.docstatus === 1 && frm.doc.status === "Held") {
      frm.set_intro(
        __(
          "Cheque is held. On presenting date, click <b>Present Cheque</b> to create Sales Invoice and Payment Entry."
        ),
        "blue"
      );
    }
  },

	agreement(frm) {
		if (!frm.doc.agreement) return;
		frappe.db.get_value("Agreement", frm.doc.agreement, ["lease_customer", "property"], (r) => {
			if (r?.lease_customer) frm.set_value("customer", r.lease_customer);
			if (r?.property) frm.set_value("property", r.property);
		});
	},

	cheque_date(frm) {
		if (frm.doc.cheque_date && !frm.doc.presenting_date) {
			frm.set_value("presenting_date", frm.doc.cheque_date);
		}
	},
});

// Copyright (c) 2018, Aakvatech and contributors
// For license information, please see license.txt
// cur_frm.add_fetch('property', 'unit_owner', 'property_owner');

// frappe.ui.form.on('Agreement', {
// 	setup: function (frm) {
// 		// frm.set_query("lease_item", "lease_item", function () {
// 		// 	return {
// 		// 		"filters": [
// 		// 			["item_group", "=", "Agreement Items"],
// 		// 		]
// 		// 	};
// 		// });
// 		frm.set_query("property", function () {
// 			return {
// 				"filters": {
// 					"company": frm.doc.company,
// 				},
// 			};
// 		});
// 	},
// 	refresh: function (frm) {
// 		cur_frm.add_custom_button(__("Make Invoice Schedule"), function () {
// 			make_lease_invoice_schedule(cur_frm);
// 		});
// 		cur_frm.add_custom_button(__("Generate Pending Invoice"), function () {
// 			generate_pending_invoice();
// 		});
// 		cur_frm.add_custom_button(__("Make Invoice Schedule for all Agreement"), function () {
// 			getAllAgreement(cur_frm);
// 		});
// 	},
// 	onload: function (frm) {
// 		frappe.realtime.on("lease_invoice_schedule_progress", function (data) {
// 			if (data.reload && data.reload === 1) {
// 				frm.reload_doc();
// 			}
// 			if (data.progress) {
// 				let progress_bar = $(cur_frm.dashboard.progress_area).find(".progress-bar");
// 				if (progress_bar) {
// 					$(progress_bar).removeClass("progress-bar-danger").addClass("progress-bar-success progress-bar-striped");
// 					$(progress_bar).css("width", data.progress + "%");
// 				}
// 			}
// 		});
// 	}
// });

// var make_lease_invoice_schedule = function (frm) {
// 	var doc = frm.doc;
// 	frappe.call({
// 		method: "propms.property_management_solution.doctype.lease.lease.make_lease_invoice_schedule",
// 		args: { leasedoc: doc.name },
// 		callback: function () {
// 			cur_frm.reload_doc();
// 		}
// 	});
// };

// var generate_pending_invoice = function () {
// 	frappe.call({
// 		method: "propms.lease_invoice.leaseInvoiceAutoCreate",
// 		args: {},
// 		callback: function () {
// 			cur_frm.reload_doc();
// 		}
// 	});
// };

// var getAllAgreement = function () {
// 	frappe.confirm(
// 		'Are you sure to initiate this long process?',
// 		function () {
// 			frappe.call({
// 				method: "propms.property_management_solution.doctype.lease.lease.getAllAgreement",
// 				args: {},
// 				callback: function () {
// 					cur_frm.reload_doc();
// 				}
// 			});
// 		},
// 		function () {
// 			frappe.msgprint(__("Closed before starting long process!"));
// 			window.close();
// 		}
// 	)
// };

// property_management_solution/doctype/agreement/agreement.js

frappe.ui.form.on("Agreement", {
  refresh(frm) {
    // update resident count
    update_resident_count(frm);

    // only when new doc and attachments are empty
    if (frm.is_new() && !(frm.doc.attachments && frm.doc.attachments.length)) {
      let row = frm.add_child("attachments");
      row.file_name = "Signed Agreement"; // optional default
      row.file_type = "PDF";
      frm.refresh_field("attachments");
    }
    if (!frm.is_new() && frm.doc.status === "Active") {
      frm.add_custom_button(__("Generate Next Billing"), () => {
        frappe.call({
          method:
            "propms.property_management_solution.doctype.agreement.agreement.generate_next_billing_manual",
          args: { agreement: frm.doc.name },
          callback: function (resp) {
            if (resp.message) {
              let { status, message } = resp.message;
              if (status === "success") {
                frappe.msgprint({
                  title: __("Success"),
                  indicator: "green",
                  message: message,
                });
                frm.reload_doc();
              } else {
                frappe.msgprint({
                  title: __("Error"),
                  indicator: "red",
                  message: message,
                });
              }
            }
          },
        });
      });

      frm.add_custom_button(__("Create PDC for Cheque Billings"), () => {
        frappe.call({
          method: "propms.api.pdc.create_pdcs_for_agreement",
          args: { agreement: frm.doc.name },
          freeze: true,
          callback(r) {
            if (!r.exc && r.message) {
              const created = r.message.created || [];
              frappe.msgprint({
                title: __("PDC"),
                indicator: created.length ? "green" : "blue",
                message: created.length
                  ? __("Created PDC(s): {0}", [created.join(", ")])
                  : r.message.message || __("No pending cheque billings need PDC."),
              });
              frm.reload_doc();
            }
          },
        });
      }, __("PDC"));
    }
  },
  validate(frm) {
    if (
      !frm.signed_agreement_received &&
      frm.doc.attachments &&
      frm.doc.attachments.length
    ) {
      // look for Signed Agreement row

      let signed_row = frm.doc.attachments.find((row) => row.file);
      console.log("signed", signed_row);
      if (signed_row) {
        frm.set_value("signed_agreement_received", 1);
      } else {
        frm.set_value("signed_agreement_received", 0);
      }
    }

    if (frm.is_new() && !frm.doc.next_period_start) {
      frm.set_value("next_period_start", frm.doc.start_date);
    }

    if (frm.is_new() && !frm.doc.next_period_end) {
      frm.set_value("next_period_end", frm.doc.end_date);
    }
  },
});

frappe.ui.form.on("File and Video Attachment Items", {
  before_attachments_remove: function (frm, cdt, cdn) {
    console.log("Before Delete");
    let row = locals[cdt][cdn];
    // If attachment_type is "Signed Agreement", stop deletion
    if (row.file_name === "Signed Agreement") {
      frappe.throw(
        __("You cannot delete the mandatory 'Signed Agreement' attachment."),
      );
      return false;
    }
  },
});

frappe.ui.form.on("Agreement Resident", {
  resident_add(frm) {
    update_resident_count(frm);
  },
  resident_remove(frm) {
    update_resident_count(frm);
  },
});

function update_resident_count(frm) {
  if (frm.doc.resident) {
    frm.set_value("number_of_residents", frm.doc.resident.length);
  } else {
    frm.set_value("number_of_residents", 0);
  }
}

frappe.ui.form.on("Agreement", {
  refresh(frm) {
    // nothing special on load for now
  },

  start_date(frm) {
    regenerate_payment_schedule(frm);
  },

  end_date(frm) {
    regenerate_payment_schedule(frm);
  },

  frequency(frm) {
    regenerate_payment_schedule(frm);
  },

  fee_amount(frm) {
    regenerate_payment_schedule(frm);
  },
});

/* ------------------------------
   Core Helpers
--------------------------------*/

function regenerate_payment_schedule(frm) {
  if (!is_ready_for_schedule(frm)) {
    return;
  }

  // Clear existing rows
  frm.clear_table("payment_schedule");

  build_payment_schedule_rows(frm);

  frm.refresh_field("payment_schedule");
}

function build_payment_schedule_rows(frm) {
  let start = moment(frm.doc.start_date);
  let end = moment(frm.doc.end_date);
  let frequency = frm.doc.frequency || "Month";
  let amount = frm.doc.fee_amount || 0;

  while (start.isSameOrBefore(end)) {
    let period_start = start.clone();
    let period_end;

    if (frequency === "Month") {
      period_end = start.clone().add(1, "months").subtract(1, "days");
      start.add(1, "months");
    } else if (frequency === "Fortnight") {
      period_end = start.clone().add(13, "days");
      start.add(14, "days");
    } else if (frequency === "Week") {
      period_end = start.clone().add(6, "days");
      start.add(7, "days");
    } else {
      frappe.msgprint("Unsupported frequency");
      return;
    }

    // Do not exceed agreement end date
    if (period_end.isAfter(end)) {
      period_end = end.clone();
    }

    let row = frm.add_child("payment_schedule");
    row.period_start = period_start.format("YYYY-MM-DD");
    row.period_end = period_end.format("YYYY-MM-DD");
    row.amount = amount;
    row.status = "Draft";
  }
}

function is_ready_for_schedule(frm) {
  if (!frm.doc.start_date || !frm.doc.end_date || !frm.doc.frequency) {
    return false;
  }

  if (moment(frm.doc.end_date).isBefore(frm.doc.start_date)) {
    frappe.msgprint("End Date cannot be before Start Date.");
    return false;
  }

  if (!frm.doc.fee_amount || frm.doc.fee_amount <= 0) {
    frappe.msgprint("Fee Amount must be greater than zero.");
    return false;
  }

  return true;
}

frappe.ui.form.on("Agreement", {
  refresh(frm) {
    if (
      frm.doc.docstatus === 1 &&
      frm.doc.key_money_amount &&
      frm.doc.key_money_status === "Draft"
    ) {
      frm.add_custom_button("Generate Key Money", () => {
        frappe.call({
          method: "propms.api.electricity.generate_key_money",
          args: {
            agreement: frm.doc.name,
          },
          callback() {
            frm.reload_doc();
          },
        });
      });
    }
  },
});

// frappe.ui.form.on("Agreement", {
//   refresh(frm) {
//     // Do not show button if already terminated
//     if (frm.doc.status === "Terminated") return;

//     // Ensure payment_schedule exists
//     if (!frm.doc.payment_schedule || !frm.doc.payment_schedule.length) return;

//     // Check if all payment schedule rows are Paid
//     const all_paid = frm.doc.payment_schedule.every(
//       (row) => row.status === "Paid"
//     );

//     if (all_paid && frm.doc.docstatus === 1) {
//       frm.add_custom_button("Terminate", () => {
//         frappe.confirm(
//           "Are you sure you want to terminate this Agreement?",
//           () => {
//             frm.set_value("status", "Terminated");
//             frm.save();
//           }
//         );
//       });
//     }
//   },
// });

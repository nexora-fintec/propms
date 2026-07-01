frappe.ui.form.on("Agreement Billing Entry", {
  refresh(frm) {
    if (frm.is_new()) return;

    const is_cheque = (frm.doc.mode_of_payment || "").toLowerCase() === "cheque";
    const open_status = ["Pending", "Sent", "Overdue"].includes(frm.doc.status);

    if (open_status) {
      frm.add_custom_button(__("Send Email"), () => {
        frappe.call({
          method: "propms.api.billing.send_billing_entry",
          args: { docname: frm.doc.name },
          callback() {
            frappe.msgprint(__("Billing Entry Sent Successfully"));
            frm.reload_doc();
          },
        });
      });

      if (is_cheque) {
        if (!frm.doc.post_dated_cheque) {
          frm.set_intro(
            __("Cheque payment: use <b>Create PDC</b> to hold the cheque until presenting date. "
              + "Sales Invoice and Payment Entry are created when the cheque is presented."),
            "blue"
          );

          frm.add_custom_button(
            __("Create PDC"),
            () => confirm_create_pdc(frm),
            __("PDC")
          );
        } else {
          frm.set_intro(
            __("PDC {0} is held. Present the cheque on or after the cheque date.", [
              frm.doc.post_dated_cheque,
            ]),
            "green"
          );
          frm.add_custom_button(__("Open PDC"), () => {
            frappe.set_route("Form", "Post Dated Cheque", frm.doc.post_dated_cheque);
          }, __("PDC"));
        }
      } else {
        frm.add_custom_button(__("Paid"), () => {
          frappe.confirm(
            __("This will create Sales Invoice and Payment Entry. Continue?"),
            () => pay_billing_now(frm)
          );
        });
      }
    }

    if (frm.doc.post_dated_cheque) {
      frm.add_custom_button(__("Post Dated Cheque"), () => {
        frappe.set_route("Form", "Post Dated Cheque", frm.doc.post_dated_cheque);
      }, __("View"));
    }

    if (frm.doc.sales_invoice) {
      frm.add_custom_button(__("Sales Invoice"), () => {
        frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice);
      }, __("View"));
    }

    if (is_cheque && frm.doc.status === "Paid" && (frm.doc.payment_entry || frm.doc.post_dated_cheque)) {
      frm.add_custom_button(__("Mark Cheque as Bounced"), () => {
        frappe.confirm(
          __("Cancel Payment Entry and mark cheque as bounced?"),
          () => {
            frappe.call({
              method: "propms.api.billing.mark_cheque_bounced",
              args: { billing_entry: frm.doc.name },
              freeze: true,
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
      }, __("PDC"));
    }
  },
});

function confirm_create_pdc(frm) {
  if (!frm.doc.cheque_no || !frm.doc.cheque_date) {
    frappe.msgprint({
      title: __("Missing Cheque Details"),
      indicator: "red",
      message: __("Enter Cheque No and Cheque Date before creating PDC."),
    });
    return;
  }

  frappe.confirm(
    __("Create Post Dated Cheque and hold until {0}?", [frm.doc.cheque_date]),
    () => {
      frappe.call({
        method: "propms.api.pdc.create_pdc_from_billing",
        args: { billing_entry_name: frm.doc.name },
        freeze: true,
        callback(r) {
          if (!r.exc) {
            frappe.msgprint({
              title: __("PDC Created"),
              indicator: "green",
              message: __("Post Dated Cheque: {0}", [r.message.pdc]),
            });
            frm.reload_doc();
          }
        },
      });
    }
  );
}

function pay_billing_now(frm) {
  frm.disable_save();
  frappe.call({
    method: "propms.api.billing.pay_billing_entry_with_invoice",
    args: { billing_entry_name: frm.doc.name },
    freeze: true,
    freeze_message: __("Processing Payment..."),
    callback(r) {
      if (!r.exc) {
        frappe.msgprint(
          `<b>${__("Sales Invoice")}:</b> ${r.message.sales_invoice}<br>
           <b>${__("Payment Entry")}:</b> ${r.message.payment_entry}`
        );
        frm.reload_doc();
      }
    },
    always() {
      frm.enable_save();
    },
  });
}

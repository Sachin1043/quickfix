frappe.ui.form.on("Job Card", {

    refresh(frm) {

        // ── Technician filter ──
        frm.set_query("assigned_technician", function () {
            return {
                filters: {
                    specialization: frm.doc.device_type
                }
            };
        });

        // ── Status Indicator ──
        if (frm.doc.status === "Pending Diagnosis") {
            frm.dashboard.add_indicator(__("Pending Diagnosis"), "orange");
        } else if (frm.doc.status === "In Repair") {
            frm.dashboard.add_indicator(__("In Repair"), "blue");
        } else if (frm.doc.status === "Ready for Delivery") {
            frm.dashboard.add_indicator(__("Ready for Delivery"), "green");
        } else if (frm.doc.status === "Delivered") {
            frm.dashboard.add_indicator(__("Delivered"), "gray");
        }

        // ── Mark as Delivered button ──
        if (frm.doc.status === "Ready for Delivery" && frm.doc.docstatus === 1) {
            frm.add_custom_button(__("Mark as Delivered"), function () {
                frm.set_value("status", "Delivered");
                frm.save();
            });
        }

        // ── Shop name in header ──
        if (frappe.boot.quickfix_shop_name) {
            frm.dashboard.set_headline(
                __("Shop: {0}", [frappe.boot.quickfix_shop_name])
            );
        }

        // ── Reject Job ──
        frm.add_custom_button(__("Reject Job"), function () {
            let d = new frappe.ui.Dialog({
                title: __("Reject Job"),
                fields: [
                    {
                        label: __("Reason"),
                        fieldname: "reason",
                        fieldtype: "Small Text",
                        reqd: 1
                    }
                ],
                primary_action(values) {
                    console.log(values.reason);
                    d.hide();
                }
            });
            d.show();
        });

        // ── Transfer Technician ──
        frm.add_custom_button(__("Transfer Technician"), function () {
            frappe.prompt(
                [
                    {
                        label: __("Technician"),
                        fieldname: "technician",
                        fieldtype: "Link",
                        options: "Technician"
                    }
                ],
                function (values) {
                    frappe.confirm(
                        __("Transfer this technician?"),
                        function () {
                            frappe.call({
                                method: "quickfix.api.transfer_job",
                                args: {
                                    technician: values.technician
                                },
                                callback: function () {
                                    frm.set_value(
                                        "assigned_technician",
                                        values.technician
                                    );
                                    frm.trigger("assigned_technician");
                                }
                            });
                        }
                    );
                }
            );
        });

        // ── Customer summary ──
        frappe.msgprint(
            __("Customer: {0}, Email: {1}, Amount: {2}", [
                frm.doc.customer_name,
                frm.doc.customer_email,
                frm.doc.final_amount
            ])
        );
    },

    // ── Technician specialization warning ──
    assigned_technician(frm) {
        if (frm.doc.assigned_technician) {
            frappe.db.get_doc("Technician", frm.doc.assigned_technician).then(doc => {
                if (doc.specialization !== frm.doc.device_type) {
                    frappe.msgprint({
                        title: __("Warning"),
                        indicator: "orange",
                        message: __("Technician specialization does not match the Device Type")
                    });
                }
            });
        }
    }
});

// ── Child Table - Part Usage ──
frappe.ui.form.on("Part Usage", {
    quantity(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        let total = row.quantity * row.unit_price;
        frappe.model.set_value(cdt, cdn, "total_price", total);
    }
});
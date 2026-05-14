frappe.ui.form.on("Job Card",
    {
        refresh(frm)
        {
            frm.set_query("assigned_technician",function()
            {
                return{
                    filters:
                    {
                        specialization:frm.doc.device_type
                    }
                }
            })
        }
    }
)
frappe.ui.form.on("Job Card", {

    refresh(frm) {

        // Status Indicator

        if (frm.doc.status === "Pending Diagnosis") {

            frm.dashboard.add_indicator(
                "Pending Diagnosis",
                "orange"
            );
        }

        else if (frm.doc.status === "In Repair") {

            frm.dashboard.add_indicator(
                "In Repair",
                "blue"
            );
        }

        else if (frm.doc.status === "Ready for Delivery") {

            frm.dashboard.add_indicator(
                "Ready for Delivery",
                "green"
            );
        }

        else if (frm.doc.status === "Delivered") {

            frm.dashboard.add_indicator(
                "Delivered",
                "gray"
            );
        }


        // Custom Button

        if (
            frm.doc.status === "Ready for Delivery" &&
            frm.doc.docstatus === 1
        ) {

            frm.add_custom_button(
                "Mark as Delivered",
                function() {

                    frm.set_value("status", "Delivered");

                    frm.save();
                }
            );
        }


        // Show Shop Name in Header

        if (frappe.boot.quickfix_shop_name) {

            frm.dashboard.set_headline(
                __("Shop: " + frappe.boot.quickfix_shop_name)
            );
        }
    }
});

// Parent Doctype - Job Card

frappe.ui.form.on("Job Card", {

    assigned_technician(frm) {

        if (frm.doc.assigned_technician) {

            frappe.db.get_doc(
                "Technician",
                frm.doc.assigned_technician
            ).then(doc => {

                if (doc.specialization !== frm.doc.device_type) {

                    frappe.msgprint({
                        title: __("Warning"),
                        indicator: "orange",
                        message: __(
                            "Technician specialization does not match the Device Type"
                        )
                    });
                }
            });
        }
    }
});


// Child Table - Part

frappe.ui.form.on("Part Usage", {

    quantity(frm, cdt, cdn) {

        let row = locals[cdt][cdn];

        let total = row.quantity * row.unit_price;

        frappe.model.set_value(
            cdt,
            cdn,
            "total_price",
            total
        );
    }
});

// frappe.ui.form.on("Job Card")
// {
//     onload(frm)
//     {
//         frm.realtime.on("Job_ready",function()
//         {
//             frappe.show_alert(
//                 {
//                     message:__("Job is ready for delivery"),
//                     indicator:"green"
//                 }
//             )
//         })
//     }
// }

frappe.ui.form.on("Job Card", {

    refresh(frm) {

        // Reject Job

        frm.add_custom_button("Reject Job", function() {

            let d = new frappe.ui.Dialog({

                title: "Reject Job",

                fields: [
                    {
                        label: "Reason",
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


        // Transfer Technician

        frm.add_custom_button("Transfer Technician", function() {

            frappe.prompt(

                [
                    {
                        label: "Technician",
                        fieldname: "technician",
                        fieldtype: "Link",
                        options: "Technician"
                    }
                ],

                function(values) {

                    frappe.confirm(

                        "Transfer this technician?",

                        function() {

                            frappe.call({

                                method: "quickfix.api.transfer_job",

                                args: {
                                    technician: values.technician
                                },

                                callback: function() {

                                    frm.set_value(
                                        "assigned_technician",
                                        values.technician
                                    );

                                    frm.trigger(
                                        "assigned_technician"
                                    );
                                }
                            });
                        }
                    );
                }
            );
        });
    }
});


frappe.listview_settings["Job Card"] = {

    add_fields: [
        "final_amount",
        "priority"
    ],

    get_indicator(doc) {

        if (doc.status === "Pending Diagnosis") {
            return ["Pending Diagnosis", "orange"];
        }

        if (doc.status === "In Repair") {
            return ["In Repair", "blue"];
        }

        if (doc.status === "Ready for Delivery") {
            return ["Ready for Delivery", "green"];
        }

        if (doc.status === "Delivered") {
            return ["Delivered", "gray"];
        }
    },

    formatters: {

        final_amount(value) {
            return `₹ ${value}`;
        }
    },

    button: {

    show(doc) {
        return doc.status === "In Repair";
    },

    get_label() {
        return "Complete";
    },

    get_description(doc) {
        return "Complete Job";
    },

    action(doc) {

        frappe.call({

            method: "quickfix.api.complete_job",

            args: {
                job: doc.name
            },

            callback() {
                frappe.show_alert("Job Completed");
                frappe.listview.refresh();
            }
        });
    }
}
};
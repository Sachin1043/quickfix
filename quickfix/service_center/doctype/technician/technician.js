frappe.ui.form.on("Technician",
    {
        refresh(frm)
        {
            if(frm.doc.technician_name === "mary")
            {
                frm.set_value("phone","9876543216")
            }
        }
    }
)
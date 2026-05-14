frappe.query_reports["Spare Parts Inventory"] = {

    formatter(value, row, column, data, default_formatter) {

        value = default_formatter(value, row, column, data);

        if (
            data.stock_qty <= data.reorder_level
            &&
            data.part_name != "Total"
        ) {

            value = `
                <span style="background-color:red;color:white;padding:2px">
                    ${value}
                </span>
            `;
        }

        return value;
    }
}
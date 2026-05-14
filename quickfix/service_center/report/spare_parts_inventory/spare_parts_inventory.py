# Copyright (c) 2026, sachin and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	report_summary = get_report_summary(data)

	return columns, data , None , None , report_summary


def get_columns():

    return [

        {
            "label": "Part Name",
            "fieldname": "part_name",
            "fieldtype": "Data",
            "width": 180
        },

        {
            "label": "Part Code",
            "fieldname": "part_code",
            "fieldtype": "Data",
            "width": 120
        },

        {
            "label": "Device Type",
            "fieldname": "device_type",
            "fieldtype": "Data",
            "width": 140
        },

        {
            "label": "Stock Qty",
            "fieldname": "stock_qty",
            "fieldtype": "Int",
            "width": 120
        },

        {
            "label": "Reorder Level",
            "fieldname": "reorder_level",
            "fieldtype": "Int",
            "width": 140
        },

        {
            "label": "Unit Cost",
            "fieldname": "unit_cost",
            "fieldtype": "Currency",
            "width": 120
        },

        {
            "label": "Selling Price",
            "fieldname": "selling_price",
            "fieldtype": "Currency",
            "width": 140
        },

        {
            "label": "Margin %",
            "fieldname": "margin_percent",
            "fieldtype": "Percent",
            "width": 120
        },

        {
            "label": "Total Value",
            "fieldname": "total_value",
            "fieldtype": "Currency",
            "width": 140
        }
    ]

def get_data():

    parts = frappe.get_list(

        "Spare Part",

        fields=[
            "part_name",
            "part_code",
            "device_type",
            "stock_qty",
            "reorder_level",
            "unit_cost",
            "selling_price"
        ]
    )

    data = []

    total_stock = 0

    total_inventory_value = 0

    for part in parts:

        margin_percent = 0

        if part.unit_cost:

            margin_percent = (
                (part.selling_price - part.unit_cost)
                / part.unit_cost
            ) * 100

        total_value = part.stock_qty * part.unit_cost

        total_stock += part.stock_qty

        total_inventory_value += total_value

        data.append({

            "part_name": part.part_name,

            "part_code": part.part_code,

            "device_type": part.device_type,

            "stock_qty": part.stock_qty,

            "reorder_level": part.reorder_level,

            "unit_cost": part.unit_cost,

            "selling_price": part.selling_price,

            "margin_percent": margin_percent,

            "total_value": total_value
        })

    data.append({

        "part_name": "Total",

        "stock_qty": total_stock,

        "total_value": total_inventory_value
    })

    return data


def get_report_summary(data):

    total_parts = len(data) - 1

    below_reorder = 0

    total_inventory_value = 0

    for row in data:

        if row.get("stock_qty") and row.get("reorder_level"):

            if row["stock_qty"] <= row["reorder_level"]:

                below_reorder += 1

        total_inventory_value += row.get("total_value") or 0

    return [

        {
            "label": "Total Parts",
            "value": total_parts,
            "indicator": "Blue"
        },

        {
            "label": "Below Reorder",
            "value": below_reorder,
            "indicator": "Red"
        },

        {
            "label": "Total Inventory Value",
            "value": total_inventory_value,
            "indicator": "Green"
        }
    ]
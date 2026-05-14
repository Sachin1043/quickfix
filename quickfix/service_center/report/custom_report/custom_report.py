
import frappe
from frappe.utils import date_diff

def execute(filters=None):

	columns  =get_columns(filters)
	data = get_data(filters)
	chart = get_chart(data)
	report_summary = get_report_summary(data)

	return columns, data , None , chart , report_summary

def get_columns(filters):

    columns = [

        {
            "label": "Technician",
            "fieldname": "technician",
            "fieldtype": "Link",
            "options": "Technician",
            "width": 180
        },

        {
            "label": "Total Jobs",
            "fieldname": "total_jobs",
            "fieldtype": "Int",
            "width": 120
        },

        {
            "label": "Completed",
            "fieldname": "completed",
            "fieldtype": "Int",
            "width": 120
        },

        {
            "label": "Avg Turnaround Days",
            "fieldname": "avg_turnaround",
            "fieldtype": "Float",
            "width": 170
        },

        {
            "label": "Revenue",
            "fieldname": "revenue",
            "fieldtype": "Currency",
            "width": 140
        },

        {
            "label": "Completion Rate",
            "fieldname": "completion_rate",
            "fieldtype": "Int",
            "width": 170
        }
    ]

    for dt in frappe.get_all("Device Type", fields=["name"]):

        columns.append({

            "label": dt.name,
            "fieldname": dt.name.lower().replace(" ", "_"),
            "fieldtype": "Int",
            "width": 100
        })

    return columns

def get_data(filters):

    jobs = frappe.get_list(

        "Job Card",

        filters={
            "creation": ["between", [filters.get("from_date"), filters.get("to_date")]]
        },

        fields=[
            "name",
            "device_type",
            "assigned_technician",
            "status",
            "creation",
            "modified",
            "final_amount"
        ]
    )

    technician_map = {}

    device_types = frappe.get_all("Device Type", fields=["name"])

    for job in jobs:

        technician = job.assigned_technician or "Not Assigned"

        if technician not in technician_map:

            technician_map[technician] = {

                "technician": technician,
                "total_jobs": 0,
                "completed": 0,
                "avg_turnaround": 0,
                "revenue": 0,
                "completion_rate": 0,
                "total_days": 0
            }

            for dt in device_types:

                technician_map[technician][dt.name.lower().replace(" ", "_")] = 0

        technician_map[technician]["total_jobs"] += 1

        technician_map[technician]["revenue"] += job.final_amount or 0

        technician_map[technician][job.device_type.lower().replace(" ", "_")] += 1

        turnaround = date_diff(job.modified, job.creation)

        technician_map[technician]["total_days"] += turnaround

        if job.status == "Delivered":

            technician_map[technician]["completed"] += 1

    data = []

    for tech in technician_map.values():

        if tech["total_jobs"] > 0:

            tech["avg_turnaround"] = (
                tech["total_days"] / tech["total_jobs"]
            )

            tech["completion_rate"] = (
                tech["completed"] / tech["total_jobs"]
            ) * 100

        data.append(tech)

    return data
	
def get_chart(data):

    return {

        "data": {

            "labels": [d["technician"] for d in data],

            "datasets": [

                {
                    "name": "Total Jobs",
                    "values": [d["total_jobs"] for d in data]
                },

                {
                    "name": "Completed",
                    "values": [d["completed"] for d in data]
                }
            ]
        },

        "type": "bar"
    }
def get_report_summary(data):

    total_jobs = sum(d["total_jobs"] for d in data)

    total_revenue = sum(d["revenue"] for d in data)

    best_technician = max(
        data,
        key=lambda x: x["completion_rate"],
        default={"technician": ""}
    )

    return [

        {
            "label": "Total Jobs",
            "value": total_jobs,
            "indicator": "Blue"
        },

        {
            "label": "Total Revenue",
            "value": total_revenue,
            "indicator": "Green"
        },

        {
            "label": "Best Technician",
            "value": best_technician["technician"],
            "indicator": "Orange"
        }
    ]

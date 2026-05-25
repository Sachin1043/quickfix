import frappe

def execute():
    translations = [
        {
            "source_text": "Phone Number must be exactly 10 digit",
            "translated_text": "தொலைபேசி எண் சரியாக 10 இலக்கங்களாக இருக்க வேண்டும்",
            "language": "ta"
        },
        {
            "source_text": "Cannot delete a submitted Job Card. Cancel it first.",
            "translated_text": "சமர்ப்பிக்கப்பட்ட வேலை அட்டையை நீக்க முடியாது. முதலில் ரத்து செய்யுங்கள்.",
            "language": "ta"
        },
        {
            "source_text": "Only allowed to submit if the status is Ready for Delivery",
            "translated_text": "நிலை டெலிவரிக்கு தயார் என்றிருக்கும்போது மட்டுமே சமர்ப்பிக்கலாம்.",
            "language": "ta"
        }
    ]

    for t in translations:
        if not frappe.db.exists("Translation", {
            "source_text": t["source_text"],
            "language": t["language"]
        }):
            frappe.get_doc({
                "doctype": "Translation",
                **t
            }).insert(ignore_permissions=True)

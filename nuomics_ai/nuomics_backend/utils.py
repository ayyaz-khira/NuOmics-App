import frappe
from frappe import _
from frappe.utils import random_string, get_url, sha256_hash


@frappe.whitelist()
def sync_custom_fields():
    if not frappe.db.exists('Custom Field', {'dt': 'User', 'fieldname': 'organization'}):
        frappe.get_doc({
            'doctype': 'Custom Field',
            'dt': 'User',
            'fieldname': 'organization',
            'label': 'Organization',
            'fieldtype': 'Link',
            'options': 'User Registration',
            'insert_after': 'email'
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    return "Custom field checked and created if missing."



@frappe.whitelist(allow_guest=True)
def request_password_reset(email):
    if not email:
        return {"status": "error", "message": "Email is required."}
    
    # Check if user exists
    user = frappe.db.get_value("User", {"email": email}, "name")
    if not user:
        return {"status": "error", "message": "This email is not registered."}
        
    try:
        ur = frappe.get_doc("User", user)
        if not ur.enabled:
            return {"status": "error", "message": "Your account is disabled. Please wait for approval or contact your administrator."}
        ur.reset_password(send_email=True)
        return {"status": "success"}
    except Exception as e:
        # Standardize the error message if it is a frappe error, else generic Support message.
        err_msg = str(e) if hasattr(e, 'message') else "Failed to send reset email. Please contact support."
        frappe.log_error(frappe.get_traceback(), "Password Reset Failed")
        return {"status": "error", "message": err_msg}
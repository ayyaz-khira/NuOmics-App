import frappe
from frappe.utils import sha256_hash

def get_context(context):
    key = frappe.form_dict.get('key')

    if not key:
        frappe.local.flags.redirect_location = '/login'
        raise frappe.Redirect

    hashed_key = sha256_hash(key)
    user = frappe.db.get_value("User", {"reset_password_key": hashed_key}, "name")

    if not user:
        frappe.local.flags.redirect_location = '/login?status=invalid_key'
        raise frappe.Redirect

    context.reset_key = key  # always pass RAW key to template
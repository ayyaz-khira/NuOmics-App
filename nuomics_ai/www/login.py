import frappe
from nuomics_ai.nuomics_backend.security import get_dashboard_url_for_user

def get_context(context):
    if frappe.session.user != "Guest":
        target = get_dashboard_url_for_user(frappe.session.user)
        if target:
            frappe.local.flags.redirect_location = target
            raise frappe.Redirect

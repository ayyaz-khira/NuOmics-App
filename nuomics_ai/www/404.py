import frappe

def get_context(context):
    frappe.local.flags.redirect_location = None
    context.no_cache = 1
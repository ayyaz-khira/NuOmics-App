import frappe
import requests

def get_context(context):
    """
    Gateway to trigger the Oracle NuOmics Auth API and redirect to the test portal.
    """
    email = frappe.form_dict.get('email')
    
    if not email:
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/login"
        return

    # 1. Hit the Oracle Auth API in the background
    auth_api_url = "https://oracle.nuomics.io/auth/forgot-password"
    try:
        # Best effort POST to trigger the external system
        requests.post(auth_api_url, json={"email": email}, timeout=10)
    except Exception as e:
        frappe.log_error(f"Failed to hit Oracle Auth API for {email}: {str(e)}", "External Auth API")

    # 2. Redirect to the test portal with the email pre-filled in the URL
    target_url = f"https://test.nuomics.io/forgot-password?email={email}"
    
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = target_url

import frappe
from frappe import _
import requests

def get_api_settings():
    """Helper to fetch NuOmics API settings."""
    settings = frappe.get_single("NuOmics Settings")

    if not settings.url:
        frappe.throw(_("Nuomics API URL not configured"))
    return settings

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
        
        # We no longer send internal mails. The Oracle system will handle it.
        trigger_password_reset_email(email)
        return {"status": "success"}
    except Exception as e:
        # Standardize the error message if it is a frappe error, else generic Support message.
        err_msg = str(e) if hasattr(e, 'message') else "Failed to send reset email. Please contact support."
        frappe.log_error(frappe.get_traceback(), "Password Reset Failed")
        return {"status": "error", "message": err_msg}



def register_external_user(email, full_name, password="Nuomics@123"):
    settings = get_api_settings()
    url = f"{settings.url.rstrip('/')}/auth/register"

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }

    data = {
        "name": full_name,
        "email": email,
        "password": password
    }

    try:
        # Use a reasonable timeout to avoid blocking the main thread for too long
        response = requests.post(url, headers=headers, json=data, timeout=10)

        if response.status_code in [200, 201]:
            frappe.logger().info(f"External registration successful for {email}")
        else:
            # Check if it's already registered (e.g. 400 or 409 depending on API)
            # We log it but don't fail the main transaction
            frappe.log_error(f"External registration returned {response.status_code} for {email}: {response.text}", "External Auth API")

    except Exception as e:
        # Catch network errors, timeouts etc.
        frappe.log_error(f"External registration exception for {email}: {str(e)}", "External Auth API")



def trigger_password_reset_email(email):
    settings = get_api_settings()
    base_url = settings.url.rstrip('/')
    url = f"{base_url}/auth/forgot-password"

    headers = {
        "accept": "application/json",
        "Content-Type": "application/json"
    }

    data = {"email": email}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)

        if response.ok:
            frappe.logger("external_api").info(f"Password reset triggered for {email}")
        else:
            frappe.log_error(
                f"Status {response.status_code} for {email}: {response.text}",
                "External Auth API"
            )

    except requests.exceptions.RequestException as e:
        frappe.log_error(
            f"Exception for {email}: {str(e)}",
            "External Auth API"
        )


#Function for getting forgot-password url
@frappe.whitelist()
def get_forgot_password_url():
    settings = get_api_settings()
    return f"{settings.url.rstrip('/')}/auth/forgot-password"



import frappe
from frappe import _

# Helper to validate if the current user has access to a specific organization registration
def validate_org_access(registration_id):
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in to access this information"), frappe.PermissionError)
        
    # Super Admin / System Manager bypass
    if "System Manager" in frappe.get_roles():
        return True
        
    # Check if the user is linked to this specific organization
    user_org = frappe.db.get_value("User", frappe.session.user, "organization")
    if user_org != registration_id:
        frappe.throw(_("You are not authorized to manage this organization"), frappe.PermissionError)
    
    return True

def get_user_permission_query(user=None):
    if not user: user = frappe.session.user
    
    try:
        # Administrators can see everything
        roles = frappe.get_roles(user)
        if "System Manager" in roles:
            return None
            
        # Get the organization for the current user
        org = frappe.db.get_value("User", user, "organization")
        
        if org:
            return f"(`tabUser`.organization = '{org}')"
        
        # If no org, restrict to self
        return "(`tabUser`.name = '{0}')".format(frappe.db.escape(user))
    except Exception:
        # Fallback to only seeing self in case of any issues during login phase
        return "(`tabUser`.name = '{0}')".format(frappe.db.escape(user))

def get_dashboard_url_for_user(user):
    """Returns the appropriate dashboard URL based on user roles."""
    if user == "Administrator":
        return "/admin/dashboard"

    roles = frappe.get_roles(user)
    
    if "System Manager" in roles:
        return "/admin/dashboard"
    
    if "Organization Admin" in roles:
        return "/dashboard"
    
    # Default for regular members
    return "http://live.nuomics.io"

def validate_org_admin_route():
    path = (frappe.request.path or "").strip("/")

    # 1. Bypass static/system paths
    if any(path.startswith(p) for p in [
        "api/", "assets/", "files/", "private/", "socket.io",
        "_/", "app/", "web_form/"
    ]):
        return

    # 2. Always allow login
    if path in ("login", "auth/login"):
        return

    # 3. Protect update-password — must have key param
    if path in ("update-password", "auth/update-password"):
        if not frappe.form_dict.get("key"):
            frappe.local.flags.redirect_location = "/404"
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = "/404"
            return

    if frappe.session.user == "Guest":
        return

    roles = frappe.get_roles()
    is_manager = "System Manager" in roles or frappe.session.user == "Administrator"

    # 4. Block admin routes for non-managers
    if not is_manager and ("admin/" in path or path.startswith("admin")):
        frappe.local.flags.redirect_location = "/404"
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/404"
        return

    # 5. Sandbox Organization Admins
    if "Organization Admin" in roles and not is_manager:
        allowed_routes = [
            "", "dashboard", "contact-us", "login", "helpdesk",
            "logout", "me", "error", "404", "home",
            "update-password", "auth/update-password", "not-found"
        ]

        is_allowed = False
        for r in allowed_routes:
            if r == "dashboard":
                if path == "dashboard":  # exact match — blocks /dashboard/ll
                    is_allowed = True
                    break
            elif path == r or path.startswith(r + "/"):
                is_allowed = True
                break

        if not is_allowed:
            frappe.local.flags.redirect_location = "/404"
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = "/404"
            return



def validate_super_admin():
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in"), frappe.PermissionError)
    if "System Manager" not in frappe.get_roles() and frappe.session.user != "Administrator":
        frappe.throw(_("Not authorized - Super Admin only"), frappe.PermissionError)

def redirect_after_login(login_manager):
    user = login_manager.user

    # Create Login Alert
    if user != "Guest":
        frappe.get_doc({
            "doctype": "System Alert",
            "alert_type": "Login",
            "message": f"User {user} logged in to the system",
            "user": user,
            "is_read": 0
        }).insert(ignore_permissions=True)
        frappe.db.commit()

    # Determine target based on roles
    target = get_dashboard_url_for_user(user)
    
    frappe.cache.hset("redirect_after_login", user, target)
    frappe.local.response["redirect_to"] = target
    frappe.local.response["message"] = target
    return

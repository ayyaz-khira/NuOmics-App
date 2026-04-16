import frappe
from frappe import _
from nuomics_ai.nuomics_backend.security import validate_super_admin

@frappe.whitelist(allow_guest=True)
def capture_registration_lead(first_name, last_name, work_email, organization_name):
    if not first_name or not last_name or not work_email or not organization_name:
        frappe.throw(_("All fields are required"))

    if frappe.db.exists("Organization Registration", {"work_email": work_email}):
        return {
            "status": "already_exists",
            "message": _("A registration request with this email already exists.")
        }

    try:
        new_lead = frappe.get_doc({
            "doctype": "Organization Registration",   
            "first_name": first_name,
            "last_name": last_name,
            "work_email": work_email,
            "organization_name": organization_name,
            "status": "Lead"
        })

        new_lead.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": _("Lead captured successfully"),
            "name": new_lead.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Lead Capture Failed"))
        return {
            "status": "error",
            "message": "Error saving request"
        }

@frappe.whitelist(allow_guest=True)
def submit_details(first_name, last_name, work_email, organization_name, contact_number, organization_type, payment_status, country_code, number_of_users=1):
    
    if not all([first_name, last_name, work_email, organization_name, contact_number, organization_type, country_code]):
        frappe.throw(_("All main fields are required"))

    # Email Validation
    if not frappe.utils.validate_email_address(work_email):
        frappe.throw(_("Invalid email address: {0}").format(work_email))

    # Organization Specific Validations
    email_lower = work_email.lower()
    org_name_clean = "".join(filter(str.isalnum, organization_name.lower()))
    
    if organization_type == "Educational":
        if not email_lower.endswith(".edu"):
            frappe.throw(_("Educational organizations require a .edu email address."))
    elif organization_type in ["Industrial", "Enterprise"]:
        domain = email_lower.split("@")[-1].split(".")[0]
        if org_name_clean not in domain and domain not in org_name_clean:
            frappe.throw(_("For {0} organizations, the email domain should match the organization name.").format(organization_type))
        
    # Phone number validation (Country Specific)
    phone_raw = "".join(filter(str.isdigit, str(contact_number)))
    if country_code in ["+91", "+1"]:
        if len(phone_raw) != 10:
            frappe.throw(_("Please enter a valid 10-digit number for {0}.").format(country_code))
    elif len(phone_raw) < 8 or len(phone_raw) > 15:
        frappe.throw(_("Invalid contact number length."))

    # Combine for full contact number
    full_contact_number = f"{country_code} {contact_number}"

    if frappe.db.exists("User Registration", {"work_email": work_email}):
        return {
            "status": "already_exists",
            "message": _("A registration request with this email already exists.")
        }

    # Server-side amount calculation
    price_per_user = 10
    total_amount = int(number_of_users or 0) * price_per_user

    try:
        user = frappe.get_doc({
            "doctype": "User Registration",
            "first_name": first_name,
            "last_name": last_name,
            "work_email": work_email,
            "organization_name": organization_name,
            "contact_number": full_contact_number,
            "organization_type": organization_type,
            "number_of_users": number_of_users,
            "amount": total_amount,
            "payment_status": payment_status,
            "approval_status": "Pending Approval" 
        })

        user.insert(ignore_permissions=True)

        # Create a matching Lead doc in the CRM Lead DocType
        try:
            lead = frappe.get_doc({
                "doctype": "CRM Lead",
                "first_name": first_name,
                "last_name": last_name,
                "email": work_email,
                "mobile_no": full_contact_number,
                "organization": organization_name,
                "status": "New",
                "source": "Website",
                "custom_no_of_users": number_of_users,
                "custom_organization_type": organization_type
            })
            lead.insert(ignore_permissions=True)
        except Exception as lead_err:
            frappe.log_error(f"Lead Creation Failed: {str(lead_err)}", "Registration Lead Error")

        frappe.db.commit()

        return {
            "status": "success",
            "message": _("User registration captured successfully"),
            "name": user.name
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _("Lead Capture Failed"))
        return {
            "status": "error",
            "message": "Error saving request"
        }   




@frappe.whitelist()
def toggle_registration_status(registration_id, status):
    validate_super_admin()

    if status not in ["Approved", "Rejected", "Inactive", "Active", "Pending Approval"]:
        return {"status": "error", "message": "Invalid status value"}

    if not frappe.db.exists("User Registration", registration_id):
        return {"status": "error", "message": "Organization not found"}

    org_doc = frappe.get_doc("User Registration", registration_id)
    org_doc.approval_status = status
    org_doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "message": f"Status updated to {status} successfully."
    }
import frappe
from frappe import _
import csv
import base64
from nuomics_ai.nuomics_backend.security import validate_org_access
from nuomics_ai.nuomics_backend.utils import register_external_user,trigger_password_reset_email


@frappe.whitelist()
def get_user_capacity(registration_id):
    validate_org_access(registration_id)
    if not frappe.db.exists("User Registration", registration_id):
        return 0
    reg = frappe.get_doc("User Registration", registration_id)
    
    if reg.number_of_users:
        try:
            return int(reg.number_of_users)
        except (ValueError, TypeError):
            pass
            
    if not reg.organization_type:
        return 5 
        
    if reg.organization_type == "Individual":
        return 1
        
    capacity_str = reg.organization_type.split('(')[-1].replace(')', '')
    if '+' in capacity_str:
        return 999999 
    if '-' in capacity_str:
        try:
            return int(capacity_str.split('-')[-1].strip())
        except (ValueError, TypeError):
            return 5
    try:
        return int(capacity_str.strip())
    except (ValueError, TypeError):
        return 5 



@frappe.whitelist()
def add_org_user(registration_id, name, email):
    validate_org_access(registration_id)
    if not registration_id:
        return {"status": "error", "message": "No registration ID provided"}
        
    capacity = get_user_capacity(registration_id)
    current_count = frappe.db.count("Org User Item", {"parent": registration_id}) + 1
    
    if current_count >= capacity:
        return {"status": "error", "message": f"Organization Capacity reached ({capacity} users limit)"}
            
    if not frappe.db.exists("User", email):
        new_user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": name,
            "send_welcome_email": 0,
            "enabled": 0,
            "user_type": "Website User",
            "organization": registration_id  
        })
        new_user.insert(ignore_permissions=True)
        
        org_doc = frappe.get_doc("User Registration", registration_id)
        org_doc.append("members", {
            "name1": name,
            "email": email,
            "user_ref": new_user.name,
            "status": "Pending Approval"
        })
        org_doc.save(ignore_permissions=True)
        
        frappe.db.commit()
        return {"status": "success", "message": f"User {name} created successfully!"}
    else:
        existing_user = frappe.get_doc("User", email)
        if existing_user.organization == registration_id:
            return {"status": "error", "message": f"A user with email {email} already exists in your organization."}
        else:
            return {"status": "error", "message": f"User with email {email} is already registered in another organization."}



@frappe.whitelist()
def upload_org_users_csv(registration_id, file_url):
    validate_org_access(registration_id)
    if file_url.startswith("/files/"):
        file_path = frappe.get_site_path("public", file_url.lstrip("/"))
    else:
        file_path = frappe.get_site_path(file_url.lstrip("/"))
    capacity = get_user_capacity(registration_id)
    current_count = frappe.db.count("Org User Item", {"parent": registration_id}) + 1

    if current_count >= capacity:
        return {"status": "error", "message": f"Organization Capacity reached. You have already utilized your limit of {capacity} users."}
    
    inserted = 0
    skipped = 0
    org_doc = frappe.get_doc("User Registration", registration_id)
    existing_members = {m.email for m in org_doc.members}
    
    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            email = row.get('email', '').strip()
            name = row.get('name', 'N/A')
            
            if not email:
                continue

            if email in existing_members:
                skipped += 1
                continue
            
            if current_count + inserted >= capacity:
                break
            
            user_id = email
            if not frappe.db.exists("User", email):
                new_user = frappe.get_doc({
                    "doctype": "User",
                    "email": email,
                    "first_name": name,
                    "send_welcome_email": 0,
                    "enabled": 0,
                    "user_type": "Website User",
                    "organization": registration_id
                })
                new_user.insert(ignore_permissions=True)
                user_id = new_user.name
            else:
                frappe.db.set_value("User", email, "organization", registration_id)
            
            org_doc.append("members", {
                "name1": name,
                "email": email,
                "user_ref": user_id,
                "status": "Pending Approval"
            })
            
            inserted += 1
            existing_members.add(email)
        
    org_doc.save(ignore_permissions=True)
    frappe.db.commit()
    final_msg = f"Created {inserted} users. ({skipped} duplicates skipped)."
    if current_count + inserted >= capacity:
        final_msg = f"Partial Success: Created {inserted} users, but reached your limit of {capacity}. Some rows were skipped."
        
    return {"status": "success", "message": final_msg}



@frappe.whitelist()
def upload_csv_base64(registration_id, filename, filedata):
    validate_org_access(registration_id)
    try:
        if "," in filedata:
            filedata = filedata.split(",")[1]
        
        decoded_data = base64.b64decode(filedata)
        
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": filename,
            "content": decoded_data,
            "is_private": 0
        })
        file_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        return upload_org_users_csv(registration_id, file_doc.file_url)
    except Exception as e:
        return {"status": "error", "message": str(e)}



@frappe.whitelist()
def update_member_status(registration_id, email, status):
    validate_org_access(registration_id)

    if not registration_id or not email or not status:
        return {"status": "error", "message": "Missing required information"}

    if status not in ["Approved", "Rejected", "Pending Approval"]:
        return {"status": "error", "message": "Invalid status value"}

    # Check org approval
    org_status = frappe.db.get_value("User Registration", registration_id, "approval_status")
    if status == "Approved" and org_status != "Approved":
        return {"status": "error", "message": "Cannot enable a member while the organization is disabled."}

    org_doc = frappe.get_doc("User Registration", registration_id)

    old_status = None
    for m in org_doc.members:
        if m.email == email:
            old_status = m.status
            break

    if old_status is None:
        return {"status": "error", "message": "Member not found in your organization record."}

    # Update user enable/disable
    if frappe.db.exists("User", email):
        u = frappe.get_doc("User", email)
        was_disabled = not u.enabled
        u.enabled = 1 if status == "Approved" else 0
        u.save(ignore_permissions=True)

    # ✅ ONLY on transition → Approved
    if old_status != "Approved" and status == "Approved":
        frappe.log_error(f"[MEMBER APPROVED] {email}", "DEBUG")

        if frappe.db.exists("User", email):
            u = frappe.get_doc("User", email)

            # Send email
            # if was_disabled:
            #     u.send_welcome_mail_to_user()

            # Call external
            try:
                full_name = u.full_name or email
                register_external_user(email, full_name)
                trigger_password_reset_email(email)

            except Exception as e:
                frappe.log_error(str(e), "Nuomics Error")

    # Update child table
    for m in org_doc.members:
        if m.email == email:
            m.status = status
            break

    org_doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "message": f"User {email} has been {'approved' if status == 'Approved' else 'rejected'}."
    }



@frappe.whitelist()
def toggle_org_user_admin(registration_id, email, is_admin):
    validate_org_access(registration_id)
    if not registration_id or not email:
        return {"status": "error", "message": "Missing required information"}

    if int(is_admin) == 1:
        org_data = frappe.db.get_value("User Registration", registration_id, ["approval_status", "work_email"], as_dict=True)
        if org_data:
            if org_data.get("approval_status") != "Approved":
                return {"status": "error", "message": "Cannot promote member to admin while the organization is disabled."}
            
            admin_enabled = frappe.db.get_value("User", org_data.get("work_email"), "enabled")
            if admin_enabled == 0:
                return {"status": "error", "message": "Cannot promote member to admin while the primary organization admin is disabled."}

    if frappe.db.exists("User", email):
        if int(is_admin) == 1:
            if not frappe.db.exists("Has Role", {"parent": email, "role": "Organization Admin"}):
                h_role = frappe.get_doc({
                    "doctype": "Has Role",
                    "parent": email,
                    "parentfield": "roles",
                    "parenttype": "User",
                    "role": "Organization Admin"
                })
                h_role.insert(ignore_permissions=True)
                
            frappe.db.set_value("User", email, "enabled", 1)
        else:
            frappe.db.sql("DELETE FROM `tabHas Role` WHERE parent=%s AND role='Organization Admin'", email)

    org_doc = frappe.get_doc("User Registration", registration_id)
    user_found = False
    for m in org_doc.members:
        if m.email == email:
            m.is_admin = int(is_admin)
            if int(is_admin) == 1:
                m.status = "Approved" 
            user_found = True
            break
            
    if user_found:
        org_doc.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.clear_cache(user=email)
        return {"status": "success", "message": f"User admin status {'enabled' if int(is_admin) == 1 else 'disabled'}."}
    else:
        return {"status": "error", "message": "Member not found in your organization record."}



@frappe.whitelist()
def get_org_users(registration_id):
    validate_org_access(registration_id)
    if not registration_id:
        return {"status": "error", "message": "Missing registration ID"}
    
    org_doc = frappe.db.get_value("User Registration", registration_id, ["approval_status", "work_email", "first_name", "last_name", "creation"], as_dict=True)
    org_status = org_doc.get("approval_status")
    org_email = org_doc.get("work_email")
    first_name = org_doc.get("first_name") or ""
    last_name = org_doc.get("last_name") or ""
    creation_date = org_doc.get("creation")
    
    members = frappe.get_all("Org User Item", 
        fields=["name1 as name", "email", "status", "creation", "is_admin"], 
        filters={"parent": registration_id, "parenttype": "User Registration"},
        order_by="creation desc"
    )
    
    filtered_members = [m for m in members if m.email != org_email]
    
    if org_status == "Pending Approval":
        for m in filtered_members:
            m.status = "Pending Approval"
            
    # Include the main registration admin
    admin_member = {
        "name": f"{first_name} {last_name}".strip() or "Organization Admin",
        "email": org_email,
        "status": "Approved" if org_status in ["Approved", "Active"] else "Pending Approval",
        "creation": creation_date,
        "is_admin": 1,
        "is_main_admin": 1
    }
    
    all_users = [admin_member] + filtered_members
            
    return {"status": "success", "users": all_users, "org_status": org_status}


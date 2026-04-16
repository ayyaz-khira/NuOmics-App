import frappe
from frappe import _
from nuomics_ai.nuomics_backend.security import validate_super_admin
from datetime import datetime
from dateutil.relativedelta import relativedelta

@frappe.whitelist()
def get_admin_stats():
    validate_super_admin()
    
    orgs = frappe.get_all("User Registration", 
        fields=["name", "organization_name", "organization_type", "first_name", "last_name", "work_email", "creation", "approval_status", "number_of_users"],
        order_by="creation desc"
    )
    
    for org in orgs:
        org.member_count = frappe.db.count("Org User Item", {"parent": org.name, "parenttype": "User Registration"}) + 1
        org.enabled_count = frappe.db.count("Org User Item", {"parent": org.name, "parenttype": "User Registration", "status": "Approved"})
        if org.approval_status in ["Approved", "Active"]:
            org.enabled_count += 1
        org.admin_name = f"{org.first_name} {org.last_name}"
        
    return {"status": "success", "organizations": orgs}

@frappe.whitelist()
def get_org_growth_data():
    validate_super_admin()
    
    end_date = datetime.now()
    start_date = end_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    query = """
        SELECT 
            DATE_FORMAT(creation, '%%b %%Y') as month,
            COUNT(*) as count,
            DATE_FORMAT(creation, '%%Y-%%m') as month_sort
        FROM `tabUser Registration`
        WHERE creation >= %s AND creation <= %s
        GROUP BY month_sort
        ORDER BY month_sort ASC
    """
    
    raw_data = frappe.db.sql(query, (start_date, end_date), as_dict=1)
    
    total_this_year = sum(item['count'] for item in raw_data)
    elapsed_months = end_date.month
    year_avg = round(total_this_year / elapsed_months, 1) if elapsed_months > 0 else 0
    
    labels = []
    values = []
    
    current = start_date
    while current <= end_date:
        m_label = current.strftime('%b %Y')
        m_sort = current.strftime('%Y-%m')
        labels.append(m_label)
        found = next((item['count'] for item in raw_data if item['month_sort'] == m_sort), 0)
        values.append(found)
        current += relativedelta(months=1)
    
    plan_data = frappe.db.sql("""
        SELECT organization_type, count(*) as count 
        FROM `tabUser Registration` 
        GROUP BY organization_type
    """, as_dict=1)
    
    plans = {
        "labels": [p.get("organization_type") or "Unspecified" for p in plan_data],
        "values": [p.get("count") for p in plan_data]
    }
    
    return {
        "status": "success",
        "data": {
            "labels": labels,
            "values": values,
            "year_avg": year_avg
        },
        "plans": plans
    }

@frappe.whitelist()
def get_system_alerts():
    validate_super_admin()
    alerts = frappe.get_all("System Alert",
        fields=["name", "alert_type", "message", "user", "creation", "is_read"],
        filters={"is_read": 0},
        order_by="creation desc",
        limit=20
    )
    return {"status": "success", "alerts": alerts}

@frappe.whitelist()
def mark_alert_as_read(alert_id):
    validate_super_admin()
    if frappe.db.exists("System Alert", alert_id):
        frappe.db.set_value("System Alert", alert_id, "is_read", 1)
        frappe.db.commit()
    return {"status": "success"}

@frappe.whitelist()
def clear_all_alerts():
    validate_super_admin()
    frappe.db.sql("UPDATE `tabSystem Alert` SET is_read = 1 WHERE is_read = 0")
    frappe.db.commit()
    return {"status": "success"}

@frappe.whitelist()
def get_all_users():
    validate_super_admin()
    users = frappe.get_all("User",
        fields=["name", "full_name", "email", "user_type", "creation", "enabled", "organization"],
        filters={
            "user_type": ["!=", "System User"],
            "name": ["!=", "Guest"]
        },
        order_by="creation desc"
    )
    
    final_users = []
    
    for u in users:
        status_val = None
        org_status = None
        is_main_admin = False
        
        if u.organization:
            status_val = frappe.db.get_value("Org User Item", {"user_ref": u.name, "parent": u.organization}, "status")
            reg_data = frappe.db.get_value("User Registration", u.organization, ["approval_status", "work_email"], as_dict=True)
            if reg_data:
                org_status = reg_data.get("approval_status")
                if reg_data.get("work_email") == u.email:
                    is_main_admin = True
            
        if not status_val and not org_status:
            reg_status = frappe.db.get_value("User Registration", {"work_email": u.email}, "approval_status")
            if reg_status:
                status_val = reg_status
                org_status = reg_status
                is_main_admin = True
                
        if org_status == "Pending Approval":
            status_val = "Pending Approval"
                
        u.actual_status = status_val or ("Approved" if u.enabled else "Disabled")
        u.is_org_admin = is_main_admin
        final_users.append(u)
        
    return {"status": "success", "users": final_users}

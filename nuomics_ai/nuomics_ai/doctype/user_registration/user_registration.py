import frappe
from frappe.model.document import Document
from nuomics_ai.nuomics_backend.utils import register_external_user , trigger_password_reset_email

class UserRegistration(Document):
    def validate(self):
        self._validate_capacity()
        self._validate_member_approvals()

    def _validate_member_approvals(self):
        # We only allow members to be set to "Approved" if the organization itself is approved.
        # This prevents enabling users of disabled or pending organizations.
        # If the organization is not approved, we sync the member status to match the org status automatically.
        if self.approval_status != "Approved":
            for member in self.get("members", []):
                if member.status == "Approved":
                    member.status = self.approval_status


    def _validate_capacity(self):
        capacity = 5
        if self.number_of_users:
            try:
                capacity = int(self.number_of_users)
            except (ValueError, TypeError):
                pass
        else:
            if self.organization_type == "Individual":
                capacity = 1
            elif self.organization_type:
                cap_str = self.organization_type.split('(')[-1].replace(')', '')
                if '+' in cap_str:
                    capacity = 999999
                elif '-' in cap_str:
                    try:
                        capacity = int(cap_str.split('-')[-1])
                    except ValueError:
                        capacity = 5
        
        current_count = len(self.get("members", [])) + 1
        if current_count > capacity:
            frappe.throw(f"Organization capacity exceeded. Limit is {capacity} users, but you are attempting to assign {current_count} users.", frappe.ValidationError)

    def on_update(self):
        old_doc = self.get_doc_before_save()
        old_status = old_doc.get("approval_status") if old_doc else None
        new_status = self.approval_status

        # Handle member-level user creation/enable/disable
        self._sync_members()

        # Handle org-level enable/disable
        self._update_user_access(new_status)

        # Send org-level emails only when transitioning TO Approved
        if old_status != "Approved" and new_status == "Approved":
            self._send_approval_emails()

    def _sync_members(self):
        for member in self.get("members", []):
            if not member.user_ref:
                member.user_ref = frappe.db.get_value("User", {"email": member.email})

            if member.status == "Approved":
                if not member.user_ref:
                    new_user = frappe.get_doc({
                        "doctype": "User",
                        "email": member.email,
                        "first_name": member.name1,
                        "enabled": 1,
                        "send_welcome_email": 0,
                        "user_type": "Website User",
                        "organization": self.name
                    })
                    new_user.insert(ignore_permissions=True)
                    member.user_ref = new_user.name
                    register_external_user(member.email, member.name1 or member.email)
                    trigger_password_reset_email(member.email)  
                    frappe.msgprint(f"User {member.email} created.")
                else:
                    user = frappe.get_doc("User", member.user_ref)
                    if not user.enabled:
                        user.enabled = 1
                        user.send_welcome_email = 0
                        user.save(ignore_permissions=True)
                        # user.send_welcome_mail_to_user()
                        frappe.msgprint(f"User {member.email} has been approved and enabled.")

            elif member.status == "Rejected" and member.user_ref:
                if frappe.db.get_value("User", member.user_ref, "enabled"):
                    frappe.db.set_value("User", member.user_ref, "enabled", 0)
                    frappe.msgprint(f"User {member.email} has been rejected and disabled.")

    def _update_user_access(self, status):
        # 1. Main admin user access
        # Admin is enabled only if status is "Approved"
        admin_enabled = 1 if status == "Approved" else 0
        if frappe.db.exists("User", self.work_email):
            frappe.db.set_value("User", self.work_email, "enabled", admin_enabled)

        # 2. Bulk Member handling (Only for disabling)
        if status != "Approved":
            # If the organization is disabled/rejected, we disable ALL linked users
            users = frappe.get_all(
                "User",
                filters={"organization": self.name, "name": ["!=", self.work_email]},
                fields=["name"]
            )
            for u in users:
                frappe.db.set_value("User", u.name, "enabled", 0)

            # Sync child table status to reflect the rejection/disabling
            for member in self.members:
                member.status = status
                if member.name:
                    frappe.db.set_value("Org User Item", member.name, "status", status)
        else:
            # When approving, we ONLY enable the main admin (done in step 1).
            # We do NOT touch other members; they must be approved individually
            # either via the child table or the portal dashboard.
            pass


    def _send_approval_emails(self):
    # 1. Admin User Handling only — members are handled by _sync_members()
        if not self.work_email:
            return

        if not frappe.db.exists("User", self.work_email):
            new_user = frappe.get_doc({
                "doctype": "User",
                "email": self.work_email,
                "first_name": self.first_name,
                "last_name": self.last_name,
                "enabled": 1,
                "send_welcome_email": 0,   # We send manually below
                "user_type": "Website User",
                "organization": self.name
            })
            new_user.insert(ignore_permissions=True)
            register_external_user(self.work_email, f"{self.first_name} {self.last_name}") 
            trigger_password_reset_email(self.work_email)
            new_user.add_roles("Organization Admin")
            # new_user.send_welcome_mail_to_user()
            frappe.msgprint(f"Core User account created for {self.work_email}")
        else:
            admin_user = frappe.get_doc("User", self.work_email)
            if not admin_user.enabled:
                admin_user.enabled = 1
                admin_user.organization = self.name
                admin_user.save(ignore_permissions=True)
                # admin_user.send_welcome_mail_to_user()
                frappe.msgprint(f"User {self.work_email} has been approved and enabled.")
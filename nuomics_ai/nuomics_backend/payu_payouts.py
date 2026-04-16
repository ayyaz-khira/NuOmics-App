import frappe
from frappe import _
import base64
import requests
import json

PAYU_PAYOUT_CLIENT_ID = "ccbb70745faad9c06092bb5c79bfd919b6f45fd454f34619d83920893e90ae6b"
PAYU_PAYOUT_CLIENT_SECRET = "534bcc8c227b0b5c4e0a62290e8faa17fd73e6d3dfa43f796572dda5044dd313" 
PAYU_PAYOUT_BASE_URL = "https://payout-api-uat.payu.in" 

@frappe.whitelist()
def get_payu_payout_token():
    auth_str = f"{PAYU_PAYOUT_CLIENT_ID}:{PAYU_PAYOUT_CLIENT_SECRET}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    
    url = f"{PAYU_PAYOUT_BASE_URL}/payout/v1/auth/token"
    headers = {
        "Authorization": f"Basic {encoded_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = "grant_type=client_credentials"
    
    try:
        response = requests.post(url, headers=headers, data=payload)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            frappe.log_error(response.text, "PayU Payout Token Error")
            return None
    except Exception as e:
        frappe.log_error(str(e), "PayU Payout Token Exception")
        return None

@frappe.whitelist()
def create_payout(member, amount, account_number, ifsc_code):
    token = get_payu_payout_token()
    if not token:
        frappe.throw(_("Could not authenticate with PayU Payouts API"))
        
    url = f"{PAYU_PAYOUT_BASE_URL}/payout/v1/transfer"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Generate unique transfer ID
    transfer_id = frappe.generate_hash(length=20)
    
    payload = {
        "transferId": transfer_id,
        "amount": str(amount),
        "beneficiaryAccountNumber": account_number,
        "beneficiaryIfscCode": ifsc_code,
        "beneficiaryName": frappe.db.get_value("Org User Item", member, "name1") or "Beneficiary",
        "purpose": "Salary/Payment",
        "beneficiaryEmail": frappe.db.get_value("Org User Item", member, "email"),
        "transferMode": "IMPS"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        res_json = response.json()
        
        # Save Payout Record
        payout = frappe.get_doc({
            "doctype": "PayU Payout",
            "member": member,
            "amount": amount,
            "account_number": account_number,
            "ifsc_code": ifsc_code,
            "payout_id": transfer_id,
            "full_response": json.dumps(res_json)
        })
        
        if response.status_code in [200, 202]:
            payout.status = "Pending" 
            payout.insert(ignore_permissions=True)
            frappe.db.commit()
            return {"status": "success", "message": "Payout initiated", "payout_id": transfer_id}
        else:
            payout.status = "Failed"
            payout.insert(ignore_permissions=True)
            frappe.db.commit()
            return {"status": "error", "message": res_json.get("message", "Payout Failed")}
            
    except Exception as e:
        frappe.log_error(str(e), "Payout API Exception")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def check_payout_status(payout_id):
    token = get_payu_payout_token()
    if not token: return None
    
    url = f"{PAYU_PAYOUT_BASE_URL}/payout/v1/transfer/status/{payout_id}"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(url, headers=headers)
        res_json = response.json()
        status = res_json.get("status") 
        
        # Update record
        pt_name = frappe.db.get_value("PayU Payout", {"payout_id": payout_id}, "name")
        if pt_name:
            pt = frappe.get_doc("PayU Payout", pt_name)
            if status == "SUCCESS": pt.status = "Success"
            elif status == "FAILURE": pt.status = "Failed"
            pt.full_response = json.dumps(res_json)
            pt.save(ignore_permissions=True)
            frappe.db.commit()
            
        return {"status": pt.status}
    except Exception as e:
        return None

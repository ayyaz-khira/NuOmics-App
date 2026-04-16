import frappe
from frappe import _
import hashlib
import json

PAYU_KEY = "SCcYkX"
PAYU_SALT = "Vyi137dOKlxYSVlaF1jWHInS7zoLBbOS"
PAYU_URL = "https://test.payu.in/_payment" 

def generate_payu_hash(data):
    # hashSequence = key|txnid|amount|productinfo|firstname|email|udf1|udf2|udf3|udf4|udf5||||||salt
    hash_args = [
        PAYU_KEY.strip(),
        data.get("txnid", ""),
        data.get("amount", ""),
        data.get("productinfo", ""),
        data.get("firstname", ""),
        data.get("email", ""),
        data.get("udf1", ""),
        data.get("udf2", ""),
        data.get("udf3", ""),
        data.get("udf4", ""),
        data.get("udf5", ""),
        "", "", "", "", "", 
        PAYU_SALT.strip()
    ]
    hash_string = "|".join(hash_args)
    return hashlib.sha512(hash_string.encode('utf-8')).hexdigest().lower()

def verify_payu_hash(data):
    # Hash reverse sequence for verifying response from PayU
    # salt|status|udf10|udf9|udf8|udf7|udf6|udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key
    response_hash_args = [
        PAYU_SALT.strip(),
        data.get("status", ""),
        data.get("udf10", ""),
        data.get("udf9", ""),
        data.get("udf8", ""),
        data.get("udf7", ""),
        data.get("udf6", ""),
        data.get("udf5", ""),
        data.get("udf4", ""),
        data.get("udf3", ""),
        data.get("udf2", ""),
        data.get("udf1", ""),
        data.get("email", ""),
        data.get("firstname", ""),
        data.get("productinfo", ""),
        data.get("amount", ""),
        data.get("txnid", ""),
        data.get("key", "")
    ]
    hash_string = "|".join(response_hash_args)
    calculated_hash = hashlib.sha512(hash_string.encode('utf-8')).hexdigest().lower()
    return calculated_hash == data.get("hash")

@frappe.whitelist(allow_guest=True)
def initiate_payment(user_registration_id, amount):
    if not frappe.db.exists("User Registration", user_registration_id):
        frappe.throw(_("Invalid registration ID"))
        
    try:
        amount_float = float(amount)
        if amount_float <= 0:
            frappe.throw(_("Amount must be greater than zero"))
    except ValueError:
        frappe.throw(_("Invalid amount format"))

    txnid = frappe.generate_hash(length=12) 
    
    pt = frappe.get_doc({
        "doctype": "Payment Transaction",
        "user_registration": user_registration_id,
        "amount": amount_float,
        "status": "Pending",
        "transaction_id": txnid,
        "payment_gateway": "PayU India"
    })
    pt.insert(ignore_permissions=True)
    frappe.db.commit()
    
    reg_doc = frappe.get_doc("User Registration", user_registration_id)
    
    phone = "".join(filter(str.isdigit, str(reg_doc.contact_number or "")))
    phone = str(phone)[-10:]
    
    firstname = "".join(filter(str.isalnum, (reg_doc.first_name or "User").split(" ")[0]))[:20]
    productinfo = "".join(filter(str.isalnum, (reg_doc.name or "Payment")))[:50]
        
    payment_data = {
        "key": PAYU_KEY.strip(),
        "txnid": txnid,
        "amount": "{:.2f}".format(float(amount)),
        "productinfo": productinfo,
        "firstname": firstname,
        "email": reg_doc.work_email,
        "phone": phone,
        "surl": frappe.utils.get_url("/api/method/nuomics_ai.nuomics_backend.payu_payments.payu_success"),
        "furl": frappe.utils.get_url("/api/method/nuomics_ai.nuomics_backend.payu_payments.payu_failure"),
        "udf1": "", "udf2": "", "udf3": "", "udf4": "", "udf5": "",
        "udf6": "", "udf7": "", "udf8": "", "udf9": "", "udf10": ""
    }
    
    payment_data["hash"] = generate_payu_hash(payment_data)
    
    return {
        "status": "success",
        "payment_url": PAYU_URL,
        "params": payment_data
    }

@frappe.whitelist(allow_guest=True)
def payu_success():
    data = frappe.local.form_dict
    
    if not verify_payu_hash(data):
        frappe.log_error(title="PayU Success Signature Fail", message=json.dumps(data, indent=4))
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/contact-us?error=invalid_signature"
        return

    txnid = data.get("txnid")
    if txnid:
        pt_name = frappe.db.get_value("Payment Transaction", {"transaction_id": txnid}, "name")
        if pt_name:
            pt = frappe.get_doc("Payment Transaction", pt_name)
            pt.status = "Success"
            pt.full_response = json.dumps(data)
            pt.save(ignore_permissions=True)
            
            reg = frappe.get_doc("User Registration", pt.user_registration)
            reg.payment_status = "True"
            reg.save(ignore_permissions=True)
            frappe.db.commit()
            
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = "/contact-us?status=received"
    return

@frappe.whitelist(allow_guest=True)
def payu_failure():
    data = frappe.local.form_dict
    
    if not verify_payu_hash(data):
        frappe.log_error(title="PayU Failure Signature Fail", message=json.dumps(data, indent=4))

    txnid = data.get("txnid")
    if txnid:
        pt_name = frappe.db.get_value("Payment Transaction", {"transaction_id": txnid}, "name")
        if pt_name:
            pt = frappe.get_doc("Payment Transaction", pt_name)
            pt.status = "Failed"
            pt.full_response = json.dumps(data)
            pt.save(ignore_permissions=True)
            frappe.db.commit()
            
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = "/contact-us?error=payment_failed"
    return

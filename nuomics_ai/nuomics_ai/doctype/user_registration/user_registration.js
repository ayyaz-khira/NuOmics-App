frappe.ui.form.on("User Registration", {
	refresh(frm) {

		// ✅ Approve All Button
		if (frappe.user_roles.includes("System Manager")) {
			frm.fields_dict['members'].grid.add_custom_button(__('Approve All Pending'), () => {
				let changed = false;
				frm.doc.members.forEach(m => {
					if (m.status === "Pending Approval") {
						frappe.model.set_value(m.doctype, m.name, "status", "Approved");
						changed = true;
					}
				});
				if (changed) {
					frm.save().then(() => {
						frappe.show_alert({ message: __('All pending users approved'), indicator: 'green' });
					});
				} else {
					frappe.msgprint(__('No pending users to approve'));
				}
			});
		}

		// 🔥 Razorpay Button
		if (!frm.is_new() && frm.doc.payment_status !== "True") {
			frm.add_custom_button('Pay Now', function () {
				payNow(frm);
			});
		}

		// Calculate amount if missing
		if (!frm.doc.amount && frm.doc.number_of_users) {
			frm.trigger("number_of_users");
		}
	},

	number_of_users(frm) {
		const price_per_user = 10;
		const total_amount = (frm.doc.number_of_users || 0) * price_per_user;
		frm.set_value("amount", total_amount);
	},

	organization_type(frm) {
		frm.trigger("number_of_users");
	}
});

function payNow(frm) {
	if (!frm.doc.amount || frm.doc.amount <= 0) {
		frappe.msgprint(__("Please enter a valid Number of Users to calculate the amount first."));
		return;
	}

	frappe.call({
		method: "razorpay_integration.api.payment.create_order_for_registration",
		args: {
			user_registration_id: frm.doc.name,
			amount: frm.doc.amount
		},
		callback: function (r) {
			const data = r.message;

			if (typeof Razorpay === "undefined") {
				frappe.msgprint("Razorpay SDK not loaded. Please ensure the razorpay_integration app is correctly set up.");
				return;
			}

			const options = {
				key: data.key_id,
				amount: data.amount,
				currency: data.currency,
				name: "NuOmics AI",
				description: "Registration Fee",
				order_id: data.order_id,
				prefill: {
					name: (frm.doc.first_name || "") + " " + (frm.doc.last_name || ""),
					email: frm.doc.work_email,
					contact: frm.doc.contact_number
				},
				handler: function (response) {
					frappe.show_progress(__("Verifying Payment"), 80, 100);
					frappe.call({
						method: "razorpay_integration.api.payment.verify_payment",
						args: {
							razorpay_order_id: response.razorpay_order_id,
							razorpay_payment_id: response.razorpay_payment_id,
							razorpay_signature: response.razorpay_signature,
							log_name: data.log_name
						},
						callback: function (res) {
							frappe.hide_progress();
							if (res.message && res.message.success) {
								frappe.show_alert({ message: __('Payment Successful'), indicator: 'green' });
								frm.reload_doc();
							}
						}
					});
				}
			};

			const rzp = new Razorpay(options);
			rzp.open();
		}
	});
}
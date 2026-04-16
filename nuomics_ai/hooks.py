app_name = "nuomics_ai"
app_title = "Nuomics Ai"
app_publisher = "Micro Crispr Ltd"
app_description = "Nuomics AI is an advanced, AI-powered business platform designed to streamline operations, enhance lead generation, and provide centralized management through intelligent automation and scalable backend systems"
app_email = "amit.bhargav@microcrispr.com"
app_license = "mit"

fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [
            ["dt", "=", "User"],
            ["fieldname", "=", "organization"]
        ]
    }
]

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "nuomics_ai",
# 		"logo": "/assets/nuomics_ai/logo.png",
# 		"title": "Nuomics Ai",
# 		"route": "/nuomics_ai",
# 		"has_permission": "nuomics_ai.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/nuomics_ai/css/nuomics_ai.css"
# app_include_js = "/assets/nuomics_ai/js/nuomics_ai.js"

app_include_js = [
    "https://checkout.razorpay.com/v1/checkout.js"
]

# include js, css files in header of web template
# web_include_css = "/assets/nuomics_ai/css/nuomics_ai.css"
# web_include_js = "/assets/nuomics_ai/js/nuomics_ai.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "nuomics_ai/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "nuomics_ai/public/icons.svg"

# Home Pages
# ----------

role_home_page = {
    "Organization Admin": "dashboard",
    "System Manager": "admin/dashboard"
}

# Permissions
# -----------

permission_query_conditions = {
	"User": "nuomics_ai.nuomics_backend.api.get_user_permission_query",
}

# Document Events
# ---------------



# Website Route Rules
# -------------------

website_route_rules = [
    {
        "from_route": "/home", "to_route": "dashboard"
    },
    {
        "from_route": "/update-password", "to_route": "auth/update-password"
    }
]

# Request Hooks
# -------------

on_login = "nuomics_ai.nuomics_backend.api.redirect_after_login"
before_request = ["nuomics_ai.nuomics_backend.api.validate_org_admin_route"]


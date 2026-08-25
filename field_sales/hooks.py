app_name = "field_sales"
app_title = "Field Sales"
app_publisher = "Edubild Technologies"
app_description = "Field sales, beat planning and customer visit management for Frappe"
app_email = "info@edubild.in"
app_license = "mit"

# Apps
# ------------------

# field_sales is not installable on a bare Frappe site: it links against
# Customer, Item, Territory, Sales Order and Pricing Rule (erpnext), and
# Employee Checkin for attendance (hrms). Declaring this is what makes
# `bench install-app field_sales` pull them in automatically instead of
# failing partway through the first doctype that references one.
required_apps = ["erpnext", "hrms"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "field_sales",
# 		"logo": "/assets/field_sales/logo.png",
# 		"title": "Field Sales",
# 		"route": "/field_sales",
# 		"has_permission": "field_sales.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/field_sales/css/field_sales.css"
# app_include_js = "/assets/field_sales/js/field_sales.js"

# include js, css files in header of web template
# web_include_css = "/assets/field_sales/css/field_sales.css"
# web_include_js = "/assets/field_sales/js/field_sales.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "field_sales/public/scss/website"

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
# app_include_icons = "field_sales/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# The Field Sales PWA lives at /field_sales_app; a rep or manager signing in
# is routed straight there rather than to the desk, which they never need.
#
# The page is named "field_sales_app", NOT "app" - Frappe core itself owns a
# www page literally named "app" (the desk shell, apps/frappe/frappe/www/app.py).
# Naming this one "app" too let it silently shadow the real desk for every
# user, since field_sales loads after frappe - www/app.py was renamed to
# www/field_sales_app.py to fix this.
website_route_rules = [
    # the bare path (no trailing segment) needs its own rule - Werkzeug's
    # <path:...> converter requires at least one character, so it never
    # matches "/field_sales_app" on its own, only "/field_sales_app/...".
    # Without this, the SPA's own root route ("/") and role_home_page below
    # both 404 before the Vue app ever loads.
    {"from_route": "/field_sales_app", "to_route": "field_sales_app"},
    {"from_route": "/field_sales_app/<path:app_path>", "to_route": "field_sales_app"},
]

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }
role_home_page = {
    "Sales Executive App": "/field_sales_app",
}

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "field_sales.utils.jinja_methods",
# 	"filters": "field_sales.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "field_sales.install.before_install"
# after_install = "field_sales.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "field_sales.uninstall.before_uninstall"
# after_uninstall = "field_sales.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "field_sales.utils.before_app_install"
# after_app_install = "field_sales.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "field_sales.utils.before_app_uninstall"
# after_app_uninstall = "field_sales.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "field_sales.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"field_sales.tasks.all"
# 	],
# 	"daily": [
# 		"field_sales.tasks.daily"
# 	],
# 	"hourly": [
# 		"field_sales.tasks.hourly"
# 	],
# 	"weekly": [
# 		"field_sales.tasks.weekly"
# 	],
# 	"monthly": [
# 		"field_sales.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "field_sales.install.before_tests"

# Removes a stale Property Setter that a legacy app installed on this site
# (mohan_impex) keeps re-shipping in its fixtures, which otherwise breaks
# every Notification Log insert after each migrate - see migrations.py.
after_migrate = "field_sales.migrations.after_migrate"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "field_sales.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "field_sales.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["field_sales.utils.before_request"]
# after_request = ["field_sales.utils.after_request"]

# Job Events
# ----------
# before_job = ["field_sales.utils.before_job"]
# after_job = ["field_sales.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"field_sales.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

# Server-side pricing enforcement. The rate a client submits is a suggestion;
# the server recalculates it on every save, whatever the origin.
# This must run on before_validate: the controller computes amounts and totals
# during validate, so correcting a rate afterwards would leave them stale.
doc_events = {
	"Sales Order": {
		"before_validate": "field_sales.pricing.enforce_sales_order_rates",
	},
}

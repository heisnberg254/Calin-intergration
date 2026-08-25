app_name = "upande_hydrax"
app_title = "Upande Hydrax"
app_publisher = "edwin@upande.com"
app_description = "This is for monitoring the calin water meter"
app_email = "edwin@upande.com"
app_license = "mit"

# Send non-GET requests for this app's endpoints as native `application/json`
# bodies instead of form-encoded, per-key JSON-stringified values.
use_json_request_body = True

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "upande_hydrax",
# 		"logo": "/assets/upande_hydrax/logo.png",
# 		"title": "Upande Hydrax",
# 		"route": "/upande_hydrax",
# 		"has_permission": "upande_hydrax.api.permission.has_app_permission",
# 	}
# ]

# Companion apps that extend a host app (instead of taking their own apps-screen icon) can pin
# their workspaces into the host app's workspace dock (rail) with this hook. Declaring it keeps
# the app off the apps screen, so it takes precedence over any add_to_apps_screen above. Who can
# see a pinned workspace is controlled by that workspace's own Roles table.
# add_to_workspace_dock = [
# 	{
# 		"app": "erpnext",
# 		"workspace": "My Workspace",
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/upande_hydrax/css/upande_hydrax.css"
# app_include_js = "/assets/upande_hydrax/js/upande_hydrax.js"

# include js, css files in header of web template
# web_include_css = "/assets/upande_hydrax/css/upande_hydrax.css"
# web_include_js = "/assets/upande_hydrax/js/upande_hydrax.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "upande_hydrax/public/scss/website"

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
# app_include_icons = "upande_hydrax/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Setup Wizard
# ------------

# open a fresh site's setup in this app's own UI instead of the desk wizard.
# must be a non-desk route (not under /desk or /app); to customize setup within
# desk, use setup_wizard_stages / setup_wizard_complete instead.
# setup_wizard_url = "/upande_hydrax/setup"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "upande_hydrax.utils.jinja_methods",
# 	"filters": "upande_hydrax.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "upande_hydrax.install.before_install"
# after_install = "upande_hydrax.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "upande_hydrax.uninstall.before_uninstall"
# after_uninstall = "upande_hydrax.uninstall.after_uninstall"

# Disable / Enable
# ----------------
# Called when this app is logically disabled or re-enabled on a site,
# without uninstalling it. Use this to hide/restore fields this app adds
# to other apps' doctypes.

# before_disable = "upande_hydrax.uninstall.before_disable"
# after_disable = "upande_hydrax.uninstall.after_disable"
# before_enable = "upande_hydrax.install.before_enable"
# after_enable = "upande_hydrax.install.after_enable"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "upande_hydrax.utils.before_app_install"
# after_app_install = "upande_hydrax.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "upande_hydrax.utils.before_app_uninstall"
# after_app_uninstall = "upande_hydrax.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "upande_hydrax.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "upande_hydrax.notifications.get_notification_config"

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
# 		"upande_hydrax.tasks.all"
# 	],
# 	"daily": [
# 		"upande_hydrax.tasks.daily"
# 	],
# 	"hourly": [
# 		"upande_hydrax.tasks.hourly"
# 	],
# 	"weekly": [
# 		"upande_hydrax.tasks.weekly"
# 	],
# 	"monthly": [
# 		"upande_hydrax.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "upande_hydrax.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "upande_hydrax.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "upande_hydrax.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "upande_hydrax.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["upande_hydrax.utils.before_request"]
# after_request = ["upande_hydrax.utils.after_request"]

# Job Events
# ----------
# before_job = ["upande_hydrax.utils.before_job"]
# after_job = ["upande_hydrax.utils.after_job"]

# after_file_upload = ["upande_hydrax.utils.after_file_upload"]

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
# 	"upande_hydrax.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
export_python_type_annotations = True

# Require all whitelisted methods to have type annotations
require_type_annotated_api_methods = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

# hooks.py — this file holds everything, both jobs living together
scheduler_events = {
    "hourly": [
        "upande_hydrax.upande_hydrax.tasks.sync_all_dcus",
        "upande_hydrax.upande_hydrax.tasks.sync_all_water_meters",
        "upande_hydrax.upande_hydrax.tasks.sync_all_meter_readings",
        "upande_hydrax.upande_hydrax.tasks.sync_all_token_records"
    ]
}

fixtures = [
    {"doctype": "Workspace", "filters": [["module", "=", "Upande Hydrax"]]},
    {"doctype": "Custom HTML Block", "filters": [["name", "in", ["Upande Sensors"]]]},
    {"doctype": "Client Script", "filters": [["dt", "in", ["DCU", "Token Record", "Water Meter", "Meter Reading"]]]}
]
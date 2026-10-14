"""What each part of the admin needs (doc 06). Staff get the permissions of their staff role; the
``admin`` user role has every permission plus the admin-only areas (settings, fee schedules, team,
roles and audit), which no staff role can be given."""

# Stable keys, grouped as the roles matrix shows them. Adding one here makes it assignable.
PERMISSIONS: dict[str, tuple[str, ...]] = {
    "users": ("users.view", "users.suspend", "users.suspend_long"),
    "reports": ("reports.manage", "help.manage"),
    "drivers": ("drivers.view", "drivers.review", "drivers.suspend"),
    "rides": ("rides.view", "rides.cancel", "live.view"),
    "quality": ("quality.view", "quality.manage"),
    "risk": ("risk.view", "risk.manage"),
    "safety": ("safety.view", "safety.manage"),
    "promotions": ("promotions.view", "promotions.manage"),
    "rates": ("rates.view", "rates.manage"),
    "notifications": ("notifications.send",),
    "wallet": ("wallet.view", "top_ups.view", "top_ups.manage", "transfers.view", "wallet.adjust"),
    "subscriptions": ("subscriptions.view", "subscriptions.manage"),
    "finance": ("finance.view", "finance.export", "finance.close"),
    "analytics": ("analytics.view", "analytics.export"),
    "system": ("dashboard.view", "system.view", "config.view"),
    "releases": ("releases.view", "releases.manage"),
    "app_control": (
        "app_status.view",
        "app_status.manage",
        "flags.view",
        "flags.manage",
        "announcements.view",
        "announcements.manage",
    ),
}
ALL_PERMISSIONS: frozenset[str] = frozenset(p for group in PERMISSIONS.values() for p in group)

# Suspensions longer than this (or with no end) need ``users.suspend_long``.
SHORT_SUSPENSION_DAYS = 7

# Roles created by the migration; an admin edits them from the Roles page.
DEFAULT_ROLES: dict[str, tuple[str, tuple[str, ...]]] = {
    "soporte": (
        "Soporte",
        (
            "dashboard.view",
            "users.view",
            "users.suspend",
            "reports.manage",
            "help.manage",
            "rides.view",
            "drivers.view",
            "live.view",
            "safety.view",
            "safety.manage",
        ),
    ),
    "verificador": (
        "Verificador",
        ("dashboard.view", "drivers.view", "drivers.review", "users.view"),
    ),
    "finanzas": (
        "Finanzas",
        (
            "dashboard.view",
            "users.view",
            "wallet.view",
            "top_ups.view",
            "top_ups.manage",
            "transfers.view",
            "wallet.adjust",
            "subscriptions.view",
            "subscriptions.manage",
            "finance.view",
            "finance.export",
            "finance.close",
            "rates.view",
        ),
    ),
    "operaciones": (
        "Operaciones",
        (
            "dashboard.view",
            "users.view",
            "drivers.view",
            "rides.view",
            "rides.cancel",
            "live.view",
            "promotions.view",
            "promotions.manage",
            "rates.view",
            "rates.manage",
            "notifications.send",
            "system.view",
            "config.view",
            "app_status.view",
            "app_status.manage",
            "flags.view",
            "announcements.view",
            "announcements.manage",
            "safety.view",
            "safety.manage",
        ),
    ),
}

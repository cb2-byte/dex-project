"""
Whale Sentry Skill Package
On-chain whale monitoring and alerting system using free APIs.
"""
from .whale_sentry import (
    WhaleSentrySkill,
    create_skill,
    whale_sentry_add_wallet,
    whale_sentry_remove_wallet,
    whale_sentry_list_wallets,
    whale_sentry_start_monitoring,
    whale_sentry_stop_monitoring,
    whale_sentry_get_alerts,
    whale_sentry_get_summary,
    whale_sentry_get_stats,
    whale_sentry_set_threshold,
    whale_sentry_get_wallet,
    register_skill,
    SKILL_METADATA,
)

__version__ = "1.0.0"
__author__ = "penny"
__all__ = [
    "WhaleSentrySkill",
    "create_skill",
    "whale_sentry_add_wallet",
    "whale_sentry_remove_wallet",
    "whale_sentry_list_wallets",
    "whale_sentry_start_monitoring",
    "whale_sentry_stop_monitoring",
    "whale_sentry_get_alerts",
    "whale_sentry_get_summary",
    "whale_sentry_get_stats",
    "whale_sentry_set_threshold",
    "whale_sentry_get_wallet",
    "register_skill",
    "SKILL_METADATA",
]

# Skill metadata for OpenClaw
__skill_name__ = "whale-sentry"
__skill_version__ = "1.0.0"
__skill_description__ = "On-chain whale monitoring and alerting system using free APIs"
__skill_author__ = "penny"
__skill_tags__ = ["crypto", "monitoring", "whale-tracking", "defi", "telegram", "alerts"]
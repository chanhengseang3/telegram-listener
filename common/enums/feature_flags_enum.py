from enum import Enum


class FeatureFlags(Enum):
    """
    Feature flags for group packages to enable/disable additional features
    """
    
    # Report features
    WEEKLY_MONTHLY_REPORTS = "weekly_monthly_reports"
    DAILY_BUSINESS_REPORTS = "daily_business_reports"
    ADVANCED_ANALYTICS = "advanced_analytics"
    
    # Transaction features
    TRANSACTION_ANNOTATION = "transaction_annotation"
    MULTI_CURRENCY = "multi_currency"
    CUSTOM_EXPORT = "custom_export"
    
    # Business features
    SHIFT_MANAGEMENT = "shift_management"
    AUTOMATED_REPORTS = "automated_reports"
    API_ACCESS = "api_access"
    
    # Premium features
    PREMIUM_SUPPORT = "premium_support"
    CUSTOM_BRANDING = "custom_branding"
    BULK_OPERATIONS = "bulk_operations"
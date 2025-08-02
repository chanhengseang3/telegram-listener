"""
Setup script for enabling weekly/monthly reports feature for business groups

This script demonstrates how to enable the weekly_monthly_reports feature flag
for business groups to access the new weekly and monthly reporting functionality.

Usage:
    python setup_weekly_monthly_reports.py --chat-id 123456789 --enable
    python setup_weekly_monthly_reports.py --chat-id 123456789 --disable
    python setup_weekly_monthly_reports.py --list-all
"""

import argparse
import asyncio

from common.enums import FeatureFlags
from services.group_package_service import GroupPackageService


async def enable_weekly_monthly_reports(chat_id: int):
    """Enable weekly/monthly reports for a chat"""
    service = GroupPackageService()
    
    try:
        # Enable the feature flag
        result = await service.set_feature_flag(chat_id, FeatureFlags.WEEKLY_MONTHLY_REPORTS.value, True)
        
        if result:
            print(f"✅ Weekly/Monthly reports enabled for chat ID: {chat_id}")
            
            # Show current feature flags
            flags = await service.get_all_feature_flags(chat_id)
            print(f"📊 Current feature flags: {flags}")
        else:
            print(f"❌ Failed to enable feature for chat ID: {chat_id}")
            print("   Make sure the chat exists and has a group package")
            
    except Exception as e:
        print(f"❌ Error: {e}")

async def disable_weekly_monthly_reports(chat_id: int):
    """Disable weekly/monthly reports for a chat"""
    service = GroupPackageService()
    
    try:
        # Disable the feature flag
        result = await service.set_feature_flag(chat_id, FeatureFlags.WEEKLY_MONTHLY_REPORTS.value, False)
        
        if result:
            print(f"✅ Weekly/Monthly reports disabled for chat ID: {chat_id}")
            
            # Show current feature flags
            flags = await service.get_all_feature_flags(chat_id)
            print(f"📊 Current feature flags: {flags}")
        else:
            print(f"❌ Failed to disable feature for chat ID: {chat_id}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

async def check_feature_status(chat_id: int):
    """Check if weekly/monthly reports are enabled for a chat"""
    service = GroupPackageService()
    
    try:
        # Check if feature is enabled
        is_enabled = await service.has_feature(chat_id, FeatureFlags.WEEKLY_MONTHLY_REPORTS.value)
        
        package = await service.get_package_by_chat_id(chat_id)
        if not package:
            print(f"❌ No package found for chat ID: {chat_id}")
            return
        
        print(f"📊 Chat ID: {chat_id}")
        print(f"📦 Package: {package.package.value}")
        print(f"🎯 Weekly/Monthly Reports: {'✅ Enabled' if is_enabled else '❌ Disabled'}")
        
        # Show all feature flags
        flags = await service.get_all_feature_flags(chat_id)
        if flags:
            print(f"🔧 All feature flags: {flags}")
        else:
            print("🔧 No feature flags set")
            
    except Exception as e:
        print(f"❌ Error: {e}")

async def list_all_business_chats():
    """List all business chats and their feature flag status"""
    # This would require additional database queries
    # For now, show the concept
    print("📋 Business Chats with Weekly/Monthly Reports:")
    print("   (This would list all business packages and their feature flags)")
    print("   Implementation would require additional database queries")

async def setup_example_business_group():
    """Setup an example business group with weekly/monthly reports"""
    service = GroupPackageService()
    
    # Example chat ID (replace with actual business chat ID)
    example_chat_id = 123456789
    
    print(f"🔧 Setting up example business group: {example_chat_id}")
    
    try:
        # Enable multiple business features
        business_features = {
            FeatureFlags.WEEKLY_MONTHLY_REPORTS.value: True,
            FeatureFlags.TRANSACTION_ANNOTATION.value: True,
            FeatureFlags.ADVANCED_ANALYTICS.value: True,
            FeatureFlags.SHIFT_MANAGEMENT.value: True,
        }
        
        result = await service.update_feature_flags(example_chat_id, business_features)
        
        if result:
            print("✅ Example business group setup completed!")
            print(f"📊 Enabled features: {business_features}")
        else:
            print("❌ Failed to setup example business group")
            print("   Make sure the chat exists and has a group package")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Manage weekly/monthly reports feature for business groups")
    parser.add_argument("--chat-id", type=int, help="Chat ID to manage")
    parser.add_argument("--enable", action="store_true", help="Enable weekly/monthly reports")
    parser.add_argument("--disable", action="store_true", help="Disable weekly/monthly reports")
    parser.add_argument("--check", action="store_true", help="Check feature status")
    parser.add_argument("--list-all", action="store_true", help="List all business chats")
    parser.add_argument("--setup-example", action="store_true", help="Setup example business group")
    
    args = parser.parse_args()
    
    if args.enable and args.chat_id:
        asyncio.run(enable_weekly_monthly_reports(args.chat_id))
    elif args.disable and args.chat_id:
        asyncio.run(disable_weekly_monthly_reports(args.chat_id))
    elif args.check and args.chat_id:
        asyncio.run(check_feature_status(args.chat_id))
    elif args.list_all:
        asyncio.run(list_all_business_chats())
    elif args.setup_example:
        asyncio.run(setup_example_business_group())
    else:
        print("Usage examples:")
        print("  python setup_weekly_monthly_reports.py --chat-id 123456789 --enable")
        print("  python setup_weekly_monthly_reports.py --chat-id 123456789 --check")
        print("  python setup_weekly_monthly_reports.py --setup-example")

if __name__ == "__main__":
    main()
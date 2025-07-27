import asyncio
from datetime import timedelta

import pytz
import schedule
from sqlalchemy import and_

from common.enums.service_package_enum import ServicePackage
from config import get_db_session
from helper import force_log, DateUtils
from models.group_package_model import GroupPackage
from services.group_package_service import GroupPackageService


class TrialExpiryScheduler:
    def __init__(self):
        self.group_package_service = GroupPackageService()

    @staticmethod
    def convert_expired_trials_to_free():
        """
        Find groups with trial packages that have expired (7+ days) without payment
        and convert them to free packages.
        """
        force_log("Trial Expiry Scheduler - Converting expired trials to free packages", "trial_expiry_scheduler")
        try:
            with get_db_session() as session:
                # Calculate the cutoff date (7 days ago) in Cambodia timezone
                cutoff_date = DateUtils.now() - timedelta(days=7)

                # Find trial groups that started 7+ days ago and are not paid
                expired_trials = session.query(GroupPackage).filter(
                    and_(
                        GroupPackage.package == ServicePackage.TRIAL,
                        GroupPackage.is_paid == False,
                        GroupPackage.package_start_date <= cutoff_date
                    )
                ).all()

                converted_count = 0

                for group_package in expired_trials:
                    try:
                        # Update package to FREE
                        group_package.package = ServicePackage.FREE
                        group_package.package_start_date = DateUtils.now()
                        group_package.package_end_date = None  # Free packages don't expire

                        session.commit()
                        converted_count += 1

                        force_log(
                            f"Converted trial group {group_package.chat_group_id} to FREE package. "
                            "Expiry Scheduler"
                        )

                    except Exception as e:
                        session.rollback()
                        force_log(
                            f"Failed to convert group {group_package.chat_group_id} to FREE: {str(e)}"
                        )

                if converted_count > 0:
                    force_log(f"Successfully converted {converted_count} expired trial groups to FREE packages")
                else:
                    force_log("No expired trial groups found to convert")

        except Exception as e:
            force_log(f"Error in convert_expired_trials_to_free: {str(e)}")

    async def start_scheduler(self):
        """
        Start the scheduler to run the trial expiry job.
        """
        # Schedule the job to run daily at 1:00 AM Cambodia time
        cambodia_tz = pytz.timezone('Asia/Phnom_Penh')
        schedule.every().day.at("01:00", cambodia_tz).do(self.convert_expired_trials_to_free)

        # For testing purposes, you can also run it every minute:
        # schedule.every().minute.do(self.convert_expired_trials_to_free)

        force_log("Trial expiry scheduler started. Job will run daily at 9:00 AM Cambodia time (Asia/Phnom_Penh)")

        try:
            while True:
                schedule.run_pending()
                await asyncio.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            force_log("Trial expiry scheduler stopped by user")
        except Exception as e:
            force_log(f"Error in scheduler: {str(e)}")

"""Scheduler pentru termene legale."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from prognoza.config.settings import DeadlineConfig, PREInfo


class DeadlineMonitor:
    """Programeaza joburi pentru notificari si raportari obligatorii."""

    def __init__(self, pre: PREInfo, deadlines: DeadlineConfig) -> None:
        self._pre = pre
        self._deadlines = deadlines
        self._scheduler = BackgroundScheduler(timezone=pre.timezone)

    def schedule_d_minus_one(self, job: Callable[[], None]) -> None:
        reminder_time = (datetime.combine(datetime.today(), self._deadlines.d_minus_1_notification)
                         - timedelta(minutes=self._deadlines.reminder_offset_minutes)).time()
        trigger = CronTrigger(hour=reminder_time.hour, minute=reminder_time.minute)
        self._scheduler.add_job(job, trigger, name="generate_notification_d_minus_1")

    def schedule_monthly_anre(self, job: Callable[[], None]) -> None:
        trigger = CronTrigger(day=self._deadlines.monthly_anre_day,
                              hour=self._deadlines.monthly_anre_hour,
                              timezone=self._pre.timezone)
        self._scheduler.add_job(job, trigger, name="generate_anre_monthly_report")

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown()

    def get_jobs(self):
        return self._scheduler.get_jobs()

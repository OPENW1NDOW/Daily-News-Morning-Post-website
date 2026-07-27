"""调度器配置测试：cron 每日 08:00 Asia/Shanghai，misfire 宽限 3600s。不运行事件循环。"""
import asyncio

from apscheduler.triggers.cron import CronTrigger

from app import scheduler as scheduler_mod


def test_daily_job_cron_config():
    # AsyncIOScheduler.start() 需要一个已设置的事件循环，但断言配置无需运行它
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        scheduler_mod.start_scheduler()

        job = scheduler_mod.scheduler.get_job("daily_pipeline")
        assert job is not None
        assert job.misfire_grace_time == 3600

        trigger = job.trigger
        assert isinstance(trigger, CronTrigger)
        assert str(trigger.timezone) == "Asia/Shanghai"
        fields = {f.name: str(f) for f in trigger.fields}
        assert fields["hour"] == "8"
        assert fields["minute"] == "0"
    finally:
        scheduler_mod.stop_scheduler()
        asyncio.set_event_loop(None)
        loop.close()

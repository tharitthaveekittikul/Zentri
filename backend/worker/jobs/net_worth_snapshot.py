from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.models.net_worth_snapshot import NetWorthSnapshot
from app.models.user import User
from app.services.net_worth_snapshot import backfill_snapshots, take_snapshot
from app.services.pipeline import create_log, finish_log

logger = get_logger(__name__)


async def job_snapshot_net_worth(ctx: dict) -> dict:
    """ARQ job: take daily net worth snapshots for all users."""
    SessionLocal: async_sessionmaker = ctx["session_factory"]
    async with SessionLocal() as db:
        log = await create_log(db, "snapshot_net_worth")
        try:
            users = list((await db.execute(select(User))).scalars().all())
            total_written = 0

            for user in users:
                has_any = (await db.execute(
                    select(NetWorthSnapshot).where(NetWorthSnapshot.user_id == user.id).limit(1)
                )).scalar_one_or_none()

                if has_any is None:
                    written = await backfill_snapshots(db, user.id)
                    total_written += written
                else:
                    yesterday = date.today() - timedelta(days=1)
                    snap = await take_snapshot(db, user.id, yesterday)
                    if snap is not None:
                        total_written += 1

            await finish_log(db, log, success=True)
            logger.info("snapshot_net_worth done users=%d snapshots_written=%d", len(users), total_written)
            return {"users": len(users), "snapshots_written": total_written}
        except Exception as e:
            logger.exception("job_snapshot_net_worth failed: %s", e)
            await finish_log(db, log, success=False, error_message=str(e))
            raise

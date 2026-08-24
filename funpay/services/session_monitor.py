import asyncio
import time
from typing import Optional, Callable
from utils.logger import logger
from funpay.client import FunPayClient

class SessionMonitorService:
    """
    Periodic session health checker that verifies the FunPay session is alive.
    If the golden_key expires or is revoked, it immediately fires an alert
    to Telegram admins with an action button to update the key without downtime.
    """

    def __init__(
        self,
        client: FunPayClient,
        on_session_expired_callback: Optional[Callable] = None,
        check_interval_seconds: int = 180,
    ):
        self.client = client
        self.on_session_expired = on_session_expired_callback
        self.check_interval = check_interval_seconds
        self.is_running = False
        self.last_health_status: bool = True
        self.last_checked_at: float = 0
        self._task: Optional[asyncio.Task] = None

    async def check_now(self) -> bool:
        """Performs immediate session health check."""
        try:
            profile = await self.client.check_auth()
            is_valid = bool(profile and profile.is_authenticated)
            self.last_checked_at = time.time()

            if not is_valid and self.last_health_status:
                self.last_health_status = False
                logger.error("🚨 [Session Monitor] FunPay Golden Key session has EXPIRED or is invalid!")
                if self.on_session_expired:
                    await self.on_session_expired()
            elif is_valid and not self.last_health_status:
                self.last_health_status = True
                logger.info("✅ [Session Monitor] FunPay session successfully restored and active!")

            return is_valid
        except Exception as e:
            logger.warning(f"[Session Monitor] Check failed: {e}")
            return self.last_health_status

    async def _loop(self) -> None:
        logger.info(f"🔄 Session Health Monitor started (Interval: {self.check_interval}s).")
        while self.is_running:
            try:
                await self.check_now()
            except Exception as e:
                logger.error(f"Error in session monitor loop: {e}")
            await asyncio.sleep(self.check_interval)

    def start(self) -> None:
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()

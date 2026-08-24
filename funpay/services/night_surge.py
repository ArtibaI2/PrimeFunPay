import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from config.settings import settings
from utils.logger import logger

class NightSurgeService:
    """
    Automated night-surge pricing engine.
    Boosts product prices by customizable percentage (+15% - +30%) during 23:00 - 07:00
    when competitors sleep and buyers need instant 24/7 delivery.
    """

    def __init__(self, surge_percent: Optional[float] = None):
        self.surge_percent = surge_percent or settings.NIGHT_SURGE_PERCENT
        self._is_night_prev: Optional[bool] = None

    def get_moscow_hour(self) -> int:
        """Returns current hour in Moscow time (UTC+3)."""
        moscow_now = datetime.now(timezone(timedelta(hours=3)))
        return moscow_now.hour

    def is_night_time(self, current_hour: Optional[int] = None) -> bool:
        """Determines whether current hour falls in night surge window (23:00 - 07:00 MSK)."""
        hour = current_hour if current_hour is not None else self.get_moscow_hour()
        return hour >= 23 or hour < 7

    def calculate_surge_price(self, base_price: float) -> float:
        """Calculates adjusted price with night surge markup."""
        if not settings.ENABLE_NIGHT_SURGE or not self.is_night_time():
            return base_price

        markup = base_price * (self.surge_percent / 100.0)
        surged = round(base_price + markup, 2)
        return surged

    def check_state_transition(self) -> Optional[str]:
        """Checks if we entered or exited night surge window to log notifications."""
        current_night = self.is_night_time()
        if self._is_night_prev is None:
            self._is_night_prev = current_night
            return None

        if current_night and not self._is_night_prev:
            self._is_night_prev = True
            logger.info(f"🌙 [Night Surge] Ночной режим АКТИВИРОВАН (23:00 MSK): наценка +{self.surge_percent}% к продажам.")
            return "activated"
        elif not current_night and self._is_night_prev:
            self._is_night_prev = False
            logger.info("☀️ [Night Surge] Ночной режим ЗАВЕРШЕН (07:00 MSK): стандартные дневные цены восстановлены.")
            return "deactivated"
        return None

    def get_status_info(self) -> dict:
        """Returns current surge status."""
        active = settings.ENABLE_NIGHT_SURGE and self.is_night_time()
        return {
            "enabled_in_settings": settings.ENABLE_NIGHT_SURGE,
            "is_night_hours": self.is_night_time(),
            "is_active_now": active,
            "current_hour_msk": self.get_moscow_hour(),
            "surge_percent": self.surge_percent,
        }

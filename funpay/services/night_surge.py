from datetime import datetime
from typing import Optional
from config.settings import settings
from utils.logger import logger

class NightSurgeService:
    def __init__(self, surge_percent: Optional[float] = None):
        self.surge_percent = surge_percent or settings.NIGHT_SURGE_PERCENT

    def is_night_time(self, current_hour: Optional[int] = None) -> bool:
        """Determines whether current hour falls in night surge window (23:00 - 07:00)."""
        hour = current_hour if current_hour is not None else datetime.now().hour
        return hour >= 23 or hour < 7

    def calculate_surge_price(self, base_price: float) -> float:
        """Calculates adjusted price with night surge markup."""
        if not settings.ENABLE_NIGHT_SURGE or not self.is_night_time():
            return base_price

        markup = base_price * (self.surge_percent / 100.0)
        surged = round(base_price + markup, 2)
        return surged

    def get_status_info(self) -> dict:
        """Returns current surge status."""
        active = settings.ENABLE_NIGHT_SURGE and self.is_night_time()
        return {
            "enabled_in_settings": settings.ENABLE_NIGHT_SURGE,
            "is_night_hours": self.is_night_time(),
            "is_active_now": active,
            "surge_percent": self.surge_percent,
        }

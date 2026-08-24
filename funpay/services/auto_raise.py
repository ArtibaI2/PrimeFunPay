import asyncio
import random
from typing import Dict, List, Optional, Callable
from config.settings import settings
from utils.logger import logger
from funpay.client import FunPayClient
from funpay.models import RaiseResult

class AutoRaiseService:
    def __init__(
        self,
        client: FunPayClient,
        categories: Optional[Dict[int, str]] = None,
        on_raise_callback: Optional[Callable] = None,
    ):
        self.client = client
        self.categories: Dict[int, str] = categories or {}
        self.on_raise = on_raise_callback
        self.is_running = False
        self._task: Optional[asyncio.Task] = None

    def add_category(self, node_id: int, category_name: str) -> None:
        self.categories[node_id] = category_name

    async def raise_all(self) -> List[RaiseResult]:
        """Raises lots for all synchronized user categories."""
        results: List[RaiseResult] = []
        if not self.categories:
            logger.warning("No categories registered for auto-raise. Fetching active user offers...")
            profile = self.client.profile or await self.client.check_auth()
            if profile:
                user_lots = await self.client.get_user_lots(profile.user_id)
                for l in user_lots:
                    if l.get("node_id"):
                        self.add_category(l["node_id"], l.get("category_name", str(l["node_id"])))

        if not self.categories:
            logger.warning("Still no categories found for auto-raise.")
            return results

        logger.info(f"Starting auto-raise for {len(self.categories)} categories...")
        for nid, cname in list(self.categories.items()):
            res = await self.client.raise_lots(node_id=nid, category_name=cname)
            results.append(res)
            logger.info(f"Auto-raise for '{cname}' (Node: {nid}): {res.message}")
            await asyncio.sleep(random.uniform(4.0, 7.0))

        if self.on_raise:
            try:
                await self.on_raise(results)
            except Exception as e:
                logger.error(f"Error in on_raise callback: {e}")

        return results

    async def _loop(self) -> None:
        logger.info(f"Auto-raise loop started (Interval: {settings.AUTO_RAISE_INTERVAL}s).")
        while self.is_running:
            try:
                if settings.ENABLE_AUTO_RAISE:
                    logger.info("Executing scheduled lot auto-raise...")
                    await self.raise_all()
                else:
                    logger.debug("Auto-raise is currently disabled in settings.")
            except Exception as e:
                logger.error(f"Error in auto-raise loop: {e}")

            jitter = random.randint(15, 60)
            sleep_duration = settings.AUTO_RAISE_INTERVAL + jitter
            await asyncio.sleep(sleep_duration)

    def start(self) -> None:
        """Starts the background auto-raise loop."""
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        """Stops the background auto-raise loop."""
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()

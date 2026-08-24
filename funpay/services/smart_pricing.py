import asyncio
import re
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from config.settings import settings
from utils.logger import logger
from funpay.client import FunPayClient

class SmartPricingService:
    def __init__(
        self,
        client: FunPayClient,
        min_price_floor: float = 1.0,
    ):
        self.client = client
        self.min_price_floor = min_price_floor
        self.is_running = False
        self._task: Optional[asyncio.Task] = None

    async def check_category_competitors(self, node_id: int, category_name: str = "") -> Optional[float]:
        """Scans the top offers in a category node and finds the lowest competitor price."""
        resp = await self.client._request("GET", f"/lots/{node_id}/")
        if not resp or resp.status != 200:
            return None

        html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        offer_rows = soup.select(".tc-item, a.tc-item")
        
        my_username = (self.client.profile.username.lower()) if (self.client.profile and self.client.profile.username) else ""

        competitor_prices: List[float] = []
        for row in offer_rows:
            # Check author
            user_el = row.select_one(".media-user-name, .user-link-name")
            username = user_el.get_text(strip=True).lower() if user_el else ""
            if my_username and my_username in username:
                continue  # Skip our own offer

            price_el = row.select_one(".tc-price")
            if price_el:
                m = re.search(r"([\d\s.,]+)", price_el.get_text())
                if m:
                    try:
                        p = float(m.group(1).replace(" ", "").replace(",", "."))
                        if p > 0:
                            competitor_prices.append(p)
                    except ValueError:
                        pass

        if competitor_prices:
            min_price = min(competitor_prices)
            logger.info(f"Smart pricing scan for '{category_name or node_id}': Top competitor price is {min_price:.2f} RUB (scanned {len(competitor_prices)} offers)")
            return min_price
        return None

    async def run_scan(self, categories: Dict[int, str]) -> Dict[int, float]:
        """Performs competitive scan for all active categories."""
        results = {}
        for nid, cname in categories.items():
            min_p = await self.check_category_competitors(nid, cname)
            if min_p is not None:
                suggested = max(min_p - 0.01, self.min_price_floor)
                results[nid] = suggested
                logger.info(f"💡 Recommended price for '{cname}': {suggested:.2f} RUB")
            await asyncio.sleep(3.0)
        return results

    async def _loop(self, categories_provider) -> None:
        logger.info("Smart Pricing service loop started.")
        while self.is_running:
            try:
                if settings.ENABLE_SMART_PRICING:
                    cats = categories_provider()
                    if cats:
                        logger.info(f"Executing smart pricing check for {len(cats)} categories...")
                        await self.run_scan(cats)
            except Exception as e:
                logger.error(f"Error in smart pricing loop: {e}")

            # Sleep 30 minutes between scans
            await asyncio.sleep(1800)

    def start(self, categories_provider) -> None:
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._loop(categories_provider))

    def stop(self) -> None:
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()

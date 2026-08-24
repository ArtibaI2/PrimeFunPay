import re
import aiohttp
from typing import List, Optional, Tuple
from config.settings import settings
from utils.logger import logger

class AutoStockService:
    def __init__(self, provider_api_url: Optional[str] = None, provider_api_key: Optional[str] = None):
        self.provider_api_url = provider_api_url
        self.provider_api_key = provider_api_key

    def clean_and_validate_items(self, lines: List[str]) -> Tuple[List[str], List[str]]:
        """Cleans stock items, removes duplicates, and separates valid items from empty lines."""
        valid_items: List[str] = []
        invalid_items: List[str] = []
        seen = set()

        for line in lines:
            cleaned = line.strip()
            if not cleaned:
                continue

            if cleaned in seen:
                continue
            seen.add(cleaned)

            # Validate basic minimum requirements
            if len(cleaned) < 3:
                invalid_items.append(cleaned)
            else:
                valid_items.append(cleaned)

        return valid_items, invalid_items

    async def fetch_item_from_provider(self, product_category: str) -> Optional[str]:
        """Fetches a digital item dynamically from an external provider API if configured."""
        if not self.provider_api_url:
            return None

        try:
            headers = {}
            if self.provider_api_key:
                headers["Authorization"] = f"Bearer {self.provider_api_key}"

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                payload = {"category": product_category}
                async with session.post(self.provider_api_url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        item = data.get("item") or data.get("key") or data.get("content")
                        if item:
                            logger.info(f"Dynamically fetched stock item from provider for category '{product_category}'")
                            return str(item)
        except Exception as e:
            logger.error(f"Error fetching item from external provider API: {e}")

        return None

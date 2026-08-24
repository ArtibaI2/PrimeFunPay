import asyncio
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
import aiohttp
from bs4 import BeautifulSoup
from utils.logger import logger
from .models import UserProfile, FunPayOrder, ChatMessage, RaiseResult
from .parser import FunPayParser

class FunPayClient:
    BASE_URL = "https://funpay.com"

    def __init__(
        self,
        golden_key: str,
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        proxy: Optional[str] = None,
    ):
        self.golden_key = golden_key
        self.user_agent = user_agent
        self.proxy = proxy
        self.session: Optional[aiohttp.ClientSession] = None
        self.profile: Optional[UserProfile] = None
        self.parser = FunPayParser()

    async def init_session(self) -> None:
        """Initializes the aiohttp client session with cookies and headers."""
        if self.session is None or self.session.closed:
            cookies = {"golden_key": self.golden_key}
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://funpay.com/",
            }
            connector = aiohttp.TCPConnector(ssl=True)
            self.session = aiohttp.ClientSession(
                cookies=cookies,
                headers=headers,
                connector=connector,
            )

    async def close(self) -> None:
        """Closes the active HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        data: Optional[Any] = None,
        json_payload: Optional[dict] = None,
        headers_override: Optional[dict] = None,
        is_ajax: bool = False,
    ) -> Optional[aiohttp.ClientResponse]:
        """Internal helper for making resilient HTTP requests."""
        await self.init_session()
        url = f"{self.BASE_URL}/{path.lstrip('/')}"
        
        headers = headers_override.copy() if headers_override else {}
        if is_ajax:
            headers["X-Requested-With"] = "XMLHttpRequest"

        try:
            assert self.session is not None
            response = await self.session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json_payload,
                headers=headers,
                proxy=self.proxy,
                timeout=aiohttp.ClientTimeout(total=30),
            )
            return response
        except asyncio.TimeoutError:
            logger.warning(f"Request timeout to {url}")
        except Exception as e:
            logger.error(f"HTTP request error ({method} {url}): {e}")
        return None

    async def check_auth(self) -> Optional[UserProfile]:
        """Validates credentials and retrieves current user profile."""
        resp = await self._request("GET", "/")
        if resp and resp.status == 200:
            html = await resp.text()
            profile = self.parser.parse_user_profile(html)
            if profile and profile.is_authenticated:
                # Enrich with exact balances from /account/balance
                bal_resp = await self._request("GET", "/account/balance")
                if bal_resp and bal_resp.status == 200:
                    bal_html = await bal_resp.text()
                    avail_rub, avail_usd, avail_eur = self.parser.parse_account_balances(bal_html)
                    profile.balance_available_rub = avail_rub
                    profile.balance_available_usd = avail_usd
                    profile.balance_available_eur = avail_eur
                    if avail_usd > 0:
                        profile.balance_usd = avail_usd
                    if avail_eur > 0:
                        profile.balance_eur = avail_eur

                self.profile = profile
                avail_info = f", Доступно к выводу: {profile.balance_available_rub} RUB" if profile.balance_available_rub != profile.balance_rub else ""
                logger.info(f"Authenticated on FunPay as '{profile.username}' (ID: {profile.user_id}), Balance: {profile.balance_rub} RUB{avail_info}")
                return profile
            else:
                logger.error("Authentication failed: invalid golden_key or session expired.")
        else:
            status = resp.status if resp else "No Response"
            logger.error(f"Failed to load FunPay main page (status: {status}).")
        return None

    async def get_user_lots(self, user_id: Optional[int] = None) -> List[Dict]:
        """Fetches all active offers listed on the user's profile."""
        uid = user_id or (self.profile.user_id if self.profile else None)
        if not uid:
            return []
        resp = await self._request("GET", f"/users/{uid}/")
        if resp and resp.status == 200:
            html = await resp.text()
            return self.parser.parse_user_lots(html)
        return []

    async def get_trade_orders(self) -> List[FunPayOrder]:
        """Fetches list of orders from /orders/trade."""
        resp = await self._request("GET", "/orders/trade")
        if resp and resp.status == 200:
            html = await resp.text()
            return self.parser.parse_trade_orders(html)
        return []

    async def get_order_details(self, order_id: str) -> Optional[FunPayOrder]:
        """Fetches full order page /orders/<id>/."""
        resp = await self._request("GET", f"/orders/{order_id.replace('#', '')}/")
        if resp and resp.status == 200:
            html = await resp.text()
            return self.parser.parse_order_page(html, order_id)
        return None

    async def send_chat_message(
        self,
        chat_node_id: int,
        message: str,
        last_message_id: Optional[int] = None,
    ) -> bool:
        """Sends a message to a FunPay chat / order conversation."""
        payload = {
            "action": "chat_message",
            "node": chat_node_id,
            "last_message": last_message_id or 0,
            "content": message,
        }
        resp = await self._request(
            "POST",
            "/runner/",
            data={"request": json.dumps(payload)},
            is_ajax=True,
        )
        if resp and resp.status == 200:
            logger.info(f"Sent message to chat {chat_node_id}: {message[:40]}...")
            return True
        return False

    async def raise_lots(
        self,
        node_id: int,
        game_id: Optional[int] = None,
        category_name: str = "",
    ) -> RaiseResult:
        """Accurately raises lots for a category node ID on FunPay, handling CSRF and subcategory modals."""
        resp = await self._request("GET", f"/lots/{node_id}/trade")
        if not resp or resp.status != 200:
            return RaiseResult(
                game_id=game_id or 0,
                node_id=node_id,
                category_name=category_name or str(node_id),
                success=False,
                message="Не удалось загрузить страницу управления предложениями.",
            )

        html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")

        btn = soup.select_one(".js-lot-raise, button[data-game][data-node]")
        actual_game_id = game_id
        if btn and btn.get("data-game"):
            actual_game_id = int(btn["data-game"])

        if not actual_game_id:
            actual_game_id = node_id

        body = soup.find("body")
        csrf_token = ""
        if body and body.get("data-app-data"):
            try:
                app_data = json.loads(body["data-app-data"])
                csrf_token = app_data.get("csrf-token", "")
            except Exception:
                pass

        headers = {
            "Referer": f"https://funpay.com/lots/{node_id}/trade",
            "Origin": "https://funpay.com",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        if csrf_token:
            headers["X-CSRF-Token"] = csrf_token

        initial_data = {
            "game_id": str(actual_game_id),
            "node_id": str(node_id),
        }

        resp_post = await self._request(
            "POST",
            "/lots/raise",
            data=urlencode(initial_data),
            headers_override=headers,
            is_ajax=True,
        )

        if not resp_post:
            return RaiseResult(
                game_id=actual_game_id,
                node_id=node_id,
                category_name=category_name or str(node_id),
                success=False,
                message="Нет ответа от сервера FunPay.",
            )

        try:
            res_json = await resp_post.json()
        except Exception:
            text = await resp_post.text()
            if resp_post.status == 429 or "429" in text:
                msg = "Кулдаун запросов FunPay (слишком частые запросы)"
            else:
                msg = text[:80]
            return RaiseResult(
                game_id=actual_game_id,
                node_id=node_id,
                category_name=category_name or str(node_id),
                success=(resp_post.status == 200),
                message=msg,
            )

        if "modal" in res_json and res_json["modal"]:
            modal_soup = BeautifulSoup(res_json["modal"], "html.parser")
            checkboxes = modal_soup.select("input[type='checkbox']")
            node_ids = [cb.get("value") for cb in checkboxes if cb.get("value")]

            if not node_ids:
                node_ids = [str(node_id)]

            modal_data = [
                ("game_id", str(actual_game_id)),
                ("node_id", str(node_id)),
            ]
            for nid in node_ids:
                modal_data.append(("node_ids[]", str(nid)))

            resp_modal = await self._request(
                "POST",
                "/lots/raise",
                data=urlencode(modal_data),
                headers_override=headers,
                is_ajax=True,
            )
            if resp_modal:
                try:
                    res_json = await resp_modal.json()
                except Exception:
                    pass

        msg = res_json.get("msg", "")
        has_error = res_json.get("error", False)
        wait_sec = res_json.get("wait")

        success = (not has_error) or ("подняты" in msg.lower())
        if not msg:
            msg = "Предложения успешно подняты!" if success else "Не удалось поднять лоты."

        return RaiseResult(
            game_id=actual_game_id,
            node_id=node_id,
            category_name=category_name or str(node_id),
            success=success,
            message=msg,
            wait_time_seconds=wait_sec,
        )

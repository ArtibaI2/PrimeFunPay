import os
import json
from pathlib import Path
from aiohttp import web
from config.settings import settings
from utils.logger import logger
from database.engine import async_session
from database.repositories import LotRepository, GoodsRepository, OrderRepository, AutoResponseRepository
from funpay.client import FunPayClient

routes = web.RouteTableDef()

class WebAppServer:
    def __init__(self, funpay_client: FunPayClient, host: str = "0.0.0.0", port: int = 8080):
        self.funpay_client = funpay_client
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: web.AppRunner = None
        self.site: web.TCPSite = None
        self._setup_routes()

    def _setup_routes(self):
        static_dir = Path(__file__).parent / "static"
        static_dir.mkdir(parents=True, exist_ok=True)

        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/api/stats", self.api_stats)
        self.app.router.add_get("/api/lots", self.api_lots)
        self.app.router.add_post("/api/stock/add", self.api_stock_add)
        self.app.router.add_get("/api/orders", self.api_orders)
        self.app.router.add_post("/api/chat/send", self.api_chat_send)
        self.app.router.add_get("/api/settings", self.api_settings_get)
        self.app.router.add_post("/api/settings", self.api_settings_set)
        self.app.router.add_get("/ping", self.api_ping)
        self.app.router.add_get("/health", self.api_ping)
        self.app.router.add_head("/ping", self.api_ping)
        self.app.router.add_head("/health", self.api_ping)
        self.app.router.add_head("/", self.api_ping)

        self.app.router.add_static("/static", path=str(static_dir), name="static")

    async def api_ping(self, request: web.Request) -> web.Response:
        return web.Response(text="OK", content_type="text/plain")

    async def handle_index(self, request: web.Request) -> web.Response:
        index_path = Path(__file__).parent / "static" / "index.html"
        if index_path.exists():
            return web.FileResponse(str(index_path))
        return web.Response(text="<h1>FunPay Bot WebApp</h1>", content_type="text/html")

    async def api_stats(self, request: web.Request) -> web.Response:
        profile = await self.funpay_client.check_auth()
        async with async_session() as session:
            order_repo = OrderRepository(session)
            stats_today = await order_repo.get_period_stats(days=1)
            stats_week = await order_repo.get_period_stats(days=7)
            stats_all = await order_repo.get_period_stats(days=None)
            top_products = await order_repo.get_top_products(limit=5)

        data = {
            "account": {
                "username": profile.username if profile else "Unknown",
                "user_id": profile.user_id if profile else None,
                "balance": profile.balance_rub if profile else 0.0,
                "balance_available": profile.balance_available_rub if profile else 0.0,
                "balance_usd": profile.balance_usd if profile else 0.0,
                "balance_eur": profile.balance_eur if profile else 0.0,
                "active_orders": profile.active_orders_count if profile else 0,
                "unread_chats": profile.unread_chats_count if profile else 0,
            },
            "stats": {
                "today": stats_today,
                "week": stats_week,
                "all": stats_all,
            },
            "top_products": top_products,
        }
        return web.json_response(data)

    async def api_lots(self, request: web.Request) -> web.Response:
        async with async_session() as session:
            lot_repo = LotRepository(session)
            goods_repo = GoodsRepository(session)
            lots = await lot_repo.get_active_lots()
            results = []
            for l in lots:
                cnt = await goods_repo.count_available(lot_id=l.id)
                results.append({
                    "id": l.id,
                    "funpay_lot_id": l.funpay_lot_id,
                    "title": l.title,
                    "category": l.category_name,
                    "price": l.price,
                    "stock_count": cnt,
                    "template": l.delivery_template or "",
                })
        return web.json_response({"lots": results})

    async def api_stock_add(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            lot_id = body.get("lot_id")
            items = body.get("items", [])
            if not lot_id or not items:
                return web.json_response({"error": "lot_id and items are required"}, status=400)

            async with async_session() as session:
                goods_repo = GoodsRepository(session)
                lot_repo = LotRepository(session)
                lot = await lot_repo.get_by_id(int(lot_id))
                lot_title = lot.title if lot else "Товар"
                added = await goods_repo.add_items(items, lot_id=int(lot_id), category_identifier=lot_title)

            return web.json_response({"success": True, "added": added})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def api_orders(self, request: web.Request) -> web.Response:
        orders = await self.funpay_client.get_trade_orders()
        serialized = [
            {
                "order_id": o.order_id,
                "title": o.title,
                "buyer_username": o.buyer_username,
                "price": o.price,
                "status": o.status,
                "is_paid": o.is_paid,
                "is_closed": o.is_closed,
            }
            for o in orders[:20]
        ]
        return web.json_response({"orders": serialized})

    async def api_chat_send(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            chat_node_id = body.get("chat_node_id")
            message = body.get("message")
            if not chat_node_id or not message:
                return web.json_response({"error": "chat_node_id and message are required"}, status=400)

            sent = await self.funpay_client.send_chat_message(
                chat_node_id=int(chat_node_id),
                message=str(message),
            )
            return web.json_response({"success": sent})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def api_settings_get(self, request: web.Request) -> web.Response:
        return web.json_response({
            "auto_delivery": settings.ENABLE_AUTO_DELIVERY,
            "auto_raise": settings.ENABLE_AUTO_RAISE,
            "auto_response": settings.ENABLE_AUTO_RESPONSE,
            "smart_pricing": settings.ENABLE_SMART_PRICING,
            "ai_support": settings.ENABLE_AI_SUPPORT,
            "upsell": settings.ENABLE_UPSELL,
            "night_surge": settings.ENABLE_NIGHT_SURGE,
            "night_surge_percent": settings.NIGHT_SURGE_PERCENT,
        })

    async def api_settings_set(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            for key, val in body.items():
                if key == "auto_delivery":
                    settings.ENABLE_AUTO_DELIVERY = bool(val)
                elif key == "auto_raise":
                    settings.ENABLE_AUTO_RAISE = bool(val)
                elif key == "auto_response":
                    settings.ENABLE_AUTO_RESPONSE = bool(val)
                elif key == "smart_pricing":
                    settings.ENABLE_SMART_PRICING = bool(val)
                elif key == "ai_support":
                    settings.ENABLE_AI_SUPPORT = bool(val)
                elif key == "upsell":
                    settings.ENABLE_UPSELL = bool(val)
                elif key == "night_surge":
                    settings.ENABLE_NIGHT_SURGE = bool(val)
            return web.json_response({"success": True})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def api_market(self, request: web.Request) -> web.Response:
        from funpay.services.market_analytics import MarketAnalyticsService
        market_svc = MarketAnalyticsService(self.funpay_client)
        categories = {}
        profile = self.funpay_client.profile or await self.funpay_client.check_auth()
        if profile:
            user_lots = await self.funpay_client.get_user_lots(profile.user_id)
            for l in user_lots:
                nid = l.get("node_id")
                cname = l.get("category_name", str(nid))
                if nid:
                    categories[nid] = cname
        if not categories:
            categories = {
                923: "Discord Nitro",
                469: "Прочее Apex Legends",
                908: "Прочее Brawl Stars",
                1351: "Прочее Counter-Strike 2",
                1099: "Прочее Minecraft",
            }
        force = request.query.get("force") == "1"
        report = await market_svc.generate_market_report(categories, force_refresh=force)
        return web.json_response(report)

    async def start(self) -> None:
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        logger.info(f"🚀 WebApp Dashboard running at http://{self.host}:{self.port}")

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()
            logger.info("WebApp Dashboard stopped.")

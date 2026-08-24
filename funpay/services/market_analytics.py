import asyncio
import re
from typing import Dict, List, Optional, Any
from collections import Counter
from bs4 import BeautifulSoup
from config.settings import settings
from utils.logger import logger
from funpay.client import FunPayClient

class MarketAnalyticsService:
    """
    Market intelligence service that analyzes 24h competitor trends,
    popular products, pricing distributions, and high-demand niches on FunPay.
    """

    def __init__(self, client: FunPayClient):
        self.client = client
        self.cached_report: Optional[Dict[str, Any]] = None
        self.last_scanned_at: Optional[float] = None
        self._lock = asyncio.Lock()

    async def scan_category_details(self, node_id: int, category_name: str) -> Dict[str, Any]:
        """Scans a single category and extracts deep competitor market statistics."""
        resp = await self.client._request("GET", f"/lots/{node_id}/")
        if not resp or resp.status != 200:
            return {
                "node_id": node_id,
                "category_name": category_name,
                "error": "Failed to fetch category page",
            }

        html = await resp.text()
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select(".tc-item, a.tc-item")

        my_username = (self.client.profile.username.lower()) if (self.client.profile and self.client.profile.username) else ""

        prices: List[float] = []
        titles: List[str] = []
        sellers: List[str] = []
        seller_reviews_list: List[int] = []
        has_autodelivery_count = 0

        top_lots: List[Dict[str, Any]] = []

        for it in items:
            href = it.get("href", "")
            if href and not href.startswith("http"):
                href = f"https://funpay.com{href}"

            # Check seller
            user_el = it.select_one(".media-user-name, .user-name")
            seller_name = user_el.get_text(strip=True) if user_el else "Unknown"
            if my_username and my_username in seller_name.lower():
                continue

            sellers.append(seller_name)

            # Reviews count
            rev_count = 0
            reviews_el = it.select_one(".media-user-reviews, .rating")
            if reviews_el:
                rev_text = reviews_el.get_text(strip=True)
                rev_digits = re.sub(r"\D", "", rev_text)
                if rev_digits:
                    rev_count = int(rev_digits)
                    seller_reviews_list.append(rev_count)

            # Title
            desc_el = it.select_one(".tc-desc-text, .tc-desc, .tc-item-title")
            title = desc_el.get_text(strip=True) if desc_el else ""
            if title:
                titles.append(title)
                if any(w in title.lower() for w in ["автовыдача", "авто-выдача", "24/7", "мгновенно", "моментально", "fast", "instant"]):
                    has_autodelivery_count += 1

            # Price
            item_price = 0.0
            price_el = it.select_one(".tc-price")
            if price_el:
                m = re.search(r"([\d\s.,]+)", price_el.get_text())
                if m:
                    try:
                        item_price = float(m.group(1).replace(" ", "").replace(",", "."))
                        if item_price > 0:
                            prices.append(item_price)
                    except ValueError:
                        pass

            if href and title and item_price > 0 and len(top_lots) < 3:
                top_lots.append({
                    "title": title[:42],
                    "price": item_price,
                    "url": href,
                    "seller": seller_name,
                    "reviews": rev_count,
                })

        total_offers = len(prices)
        if total_offers == 0:
            return {
                "node_id": node_id,
                "category_name": category_name,
                "total_offers": 0,
                "status": "empty",
                "top_lots": [],
            }

        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / total_offers
        sorted_prices = sorted(prices)
        median_price = sorted_prices[total_offers // 2]

        # Extract top keywords and formats from titles
        all_words = []
        for t in titles:
            clean = re.sub(r"[^\w\s]", " ", t)
            words = [w for w in clean.split() if len(w) >= 3 and not w.isdigit()]
            all_words.extend(words)

        stop_words = {"для", "или", "как", "все", "при", "без", "под", "год", "руб", "рублей", "что", "это", "прочее", "аккаунт", "аккаунтов", "игры", "игры"}
        filtered_words = [w for w in all_words if w.lower() not in stop_words]
        keyword_counts = Counter(filtered_words).most_common(6)
        top_keywords = [k[0] for k in keyword_counts]

        # Top competitors by presence
        top_sellers = [s[0] for s in Counter(sellers).most_common(3)]
        avg_reviews = (sum(seller_reviews_list) / len(seller_reviews_list)) if seller_reviews_list else 0

        # Demand score calculation (0 - 100)
        demand_score = min(100, int((total_offers / 40) * 40 + (min(avg_reviews, 1000) / 1000) * 40 + (has_autodelivery_count / max(1, total_offers)) * 20))
        demand_level = "🔥 ВЫСОКИЙ" if demand_score >= 65 else ("⚡ СРЕДНИЙ" if demand_score >= 35 else "Нормальный")

        # Optimal competitive pricing
        recommended_price = max(round(min_price * 0.98, 2), 1.0)

        # Smart insights
        insights = []
        if has_autodelivery_count / max(1, total_offers) > 0.4:
            insights.append("⚡ Высокая доля автовыдачи — обязательна мгновенная выдача товара.")
        if min_price < avg_price * 0.3:
            insights.append("🎯 В категории есть бюджетные товары от 1-2 ₽ для быстрого набора отзывов.")
        if top_keywords:
            insights.append(f"🔍 Частые запросы покупателей: {', '.join(top_keywords[:3])}.")

        return {
            "node_id": node_id,
            "category_name": category_name,
            "category_url": f"https://funpay.com/lots/{node_id}/",
            "total_offers": total_offers,
            "min_price": min_price,
            "avg_price": round(avg_price, 2),
            "median_price": round(median_price, 2),
            "max_price": max_price,
            "recommended_price": recommended_price,
            "top_keywords": top_keywords,
            "top_sellers": top_sellers,
            "top_lots": top_lots,
            "avg_reviews": int(avg_reviews),
            "autodelivery_percent": int((has_autodelivery_count / max(1, total_offers)) * 100),
            "demand_score": demand_score,
            "demand_level": demand_level,
            "insights": insights,
        }

    async def generate_market_report(self, categories: Dict[int, str], force_refresh: bool = False) -> Dict[str, Any]:
        """Generates or retrieves full 24h market intelligence across all active categories."""
        import time
        async with self._lock:
            now = time.time()
            if not force_refresh and self.cached_report and self.last_scanned_at and (now - self.last_scanned_at < 600):
                return self.cached_report

            logger.info(f"Generating 24h market analysis for {len(categories)} categories...")
            cat_results = []
            
            # Scan categories in parallel batches of 3
            items_list = list(categories.items())
            for i in range(0, len(items_list), 3):
                chunk = items_list[i:i+3]
                tasks = [self.scan_category_details(nid, cname) for nid, cname in chunk]
                res_chunk = await asyncio.gather(*tasks, return_exceptions=True)
                for r in res_chunk:
                    if isinstance(r, dict) and "total_offers" in r:
                        cat_results.append(r)
                await asyncio.sleep(1.5)

            # Sort by demand score
            cat_results.sort(key=lambda x: x.get("demand_score", 0), reverse=True)

            # Top selling formats / categories
            hot_categories = [c for c in cat_results if c.get("demand_score", 0) >= 50]
            if not hot_categories and cat_results:
                hot_categories = cat_results[:3]

            overall_recommendations = []
            if cat_results:
                top_cat = cat_results[0]
                overall_recommendations.append(
                    f"🔥 Самый высокий спрос зафиксирован в категории «<a href='https://funpay.com/lots/{top_cat['node_id']}/'>{top_cat['category_name']}</a>» (Спрос: {top_cat['demand_level']})."
                )
                
                cheap_cats = [c for c in cat_results if c.get("min_price", 999) <= 5.0]
                if cheap_cats:
                    overall_recommendations.append(
                        f"⭐ Для быстрого набора 5★ отзывов отлично подходят лоты в «<a href='https://funpay.com/lots/{cheap_cats[0]['node_id']}/'>{cheap_cats[0]['category_name']}</a>» с автовыдачей по {cheap_cats[0]['min_price']:.2f} ₽."
                    )
                    
                overall_recommendations.append(
                    "💡 Покупатели чаще всего выбирают товары с пометками «<b>АВТОВЫДАЧА</b>», «<b>ГАРАНТИЯ</b>» и ссылками на проверенные облака (Workupload / Google Диск)."
                )

            report = {
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_categories_scanned": len(cat_results),
                "categories": cat_results,
                "hot_categories": hot_categories[:5],
                "recommendations": overall_recommendations,
            }

            self.cached_report = report
            self.last_scanned_at = now
            logger.info(f"✅ Market analysis completed. Scanned {len(cat_results)} categories.")
            return report

    def format_telegram_report(self, report: Dict[str, Any], max_items: int = 4) -> str:
        """Formats the market analysis into an aesthetic Telegram markdown report with direct links."""
        if not report or not report.get("categories"):
            return "📊 <b>Анализ рынка:</b> Недостаточно данных по категориям для построения отчета."

        categories = report.get("categories", [])[:max_items]
        recs = report.get("recommendations", [])

        lines = [
            "📊 <b>АНАЛИЗ РЫНКА FUNPAY ЗА 24 ЧАСА</b>\n"
            "<i>(Прямые ссылки на самые продаваемые товары и категории)</i>\n"
        ]

        lines.append("🔥 <b>ТОП НАИБОЛЕЕ ВОСТРЕБОВАННЫХ КАТЕГОРИЙ:</b>\n")

        for idx, cat in enumerate(categories, 1):
            cname = cat.get("category_name", "Категория")
            nid = cat.get("node_id")
            cat_url = cat.get("category_url", f"https://funpay.com/lots/{nid}/" if nid else "https://funpay.com")
            min_p = cat.get("min_price", 0.0)
            avg_p = cat.get("avg_price", 0.0)
            rec_p = cat.get("recommended_price", 0.0)
            offers = cat.get("total_offers", 0)
            d_level = cat.get("demand_level", "Нормальный")
            keywords = cat.get("top_keywords", [])
            autodelivery = cat.get("autodelivery_percent", 0)
            top_lots = cat.get("top_lots", [])

            kw_str = ", ".join(keywords[:3]) if keywords else "Ключи, гайды, услуги"

            lines.append(
                f"<b>{idx}. <a href='{cat_url}'>{cname}</a></b>\n"
                f"• Спрос: <b>{d_level}</b> (Конкурентов: <code>{offers}</code>)\n"
                f"• Цены рынка: от <b>{min_p:,.2f} ₽</b> (средняя: <code>{avg_p:,.2f} ₽</code>)\n"
                f"• 🎯 Входная цена: <b>{rec_p:,.2f} ₽</b>\n"
                f"• 🔍 В тренде: <i>{kw_str}</i> | ⚡ Автовыдача: <code>{autodelivery}%</code>"
            )

            if top_lots:
                lines.append("• 🔗 <b>Топовые товары конкурентов:</b>")
                for l_idx, lot in enumerate(top_lots, 1):
                    lines.append(
                        f"   {l_idx}) <a href='{lot['url']}'>{lot['title']}</a> — <b>{lot['price']:,.2f} ₽</b> (⭐ {lot['reviews']})"
                    )
            lines.append("")

        if recs:
            lines.append("💡 <b>РЕКОМЕНДАЦИИ ПО ТОРГОВЛЕ:</b>")
            for r in recs:
                lines.append(f"• {r}")

        lines.append(
            "\n<i>💡 Нажмите <b>➕ Создать товар по тренду</b>, чтобы сразу добавить прибыльный лот!</i>"
        )

        return "\n".join(lines)

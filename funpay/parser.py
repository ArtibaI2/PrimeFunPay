import re
from typing import List, Optional, Dict
from bs4 import BeautifulSoup
from utils.logger import logger
from .models import UserProfile, FunPayOrder, ChatMessage, RaiseResult

class FunPayParser:
    @staticmethod
    def parse_user_profile(html: str) -> Optional[UserProfile]:
        """Extracts clean user profile details from FunPay HTML."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            user_name_el = soup.select_one(".user-link-name, .user-name")
            user_anchor = soup.find("a", href=re.compile(r"/users/(\d+)/"))
            
            if not user_anchor and not user_name_el:
                return None

            user_id = 0
            username = "Unknown"

            if user_anchor and user_anchor.get("href"):
                match = re.search(r"/users/(\d+)/", user_anchor["href"])
                if match:
                    user_id = int(match.group(1))

            if user_name_el:
                username = user_name_el.get_text(strip=True)
            elif user_anchor:
                for tag in user_anchor.find_all(["span", "div", "i"]):
                    tag.decompose()
                username = user_anchor.get_text(strip=True)

            username = re.sub(r"(Профиль|Profile|Баланс|Balance).*$", "", username, flags=re.IGNORECASE).strip()

            balance_rub = 0.0
            balance_usd = 0.0
            balance_eur = 0.0

            balance_rub_el = soup.find(class_=re.compile(r"badge-balance|menu-item-balance"))
            if balance_rub_el:
                badge_text = balance_rub_el.get_text(strip=True).replace("\xa0", " ").replace("¤", "₽")
                usd_match = re.search(r"(?:\$|\busd\b)\s*([\d\s.,]+)|([\d\s.,]+)\s*(?:\$|\busd\b)", badge_text, re.IGNORECASE)
                eur_match = re.search(r"(?:€|\beur\b)\s*([\d\s.,]+)|([\d\s.,]+)\s*(?:€|\beur\b)", badge_text, re.IGNORECASE)
                if usd_match:
                    val_str = usd_match.group(1) or usd_match.group(2)
                    try:
                        balance_usd = float(val_str.replace(" ", "").replace(",", "."))
                    except ValueError:
                        pass
                if eur_match:
                    val_str = eur_match.group(1) or eur_match.group(2)
                    try:
                        balance_eur = float(val_str.replace(" ", "").replace(",", "."))
                    except ValueError:
                        pass
                if not (usd_match or eur_match):
                    rub_match = re.search(r"([\d\s.,]+)", badge_text)
                    if rub_match:
                        try:
                            balance_rub = float(rub_match.group(1).replace(" ", "").replace(",", "."))
                        except ValueError:
                            pass

            orders_count = 0
            orders_badge = soup.find("span", class_="badge-orders")
            if orders_badge and orders_badge.get_text(strip=True).isdigit():
                orders_count = int(orders_badge.get_text(strip=True))

            unread_chats = 0
            chat_badge = soup.find("span", class_="badge-chat")
            if chat_badge and chat_badge.get_text(strip=True).isdigit():
                unread_chats = int(chat_badge.get_text(strip=True))

            return UserProfile(
                user_id=user_id,
                username=username,
                balance_rub=balance_rub,
                balance_usd=balance_usd,
                balance_eur=balance_eur,
                balance_available_rub=balance_rub,
                balance_available_usd=balance_usd,
                balance_available_eur=balance_eur,
                active_orders_count=orders_count,
                unread_chats_count=unread_chats,
                is_authenticated=True,
            )
        except Exception as e:
            logger.error(f"Error parsing user profile HTML: {e}")
            return None

    @staticmethod
    def parse_account_balances(html: str) -> tuple[float, float, float]:
        """Parses multi-currency available balances from /account/balance HTML."""
        rub, usd, eur = 0.0, 0.0, 0.0
        try:
            soup = BeautifulSoup(html, "html.parser")
            val_spans = soup.select(".balances-value, .balances-list span")
            for s in val_spans:
                txt = s.get_text(strip=True).replace("\xa0", " ")
                if not txt or txt == "·":
                    continue
                if "$" in txt or "usd" in txt.lower():
                    m = re.search(r"([\d\s.,]+)", txt)
                    if m:
                        usd = float(m.group(1).replace(" ", "").replace(",", "."))
                elif "€" in txt or "eur" in txt.lower():
                    m = re.search(r"([\d\s.,]+)", txt)
                    if m:
                        eur = float(m.group(1).replace(" ", "").replace(",", "."))
                elif "₽" in txt or "¤" in txt or "руб" in txt.lower() or "rub" in txt.lower():
                    m = re.search(r"([\d\s.,]+)", txt)
                    if m:
                        rub = float(m.group(1).replace(" ", "").replace(",", "."))
        except Exception as e:
            logger.error(f"Error parsing account balances HTML: {e}")
        return rub, usd, eur

    @staticmethod
    def parse_user_lots(html: str) -> List[Dict]:
        """Parses all active offers/lots with category names and node IDs from profile page."""
        lots = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            offer_items = soup.select("a.tc-item")
            for item in offer_items:
                href = item.get("href", "")
                lot_id_match = re.search(r"id=(\d+)", href)
                if not lot_id_match:
                    continue
                lot_id = int(lot_id_match.group(1))

                desc_el = item.select_one(".tc-desc-text, .tc-title")
                desc = desc_el.get_text(strip=True) if desc_el else item.get_text(strip=True)

                price = 0.0
                price_el = item.select_one(".tc-price")
                if price_el:
                    p_match = re.search(r"([\d\s.,]+)", price_el.get_text())
                    if p_match:
                        price = float(p_match.group(1).replace(" ", "").replace(",", "."))

                cat_title = "Разное"
                node_id = None

                curr = item
                while curr:
                    prev = curr.find_previous_sibling()
                    if prev and (prev.find("a", href=re.compile(r"/(lots|chips)/(\d+)/")) or "tc-header" in prev.get("class", [])):
                        a_cat = prev.find("a", href=re.compile(r"/(lots|chips)/(\d+)/"))
                        if a_cat:
                            cat_title = a_cat.get_text(strip=True)
                            m = re.search(r"/(lots|chips)/(\d+)/", a_cat["href"])
                            if m:
                                node_id = int(m.group(2))
                            break
                    curr = curr.parent
                    if not curr or curr.name == "body":
                        break

                if not node_id:
                    prev_a = item.find_previous("a", href=re.compile(r"/(lots|chips)/(\d+)/"))
                    if prev_a:
                        cat_title = prev_a.get_text(strip=True)
                        m = re.search(r"/(lots|chips)/(\d+)/", prev_a["href"])
                        if m:
                            node_id = int(m.group(2))

                lots.append({
                    "lot_id": lot_id,
                    "title": desc,
                    "price": price,
                    "category_name": cat_title,
                    "node_id": node_id,
                    "url": href,
                })
        except Exception as e:
            logger.error(f"Error parsing user lots: {e}")
        return lots

    @staticmethod
    def parse_trade_orders(html: str) -> List[FunPayOrder]:
        """Parses list of orders from https://funpay.com/orders/trade."""
        orders: List[FunPayOrder] = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            order_rows = soup.select(".tc-order-item, a.tc-item")
            for row in order_rows:
                order_id_el = row.select_one(".tc-order")
                if not order_id_el:
                    continue
                raw_id = order_id_el.get_text(strip=True).replace("#", "")
                
                title_el = row.select_one(".order-desc, .tc-title")
                title = title_el.get_text(strip=True) if title_el else ""

                user_name_el = row.select_one(".media-user-name span, .media-user-name a, .media-user-name")
                if user_name_el:
                    buyer = user_name_el.get_text(strip=True)
                else:
                    user_el = row.select_one(".tc-user")
                    if user_el:
                        status_tag = user_el.select_one(".media-user-status")
                        if status_tag:
                            status_tag.decompose()
                        buyer = user_el.get_text(strip=True)
                    else:
                        buyer = "Unknown"
                buyer = re.sub(r"(?i)\s*(онлайн|был\s+.*|заблокирован|online).*$", "", buyer).strip()

                price_el = row.select_one(".tc-price")
                price = 0.0
                if price_el:
                    p_match = re.search(r"([\d\s.,]+)", price_el.get_text())
                    if p_match:
                        price = float(p_match.group(1).replace(" ", "").replace(",", "."))

                status_el = row.select_one(".tc-status")
                status_text = status_el.get_text(strip=True).lower() if status_el else "оплачен"
                
                status = "paid"
                is_paid = True
                if "закрыт" in status_text or "выполнен" in status_text or "доставлен" in status_text:
                    status = "closed"
                    is_paid = False
                elif "возврат" in status_text or "отменен" in status_text:
                    status = "refunded"
                    is_paid = False
                elif "спор" in status_text:
                    status = "disputed"
                    is_paid = False

                orders.append(
                    FunPayOrder(
                        order_id=raw_id,
                        title=title,
                        buyer_username=buyer,
                        price=price,
                        status=status,
                        is_closed=(status == "closed"),
                        is_paid=is_paid,
                        url=f"https://funpay.com/orders/{raw_id}/",
                    )
                )
        except Exception as e:
            logger.error(f"Error parsing trade orders HTML: {e}")
        return orders

    @staticmethod
    def parse_order_page(html: str, order_id: str) -> Optional[FunPayOrder]:
        """Parses full order details page https://funpay.com/orders/<id>/."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # 1. Chat node ID
            chat_node_id = None
            chat_el = soup.select_one(".chat[data-id], .chat[data-node], div[data-id][data-name*='users-']")
            if chat_el:
                raw_node = chat_el.get("data-id") or chat_el.get("data-node")
                if raw_node and str(raw_node).isdigit():
                    chat_node_id = int(raw_node)

            if not chat_node_id:
                m = re.search(r'node_id\s*:\s*(\d+)', html)
                if m:
                    chat_node_id = int(m.group(1))

            # 2. Buyer username & Buyer ID
            buyer_username = "Unknown"
            buyer_id = None

            buyer_el = soup.select_one(".chat-header .media-user-name, .chat-panel .media-user-name, .chat .media-user-name, .media-user-name")
            if buyer_el:
                buyer_username = buyer_el.get_text(strip=True)
            else:
                user_link = soup.select_one(".chat-header [data-href*='/users/'], .param-item [data-href*='/users/'], a[href*='/users/']")
                if user_link:
                    buyer_username = user_link.get_text(strip=True)
            buyer_username = re.sub(r"(?i)\s*(онлайн|был\s+.*|заблокирован|online).*$", "", buyer_username).strip()

            # Buyer ID from chat data-name (e.g. users-8940963-20869116)
            if chat_el and chat_el.get("data-name"):
                m = re.search(r"users-(\d+)-(\d+)", chat_el["data-name"])
                if m:
                    u1, u2 = int(m.group(1)), int(m.group(2))
                    cur_user = int(chat_el.get("data-user", 0))
                    buyer_id = u1 if (cur_user and u2 == cur_user) else (u2 if (cur_user and u1 == cur_user) else u1)

            # 3. Param items
            params = {}
            for p in soup.select(".param-item"):
                h5 = p.select_one("h5")
                if h5:
                    key = h5.get_text(strip=True)
                    h5_clone = p.select_one("h5")
                    if h5_clone:
                        h5_clone.decompose()
                    val = p.get_text(" ", strip=True)
                    params[key] = val

            # Title
            title = params.get("Краткое описание") or params.get("Подробное описание") or ""
            server = params.get("Сервер") or ""
            if server and title:
                title = f"{server}, {title}"
            elif not title:
                desc_el = soup.select_one(".order-desc")
                title = desc_el.get_text(strip=True) if desc_el else "Order Item"

            # Price
            price = 0.0
            price_str = params.get("Сумма", "")
            p_match = re.search(r"([\d\s.,]+)", price_str)
            if p_match:
                price = float(p_match.group(1).replace(" ", "").replace(",", "."))
            else:
                price_el = soup.select_one(".order-status .text-bold, .param-item .text-bold")
                if price_el:
                    p_m2 = re.search(r"([\d\s.,]+)", price_el.get_text())
                    if p_m2:
                        price = float(p_m2.group(1).replace(" ", "").replace(",", "."))

            # Status
            status = "paid"
            for k in params.keys():
                kl = k.lower()
                if "закрыт" in kl or "выполнен" in kl or "подтвержден" in kl:
                    status = "closed"
                    break
                elif "возврат" in kl:
                    status = "refunded"
                    break
                elif "спор" in kl:
                    status = "disputed"
                    break
                elif "открыт" in kl or "оплачен" in kl:
                    status = "paid"

            return FunPayOrder(
                order_id=order_id,
                title=title,
                buyer_username=buyer_username,
                buyer_id=buyer_id,
                price=price,
                status=status,
                chat_node_id=chat_node_id,
                is_closed=(status == "closed"),
                is_paid=(status == "paid"),
                url=f"https://funpay.com/orders/{order_id}/",
            )
        except Exception as e:
            logger.error(f"Error parsing order page {order_id}: {e}")
            return None

    @staticmethod
    def parse_chat_messages(html: str, current_user_id: int = 0) -> List[ChatMessage]:
        """Parses chat messages from a chat node HTML snippet."""
        messages: List[ChatMessage] = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            msg_items = soup.select(".chat-msg-item")
            for item in msg_items:
                msg_id_attr = item.get("data-id")
                if not msg_id_attr or not msg_id_attr.isdigit():
                    continue
                msg_id = int(msg_id_attr)

                author_el = item.select_one(".chat-msg-author")
                sender_username = author_el.get_text(strip=True) if author_el else ""
                
                sender_id = 0
                if author_el and author_el.find("a"):
                    m = re.search(r"/users/(\d+)/", author_el.find("a").get("href", ""))
                    if m:
                        sender_id = int(m.group(1))

                text_el = item.select_one(".chat-msg-text")
                text = text_el.get_text(strip=True) if text_el else ""

                is_system = "chat-msg-system" in item.get("class", [])
                is_my_msg = (sender_id == current_user_id) if current_user_id else False

                node_id = 0
                parent_chat = item.find_parent("div", class_="chat")
                if parent_chat and parent_chat.get("data-node", "").isdigit():
                    node_id = int(parent_chat["data-node"])

                messages.append(
                    ChatMessage(
                        message_id=msg_id,
                        chat_node_id=node_id,
                        sender_username=sender_username,
                        sender_id=sender_id,
                        text=text,
                        is_my_message=is_my_msg,
                        is_system=is_system,
                    )
                )
        except Exception as e:
            logger.error(f"Error parsing chat messages: {e}")
        return messages

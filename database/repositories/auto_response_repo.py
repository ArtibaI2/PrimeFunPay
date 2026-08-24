import re
from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import AutoResponseRule

class AutoResponseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_rule(self, keyword: str, response_text: str, is_regex: bool = False) -> AutoResponseRule:
        """Adds a new trigger rule for auto-replies."""
        rule = AutoResponseRule(
            keyword=keyword.strip().lower(),
            response_text=response_text.strip(),
            is_regex=is_regex,
            is_active=True,
        )
        self.session.add(rule)
        await self.session.commit()
        await self.session.refresh(rule)
        return rule

    async def create_rule(self, keyword: str, response_text: str, is_regex: bool = False) -> AutoResponseRule:
        """Alias to add_rule."""
        return await self.add_rule(keyword=keyword, response_text=response_text, is_regex=is_regex)

    async def get_by_id(self, rule_id: int) -> Optional[AutoResponseRule]:
        """Gets rule by ID."""
        result = await self.session.execute(
            select(AutoResponseRule).where(AutoResponseRule.id == rule_id)
        )
        return result.scalar_one_or_none()

    async def get_all_rules(self) -> List[AutoResponseRule]:
        """Returns all rules."""
        result = await self.session.execute(select(AutoResponseRule))
        return list(result.scalars().all())

    async def get_all_active(self) -> List[AutoResponseRule]:
        """Returns all active auto-response rules."""
        result = await self.session.execute(
            select(AutoResponseRule).where(AutoResponseRule.is_active == True)  # noqa: E712
        )
        return list(result.scalars().all())

    async def find_matching_response(self, text: str) -> Optional[str]:
        """Finds matching template response for user message."""
        clean_text = text.strip().lower()
        rules = await self.get_all_active()
        for rule in rules:
            if rule.is_regex:
                try:
                    if re.search(rule.keyword, clean_text, re.IGNORECASE):
                        return rule.response_text
                except re.error:
                    continue
            else:
                if rule.keyword in clean_text:
                    return rule.response_text
        return None

    async def delete_rule(self, rule_id: int) -> bool:
        """Deletes a rule by ID."""
        result = await self.session.execute(
            delete(AutoResponseRule).where(AutoResponseRule.id == rule_id)
        )
        await self.session.commit()
        return result.rowcount > 0

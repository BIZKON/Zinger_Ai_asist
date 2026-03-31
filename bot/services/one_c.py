"""1С OData API — клиент для Зингер Логистика.

Подключение через Cloudflare Tunnel.
Basic Auth: ONE_C_USERNAME / ONE_C_PASSWORD.

Ключевые сущности OData:
  - Document_РасходнаяНакладная — накладные
  - Catalog_Контрагенты — контрагенты
  - Document_ЗаказКлиента — заказы
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
import redis.asyncio as aioredis
import structlog

from bot.config import settings

logger = structlog.get_logger()

CACHE_TTL_SHORT = 300   # 5 min  — для списков
CACHE_TTL_LONG = 1800   # 30 min — для справочников


class OneCClient:
    """Async client for 1С OData REST API."""

    def __init__(self) -> None:
        self.base_url = settings.one_c_base_url.rstrip("/")
        self.auth = (settings.one_c_username, settings.one_c_password)

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and settings.one_c_username)

    async def _request(
        self,
        endpoint: str,
        params: dict | None = None,
        method: str = "GET",
        json_data: dict | None = None,
        timeout: int = 15,
    ) -> dict | list | None:
        """Make a request to 1С OData API."""
        if not self.is_configured:
            logger.warning("one_c_not_configured")
            return None

        url = f"{self.base_url}/odata/standard.odata/{endpoint}"
        default_params = {"$format": "json"}
        if params:
            default_params.update(params)

        start = time.monotonic()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(
                    method=method,
                    url=url,
                    params=default_params,
                    auth=self.auth,
                    json=json_data,
                )
                resp.raise_for_status()
                data = resp.json()

            elapsed = time.monotonic() - start
            logger.info(
                "one_c_request",
                endpoint=endpoint,
                method=method,
                elapsed_sec=round(elapsed, 2),
                status=resp.status_code,
            )

            # OData returns {"value": [...]} for collections
            if isinstance(data, dict) and "value" in data:
                return data["value"]
            return data

        except httpx.ConnectError:
            logger.error("one_c_unreachable", endpoint=endpoint)
            return None
        except httpx.HTTPStatusError as e:
            logger.error("one_c_http_error", status=e.response.status_code, endpoint=endpoint)
            return None
        except Exception as e:
            logger.error("one_c_error", endpoint=endpoint, error=str(e))
            return None

    # ── Накладные ──

    async def get_waybills(
        self,
        status: str | None = None,
        top: int = 20,
        redis_client: aioredis.Redis | None = None,
    ) -> list[dict]:
        """Получить список накладных."""
        cache_key = f"1c:waybills:{status or 'all'}"
        cached = await self._get_cache(redis_client, cache_key)
        if cached is not None:
            return cached

        params: dict[str, Any] = {
            "$top": str(top),
            "$orderby": "Date desc",
        }
        if status:
            params["$filter"] = f"Status eq '{status}'"

        result = await self._request("Document_РасходнаяНакладная", params)
        items = result if isinstance(result, list) else []

        await self._set_cache(redis_client, cache_key, items, CACHE_TTL_SHORT)
        return items

    async def get_waybill_by_number(
        self,
        number: str,
        redis_client: aioredis.Redis | None = None,
    ) -> dict | None:
        """Получить накладную по номеру."""
        cache_key = f"1c:waybill:{number}"
        cached = await self._get_cache(redis_client, cache_key)
        if cached is not None:
            return cached

        params = {"$filter": f"Number eq '{number}'"}
        result = await self._request("Document_РасходнаяНакладная", params)

        if isinstance(result, list) and result:
            item = result[0]
            await self._set_cache(redis_client, cache_key, item, CACHE_TTL_SHORT)
            return item
        return None

    # ── Контрагенты ──

    async def get_contractors(
        self,
        top: int = 50,
        redis_client: aioredis.Redis | None = None,
    ) -> list[dict]:
        """Получить справочник контрагентов."""
        cache_key = "1c:contractors"
        cached = await self._get_cache(redis_client, cache_key)
        if cached is not None:
            return cached

        params: dict[str, Any] = {"$top": str(top)}
        result = await self._request("Catalog_Контрагенты", params)
        items = result if isinstance(result, list) else []

        await self._set_cache(redis_client, cache_key, items, CACHE_TTL_LONG)
        return items

    async def search_contractor(
        self,
        query: str,
        redis_client: aioredis.Redis | None = None,
    ) -> list[dict]:
        """Поиск контрагента по имени."""
        params = {
            "$filter": f"substringof('{query}', Description)",
            "$top": "10",
        }
        result = await self._request("Catalog_Контрагенты", params)
        return result if isinstance(result, list) else []

    # ── Заказы ──

    async def get_orders(
        self,
        status: str | None = None,
        top: int = 20,
        redis_client: aioredis.Redis | None = None,
    ) -> list[dict]:
        """Получить список заказов."""
        cache_key = f"1c:orders:{status or 'all'}"
        cached = await self._get_cache(redis_client, cache_key)
        if cached is not None:
            return cached

        params: dict[str, Any] = {
            "$top": str(top),
            "$orderby": "Date desc",
        }
        if status:
            params["$filter"] = f"Status eq '{status}'"

        result = await self._request("Document_ЗаказКлиента", params)
        items = result if isinstance(result, list) else []

        await self._set_cache(redis_client, cache_key, items, CACHE_TTL_SHORT)
        return items

    async def update_order_status(
        self,
        order_ref: str,
        new_status: str,
    ) -> bool:
        """Обновить статус заказа в 1С (если есть права на запись)."""
        result = await self._request(
            f"Document_ЗаказКлиента(guid'{order_ref}')",
            method="PATCH",
            json_data={"Status": new_status},
        )
        return result is not None

    # ── Polling (проактивные уведомления) ──

    async def poll_waybill_changes(
        self,
        since_minutes: int = 5,
        redis_client: aioredis.Redis | None = None,
    ) -> list[dict]:
        """Проверить накладные, изменившиеся за последние N минут.

        Используется для проактивных уведомлений при смене статуса.
        """
        # 1С OData не поддерживает $filter по времени изменения напрямую,
        # поэтому сравниваем с кэшированным состоянием.
        current = await self.get_waybills(top=50)
        if not current:
            return []

        cache_key = "1c:waybills_snapshot"
        old_raw = await self._get_cache(redis_client, cache_key)
        old_map: dict[str, str] = {}
        if old_raw and isinstance(old_raw, dict):
            old_map = old_raw

        # Build current state map: number → status
        current_map = {}
        changed = []
        for wb in current:
            num = wb.get("Number", "")
            status = wb.get("Status", "")
            current_map[num] = status
            if num in old_map and old_map[num] != status:
                changed.append({
                    "number": num,
                    "old_status": old_map[num],
                    "new_status": status,
                    "waybill": wb,
                })

        # Save snapshot
        await self._set_cache(redis_client, cache_key, current_map, CACHE_TTL_SHORT)
        return changed

    # ── Cache helpers ──

    async def _get_cache(self, redis_client: aioredis.Redis | None, key: str) -> Any:
        if not redis_client:
            return None
        try:
            raw = await redis_client.get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    async def _set_cache(
        self, redis_client: aioredis.Redis | None, key: str, data: Any, ttl: int
    ) -> None:
        if not redis_client:
            return
        try:
            await redis_client.setex(key, ttl, json.dumps(data, ensure_ascii=False, default=str))
        except Exception:
            pass


# Singleton
one_c = OneCClient()


# ── Format helpers ──

def format_waybill(wb: dict) -> str:
    """Форматировать накладную для отображения в Telegram."""
    num = wb.get("Number", "?")
    date = wb.get("Date", "")[:10]
    status = wb.get("Status", "неизвестен")
    contractor = wb.get("Контрагент", wb.get("Contractor", ""))
    amount = wb.get("СуммаДокумента", wb.get("Amount", ""))

    lines = [f"📄 <b>Накладная {num}</b>"]
    if date:
        lines.append(f"  Дата: {date}")
    if contractor:
        lines.append(f"  Контрагент: {contractor}")
    if amount:
        lines.append(f"  Сумма: {amount} ₽")
    lines.append(f"  Статус: <b>{status}</b>")

    return "\n".join(lines)


def format_waybills_list(waybills: list[dict]) -> str:
    """Форматировать список накладных."""
    if not waybills:
        return "Накладных не найдено."
    return "\n\n".join(format_waybill(wb) for wb in waybills[:10])


def format_contractor(c: dict) -> str:
    """Форматировать контрагента."""
    name = c.get("Description", c.get("Наименование", "?"))
    inn = c.get("ИНН", c.get("INN", ""))
    phone = c.get("Телефон", c.get("Phone", ""))

    lines = [f"👤 <b>{name}</b>"]
    if inn:
        lines.append(f"  ИНН: {inn}")
    if phone:
        lines.append(f"  📞 {phone}")

    return "\n".join(lines)


def format_order(order: dict) -> str:
    """Форматировать заказ."""
    num = order.get("Number", "?")
    date = order.get("Date", "")[:10]
    status = order.get("Status", "")
    contractor = order.get("Контрагент", order.get("Contractor", ""))

    lines = [f"📦 <b>Заказ {num}</b>"]
    if date:
        lines.append(f"  Дата: {date}")
    if contractor:
        lines.append(f"  Клиент: {contractor}")
    if status:
        lines.append(f"  Статус: <b>{status}</b>")

    return "\n".join(lines)

from __future__ import annotations

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

SEC_BASE_URL = "https://api.sec.or.th"
ACTIVE_STATUSES = {"Registered", "IPO"}


async def search_th_funds(query: str, api_key: str) -> list[dict]:
    """Search for active TH mutual funds by name or abbreviation via SEC API v2.

    Uses GET /v2/fund/general-info/profiles with project_info param.
    Returns only Registered/IPO funds.
    """
    if not api_key:
        logger.warning("search_th_funds: no SEC API key provided")
        return []

    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{SEC_BASE_URL}/v2/fund/general-info/profiles",
            headers=headers,
            params={"project_info": query, "page_size": 20},
        )
        resp.raise_for_status()
        data = resp.json()

    results = []
    seen_proj_ids: set[str] = set()
    for item in data.get("items", []):
        if item.get("fund_status") not in ACTIVE_STATUSES:
            continue
        proj_id = item.get("proj_id", "")
        if proj_id in seen_proj_ids:
            continue
        seen_proj_ids.add(proj_id)
        results.append({
            "proj_id": proj_id,
            "proj_abbr_name": item.get("proj_abbr_name", ""),
            "proj_name_en": item.get("proj_name_en", ""),
            "proj_name_th": item.get("proj_name_th", ""),
            "fund_status": item.get("fund_status", ""),
            "management_style": item.get("management_style", ""),
            "policy_desc": item.get("policy_desc", ""),
        })

    logger.info("search_th_funds: query=%r returned %d active results", query, len(results))
    return results

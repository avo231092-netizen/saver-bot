import re
import json
import logging
import asyncio
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def _try_html(url: str) -> dict | None:
    """Parse Ozon product page with browser TLS fingerprint."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
    try:
        resp = cffi_requests.get(url, headers=headers, impersonate="chrome120", timeout=20, allow_redirects=True)
        if resp.status_code not in (200, 307):
            return None
        html = resp.text
        if len(html) < 500:
            return None
        
        soup = BeautifulSoup(html, "lxml")
        
        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else ""
        if not title:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                title = m.group(1).split(" — ")[0].split(" | ")[0]
        if not title:
            title = "Товар Ozon"
        
        price = 0.0
        scripts = soup.find_all("script", type="application/ld+json")
        for s in scripts:
            try:
                data = json.loads(s.string or "{}")
                if isinstance(data, dict):
                    offers = data.get("offers")
                    if offers and isinstance(offers, dict):
                        price = float(offers.get("price", 0))
                        if price > 0:
                            break
            except Exception:
                continue
        
        if price == 0:
            for pattern in [r'"price"\s*:\s*"?(\d+(?:\.\d+)?)"?', r'"salePrice"\s*:\s*"?(\d+(?:\.\d+)?)"?']:
                m = re.search(pattern, html)
                if m:
                    price = float(m.group(1))
                    break
        
        if price == 0:
            meta = soup.find("meta", {"itemprop": "price"})
            if meta:
                price = float(meta.get("content", 0))
        
        if title and price > 0:
            logger.info(f"Ozon: found — {title}, {price}")
            return {"title": title, "price": price, "marketplace": "ozon"}
        return None
    except Exception as e:
        logger.debug(f"Ozon HTML parse failed: {e}")
        return None


async def parse(url: str) -> dict | None:
    """Parse Ozon product using curl_cffi."""
    try:
        logger.info(f"Ozon: parsing {url}")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _try_html, url)
        if not result:
            logger.warning(f"Ozon: all methods failed for {url}")
        return result
    except Exception as e:
        logger.error(f"Ozon parse error: {e}")
        return None

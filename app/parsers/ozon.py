import aiohttp
import re
import json
import logging
from urllib.parse import quote
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

WORKER_URL = "https://empty-voice-cf22.avo231092.workers.dev"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


def proxy_url(target: str) -> str:
    return f"{WORKER_URL}/?url={quote(target, safe='')}"


async def parse(url: str) -> dict | None:
    """Parse Ozon product via Cloudflare Worker proxy."""
    try:
        logger.info(f"Ozon: parsing {url} via proxy")
        
        pu = proxy_url(url)
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20), headers=HEADERS) as session:
            async with session.get(pu, allow_redirects=True) as resp:
                if resp.status not in (200, 307):
                    logger.warning(f"Ozon status {resp.status}")
                    return None
                html = await resp.text()
            
            if len(html) < 500:
                logger.warning(f"Ozon HTML too short: {len(html)}")
                return None
            
            soup = BeautifulSoup(html, "lxml")
            
            # Title
            title_tag = soup.find("h1")
            title = title_tag.get_text(strip=True) if title_tag else ""
            if not title:
                m = re.search(r'<title>([^<]+)</title>', html)
                if m:
                    title = m.group(1).split(" — ")[0].split(" | ")[0]
            if not title:
                title = "Товар Ozon"
            
            # Price
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
            
            logger.warning(f"Ozon: could not extract price for {url}")
            return None
    except Exception as e:
        logger.error(f"Ozon parse error: {e}")
        return None

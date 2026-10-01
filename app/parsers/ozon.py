import aiohttp
import re
import json
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

PROXY_SERVICES = [
    "https://corsproxy.io/?url=",
    "https://api.allorigins.win/raw?url=",
    "https://proxy.cors.sh/",
]


async def parse(url: str) -> dict | None:
    """Parse Ozon product page."""
    try:
        logger.info(f"Ozon: parsing {url}")
        
        urls_to_try = [url]
        for proxy in PROXY_SERVICES[:2]:
            urls_to_try.append(f"{proxy}{url}")
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20), headers=HEADERS) as session:
            for try_url in urls_to_try:
                try:
                    async with session.get(try_url, allow_redirects=True) as resp:
                        if resp.status not in (200, 307):
                            continue
                        html = await resp.text()
                        if len(html) < 500:
                            continue
                        
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
                        # JSON-LD
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
                        
                        # Fallback: regex
                        if price == 0:
                            for pattern in [r'"price"\s*:\s*"?(\d+(?:\.\d+)?)"?', r'"salePrice"\s*:\s*"?(\d+(?:\.\d+)?)"?']:
                                m = re.search(pattern, html)
                                if m:
                                    price = float(m.group(1))
                                    break
                        
                        # Meta tag
                        if price == 0:
                            meta = soup.find("meta", {"itemprop": "price"})
                            if meta:
                                price = float(meta.get("content", 0))
                        
                        if title and price > 0:
                            logger.info(f"Ozon: found — {title}, {price}")
                            return {"title": title, "price": price, "marketplace": "ozon"}
                except Exception as e:
                    logger.debug(f"Ozon parse failed for {try_url}: {e}")
                    continue
            
            logger.warning(f"Ozon: all methods failed for {url}")
            return None
    except Exception as e:
        logger.error(f"Ozon parse error: {e}")
        return None

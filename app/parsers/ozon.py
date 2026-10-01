import aiohttp
import re
import json
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

async def parse(url: str) -> dict | None:
    """Parse Ozon product page and return title + price."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(url, headers=headers, allow_redirects=True) as resp:
                if resp.status != 200:
                    logger.warning(f"Ozon status {resp.status} for {url}")
                    return None
                html = await resp.text()
        soup = BeautifulSoup(html, "lxml")
        # Title
        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else "Товар"
        # Price - Ozon embeds JSON in script tags
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
            # Fallback: regex
            m = re.search(r"\"price\":\s*\"?(\d+(?:\\.\d+)?)\"?", html)
            if m:
                price = float(m.group(1))
        return {"title": title, "price": price, "marketplace": "ozon"}
    except Exception as e:
        logger.error(f"Ozon parse error: {e}")
        return None

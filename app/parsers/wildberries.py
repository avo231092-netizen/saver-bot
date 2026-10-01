import aiohttp
import re
import json
import logging
import asyncio
from urllib.parse import quote
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Cloudflare Worker proxy - bypasses IP block
WORKER_URL = "https://empty-voice-cf22.avo231092.workers.dev"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


def extract_product_id(url: str) -> str | None:
    m = re.search(r"/(?:catalog|product)/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"nm=(\d+)", url)
    if m:
        return m.group(1)
    return None


def proxy_url(target: str) -> str:
    """Wrap target URL with Cloudflare Worker proxy."""
    return f"{WORKER_URL}/?url={quote(target, safe='')}"


async def parse(url: str) -> dict | None:
    """Parse Wildberries product via Cloudflare Worker proxy."""
    try:
        product_id = extract_product_id(url)
        if not product_id:
            logger.warning(f"WB: cannot extract product ID from {url}")
            return None
        
        logger.info(f"WB: parsing product {product_id} via proxy")
        
        # API endpoints to try
        api_urls = [
            f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={product_id}",
            f"https://card.wb.ru/cards/v2/detail?appType=1&curr=amd&dest=-593528&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={product_id}",
            f"https://catalog.wb.ru/catalog/card/v1?nm={product_id}",
        ]
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20), headers=HEADERS) as session:
            # 1. Try API endpoints through proxy
            for api in api_urls:
                try:
                    pu = proxy_url(api)
                    async with session.get(pu) as resp:
                        if resp.status != 200:
                            continue
                        text = await resp.text()
                        if not text.startswith("{"):
                            continue
                        data = json.loads(text)
                        products = data.get("data", {}).get("products", [])
                        if products:
                            p = products[0]
                            title = p.get("name", "Без названия")
                            price = p.get("salePriceU", p.get("priceU", 0)) / 100
                            if price > 0:
                                logger.info(f"WB: found via API — {title}, {price}")
                                return {"title": title, "price": float(price), "marketplace": "wildberries"}
                except Exception as e:
                    logger.debug(f"WB API failed: {e}")
            
            # 2. Fallback: parse HTML page through proxy
            try:
                pu = proxy_url(url)
                async with session.get(pu) as resp:
                    if resp.status not in (200, 307):
                        logger.warning(f"WB HTML status {resp.status}")
                        return None
                    html = await resp.text()
                
                if len(html) < 500:
                    logger.warning(f"WB HTML too short: {len(html)}")
                    return None
                
                soup = BeautifulSoup(html, "lxml")
                title_tag = soup.find("h1")
                title = title_tag.get_text(strip=True) if title_tag else ""
                if not title:
                    m = re.search(r'<title>([^<]+)</title>', html)
                    if m:
                        title = m.group(1).split(" — ")[0].split(" | ")[0]
                if not title:
                    title = "Товар Wildberries"
                
                price = 0.0
                for pattern in [r'"salePriceU"\s*:\s*(\d+)', r'"priceU"\s*:\s*(\d+)', r'"price"\s*:\s*(\d+)']:
                    m = re.search(pattern, html)
                    if m:
                        val = int(m.group(1))
                        price = val / 100 if val > 1000 else float(val)
                        break
                if price == 0:
                    meta = soup.find("meta", {"itemprop": "price"})
                    if meta:
                        price = float(meta.get("content", 0))
                
                if title and price > 0:
                    logger.info(f"WB: found via HTML — {title}, {price}")
                    return {"title": title, "price": price, "marketplace": "wildberries"}
            except Exception as e:
                logger.debug(f"WB HTML parse failed: {e}")
            
            logger.warning(f"WB: all methods failed for product {product_id}")
            return None
    except Exception as e:
        logger.error(f"WB parse error: {e}")
        return None

import aiohttp
import re
import logging
import asyncio
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# Public CORS/API proxy services that can bypass IP blocks
PROXY_SERVICES = [
    "https://corsproxy.io/?url=",
    "https://api.allorigins.win/raw?url=",
    "https://cors-anywhere.herokuapp.com/",
    "https://proxy.cors.sh/",
]


def extract_product_id(url: str) -> str | None:
    m = re.search(r"/(?:catalog|product)/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"nm=(\d+)", url)
    if m:
        return m.group(1)
    return None


async def try_direct_api(session, product_id: str) -> dict | None:
    """Try WB API directly."""
    api_urls = [
        f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={product_id}",
        f"https://card.wb.ru/cards/v2/detail?appType=1&curr=amd&dest=-593528&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={product_id}",
        f"https://catalog.wb.ru/catalog/card/v1?nm={product_id}",
    ]
    for api_url in api_urls:
        try:
            async with session.get(api_url, headers={**HEADERS, "Accept": "application/json"}) as resp:
                if resp.status != 200:
                    continue
                ct = resp.headers.get("Content-Type", "")
                if "json" not in ct and "text" not in ct:
                    continue
                text = await resp.text()
                if not text.startswith("{"):
                    continue
                import json
                data = json.loads(text)
                products = data.get("data", {}).get("products", [])
                if products:
                    p = products[0]
                    title = p.get("name", "Без названия")
                    price = p.get("salePriceU", p.get("priceU", 0)) / 100
                    if price > 0:
                        return {"title": title, "price": float(price), "marketplace": "wildberries"}
        except Exception as e:
            logger.debug(f"WB direct API failed: {e}")
    return None


async def try_proxy_api(session, product_id: str) -> dict | None:
    """Try WB API through public CORS proxies."""
    api_url = f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&hide_dtype=10&ab_testing=false&lang=ru&nm={product_id}"
    for proxy in PROXY_SERVICES:
        try:
            proxy_url = f"{proxy}{api_url}"
            async with session.get(proxy_url, headers={"Accept": "application/json"}, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    continue
                text = await resp.text()
                if not text.startswith("{"):
                    continue
                import json
                data = json.loads(text)
                products = data.get("data", {}).get("products", [])
                if products:
                    p = products[0]
                    title = p.get("name", "Без названия")
                    price = p.get("salePriceU", p.get("priceU", 0)) / 100
                    if price > 0:
                        logger.info(f"WB: found via proxy {proxy}")
                        return {"title": title, "price": float(price), "marketplace": "wildberries"}
        except Exception as e:
            logger.debug(f"WB proxy {proxy} failed: {e}")
    return None


async def try_html_parse(session, url: str) -> dict | None:
    """Try parsing HTML page directly or through proxy."""
    urls_to_try = [url]
    # Also try through proxies
    for proxy in PROXY_SERVICES[:2]:
        urls_to_try.append(f"{proxy}{url}")
    
    for try_url in urls_to_try:
        try:
            async with session.get(try_url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=20), allow_redirects=True) as resp:
                if resp.status not in (200, 307):
                    continue
                html = await resp.text()
                if len(html) < 500:
                    continue
                
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
                # Pattern 1: JSON in script tags
                for pattern in [r'"salePriceU"\s*:\s*(\d+)', r'"priceU"\s*:\s*(\d+)', r'"price"\s*:\s*(\d+)']:
                    m = re.search(pattern, html)
                    if m:
                        val = int(m.group(1))
                        price = val / 100 if val > 1000 else float(val)
                        break
                # Pattern 2: meta tag
                if price == 0:
                    meta = soup.find("meta", {"itemprop": "price"})
                    if meta:
                        price = float(meta.get("content", 0))
                # Pattern 3: visible price
                if price == 0:
                    for cls in ["price-block__final-price", "catalog-page__price", "product-page__price"]:
                        tag = soup.find("span", class_=cls) or soup.find("div", class_=cls)
                        if tag:
                            txt = tag.get_text(strip=True)
                            m = re.search(r'(\d+[\s\d]*)', txt)
                            if m:
                                price = float(m.group(1).replace(" ", "").replace("\xa0", ""))
                                break
                
                if title and price > 0:
                    return {"title": title, "price": price, "marketplace": "wildberries"}
        except Exception as e:
            logger.debug(f"WB HTML parse failed for {try_url}: {e}")
    return None


async def parse(url: str) -> dict | None:
    """Parse Wildberries product — tries API, proxy, HTML."""
    try:
        product_id = extract_product_id(url)
        if not product_id:
            logger.warning(f"WB: cannot extract product ID from {url}")
            return None
        
        logger.info(f"WB: parsing product {product_id}")
        
        async with aiohttp.ClientSession() as session:
            # 1. Direct API
            result = await try_direct_api(session, product_id)
            if result:
                return result
            
            # 2. Through CORS proxy
            result = await try_proxy_api(session, product_id)
            if result:
                return result
            
            # 3. HTML parsing (direct + proxy)
            result = await try_html_parse(session, url)
            if result:
                return result
            
            logger.warning(f"WB: all methods failed for product {product_id}")
            return None
    except Exception as e:
        logger.error(f"WB parse error: {e}")
        return None

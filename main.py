from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
from selectolax.lexbor import LexborHTMLParser
from playwright.async_api import async_playwright
from datetime import datetime
from urllib.parse import urljoin, urlparse
import re
import asyncio
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

NOISE_SELECTORS = ["#cookie", ".modal", ".overlay", ".popup", "[data-testid='cookie-banner']"]
TRUNCATE_LEN = 5000
MIN_STATIC_TEXT = 500

async def extract_meta(html: str, base_url: str):
    parser = LexborHTMLParser(html)
    title = parser.css_first("title") or parser.css_first("meta[property='og:title']")
    title = title.text() if title else ""
    
    desc = parser.css_first("meta[name='description']") or parser.css_first("meta[property='og:description']")
    desc = desc.attributes.get("content", "") if desc else ""
    
    lang = parser.root.attributes.get("lang", "en")
    canonical = parser.css_first("link[rel='canonical']")
    canonical = canonical.attributes.get("href") if canonical else None
    
    return {
        "title": title[:200],
        "description": desc[:500],
        "language": lang,
        "canonical": canonical
    }

async def scrape_sections(html: str, base_url: str):
    parser = LexborHTMLParser(html)
    for sel in NOISE_SELECTORS:
        for node in parser.css(sel):
            node.remove()
    
    landmarks = parser.css("header, nav, main, section, footer, [role='region'], article")
    sections = []
    
    for i, landmark in enumerate(landmarks):
        text_content = landmark.text(strip=True)
        if len(text_content) < 50:
            continue
            
        raw_html = landmark.html
        if len(raw_html) > TRUNCATE_LEN:
            raw_html = raw_html[:TRUNCATE_LEN] + "..."
            truncated = True
        else:
            truncated = False
            
        heading = landmark.css_first("h1, h2, h3")
        label = heading.text(strip=True) if heading else text_content[:57].strip()
        
        # Map to section type
        tag = landmark.tag
        if tag in ["header", "nav"]: section_type = tag
        elif "hero" in label.lower(): section_type = "hero"
        elif any(x in label.lower() for x in ["feature", "product"]): section_type = "features"
        elif any(x in label.lower() for x in ["faq", "question"]): section_type = "faq"
        else: section_type = "section"
        
        content = {
            "headings": [h.text(strip=True) for h in landmark.css("h1, h2, h3")],
            "text": text_content[:1000],
            "links": [],
            "images": [],
            "lists": [],
            "tables": [],
            "rawHtml": raw_html,
            "truncated": truncated
        }
        
        # Extract links
        for a in landmark.css("a[href]"):
            href = a.attributes.get("href", "")
            if href:
                content["links"].append({
                    "text": a.text(strip=True)[:100],
                    "href": urljoin(base_url, href)
                })
        
        # Extract images
        for img in landmark.css("img[src]"):
            src = img.attributes.get("src", "")
            if src:
                content["images"].append({
                    "src": urljoin(base_url, src),
                    "alt": img.attributes.get("alt", "")
                })
        
        # Extract lists
        lists = []
        for list_tag in landmark.css("ul, ol"):
            items = [li.text(strip=True) for li in list_tag.css("li")]
            if items:
                lists.append(items)
        content["lists"] = lists
        
        sections.append({
            "id": f"sec-{i}",
            "type": section_type,
            "label": label,
            "sourceUrl": base_url,
            "content": content
        })
    
    return sections if sections else [{
        "id": "sec-0",
        "type": "unknown",
        "label": "Main Content",
        "sourceUrl": base_url,
        "content": {
            "headings": [],
            "text": parser.body.text(strip=True)[:1000],
            "links": [], "images": [], "lists": [], "tables": [],
            "rawHtml": parser.body.html[:TRUNCATE_LEN],
            "truncated": True
        }
    }]

async def dynamic_scrape(url: str):
    pages = [url]
    clicks = []
    scrolls = 0
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()
        
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=10000)
        
        # Scroll 3 times
        prev_height = await page.evaluate("document.body.scrollHeight")
        for i in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height > prev_height * 1.1:
                scrolls += 1
            prev_height = new_height
        
        # Try common click patterns
        click_selectors = [
            'button:has-text("Load more")',
            'button:has-text("Show more")',
            'button:has-text("more")',
            '[role="tab"]',
            '.load-more',
            '[aria-label*="more"]'
        ]
        
        for selector in click_selectors:
            try:
                await page.click(selector, timeout=3000)
                clicks.append(selector)
                await page.wait_for_timeout(1500)
            except:
                continue
        
        html = await page.content()
        await browser.close()
    
    return html, {"clicks": clicks, "scrolls": scrolls, "pages": pages}

@app.get("/healthz")
async def health():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/scrape")
async def scrape(url: str = Form(...)):
    if not url.startswith("https"):
        return JSONResponse({
            "result": {
                "url": url,
                "scrapedAt": datetime.utcnow().isoformat() + "Z",
                "meta": {"title": "", "description": "", "language": "en", "canonical": None},
                "sections": [],
                "interactions": {"clicks": [], "scrolls": 0, "pages": [url]},
                "errors": [{"message": "Only HTTPS URLs supported", "phase": "validation"}]
            }
        })
    
    try:
        # Try static first
        resp = httpx.get(url, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
        html = resp.text
        sections = await scrape_sections(html, url)
        
        total_text = sum(len(s["content"]["text"]) for s in sections)
        strategy = "static"
        
        # Fallback to dynamic if static content is insufficient
        if total_text < MIN_STATIC_TEXT or len(sections) < 2:
            html, interactions = await dynamic_scrape(url)
            sections = await scrape_sections(html, url)
            strategy = "dynamic"
        else:
            interactions = {"clicks": [], "scrolls": 0, "pages": [url]}
        
        return {
            "result": {
                "url": url,
                "scrapedAt": datetime.utcnow().isoformat() + "Z",
                "meta": await extract_meta(html, url),
                "sections": sections,
                "interactions": interactions,
                "errors": []
            }
        }
    except Exception as e:
        return JSONResponse({
            "result": {
                "url": url,
                "scrapedAt": datetime.utcnow().isoformat() + "Z",
                "meta": {"title": "", "description": "", "language": "en", "canonical": None},
                "sections": [],
                "interactions": {"clicks": [], "scrolls": 0, "pages": [url]},
                "errors": [{"message": str(e), "phase": "scrape"}]
            }
        })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

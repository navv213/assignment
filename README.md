Visit http://localhost:8000

## Test URLs
1. **Static**: https://en.wikipedia.org/wiki/Artificial_intelligence - Clean static content
2. **JS-Heavy**: https://vercel.com - Tabs, dynamic rendering  
3. **Pagination**: https://news.ycombinator.com - Infinite scroll depth 3

## Features Implemented
- ✅ Static scraping (httpx + selectolax)
- ✅ JS rendering fallback (Playwright)
- ✅ Click flows (Load more, tabs)
- ✅ Infinite scroll (3x depth)
- ✅ Section-aware JSON schema
- ✅ Noise filtering (cookie banners, modals)
- ✅ Frontend JSON viewer + download

## Limitations
- Same-origin only
- No aggressive retries
- Tables parsing basic (array format)

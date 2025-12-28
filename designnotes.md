# Design Notes

## Static vs JS Fallback
Static scraping first using httpx + selectolax. Fallback to Playwright if total text < 500 chars OR < 2 sections found.

## Wait Strategy for JS
- `wait_until="networkidle"` (30s timeout)
- Additional `wait_for_load_state("networkidle")` (10s)
- 2s delays after scrolls/clicks

## Click/Scroll Strategy
**Scrolls**: 3x full page scroll, check height change >10%
**Clicks**: Try selectors `button:has-text("Load more")`, `button:has-text("Show more")`, `[role="tab]`
**Stop**: Max 3 scrolls/clicks per type, 3s timeout per click

## Section Grouping/Labels
**Landmarks**: `header, nav, main, section, footer, [role='region'], article`
**Type mapping**: header/nav → nav/hero/features/faq/section/unknown
**Label**: h1-h3 or first 57 chars of text

## Noise Filtering/Truncation
**Filtered**: `#cookie`, `.modal`, `.overlay`, `.popup`, `[data-testid='cookie-banner']`
**Truncation**: rawHtml 5000 chars, content.text 1000 chars

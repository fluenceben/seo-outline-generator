# SEO Content Outline Generator

A local wizard for building SEO content briefs: pick an intent, enter a primary/secondary
keyword and your client's site, review the top 10 Google results and select the ones that
are actually intent-relevant, then pull their headers and TF-IDF terms into an editable
outline (title, H1, H2/H3s, and FAQ suggestions).

## Setup

1. **Install dependencies** (system Python 3.9+, no other runtime needed):

   ```bash
   cd seo-outline-generator
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Get a Serper API key:**
   - Sign up at https://serper.dev (Google sign-in works) and copy the API key from the
     dashboard.
   - Free tier includes 2,500 queries; paid usage is prepaid credit packs after that.
   - (Google's Custom Search API no longer supports whole-web search for newly created
     Programmable Search Engines, so this app uses Serper instead.)

3. **Get an Anthropic API key** (powers the "Generate with AI" outline step):
   - Sign up at https://console.anthropic.com and create a key under Settings → API Keys.
   - Uses `claude-sonnet-5`; each generation call is small, typically a few cents.

4. **Configure environment variables:**

   ```bash
   cp .env.example .env
   # then edit .env and fill in SERPER_API_KEY and ANTHROPIC_API_KEY
   ```

5. **Run it:**

   ```bash
   python3 app.py
   ```

   Open http://localhost:5001

## Workflow

1. **Setup** — choose the page intent (service, informational, blog, product, category),
   enter your primary keyword, optional secondary keywords, and your client's site (used to
   exclude their own domain from the competitor set).
2. **Pick results** — the top 10 Google results for your primary keyword come back with
   title/snippet; check the ones that are actually intent-relevant.
3. **Headers & terms** — the tool scrapes each selected page, extracts every H1–H6, and
   computes TF-IDF terms across their body text as a topical-coverage reference. Similar
   headers are clustered across competitors and ordered to flow like real content, split into
   a "Recommended outline" (covered by 2+ competitors) and "Alternate headers" (single-source)
   pool you can drag between. Click **Generate with AI** to have Claude write an original
   outline and FAQ list instead — informed by competitor coverage but not copied from it.
4. **Build outline** — selected headers land in an editable outline builder (level dropdown,
   reorder, remove); title/H1 are pre-filled from intent-based templates and editable.
5. **Export** — copy or download the finished outline as Markdown.

## Notes

- All Serper and Anthropic API calls happen server-side — keys never reach the browser.
- Scraping is best-effort: pages that block requests, time out, or aren't HTML are skipped
  with a warning rather than failing the whole batch.
- FAQ suggestions default to question-phrased headers found on competitor pages; "Generate
  with AI" replaces them with Claude-written questions grounded in the same source material.

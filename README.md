# kobo-xray-plugin
A Calibre plugin that generates Kindle X-Ray style metadata for Kobo using NLP and local AI.

## What it does
- Scans an EPUB for characters, locations, factions, and key items using NLP.
- Intelligently groups character aliases based on text co-occurrence and substring relations.
- Generates short, spoiler-free Kindle X-Ray style descriptions using a local LLM.
- Embeds the generated metadata into the book for use with a custom Kobo dictionary/popup.

## Status
🚧 Work in progress (Backend Data Pipeline Complete)

## Tech Stack
- **Python**
- **BeautifulSoup4** (EPUB HTML parsing and text extraction)
- **spaCy** (Named Entity Recognition)
- **Ollama** (Local LLM inference, optimized for Qwen 3.5)
- **Calibre Plugin API**

## Progress
- [x] **Basic text extraction from EPUB**
  - Chapter filtering working (prologue, epilogue, parts)
  - HTML and image tag stripping working
- [x] **NER with spaCy**
  - Created NER map with frequency and context tracking
  - Alias filtering and cleaning (substring and co-occurrence relation mapping implemented)
- [x] **LLM description generation**
  - Integrated local inference via Ollama
  - Implemented strict JSON formatting and hallucination guardrails
  - Implemented anti-spoiler prompt constraints (context-locked generation)
  - Built an end-to-end, in-memory master pipeline (`main.py`)
- [ ] **Calibre plugin wrapper**
  - Build UI for model selection/generation
- [ ] **Kobo metadata format**
  - Inject JSON data as EPUB3 footnotes/invisible links for native Kobo popups
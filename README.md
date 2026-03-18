# kobo-xray-plugin
A Calibre plugin that generates Kindle X-Ray style metadata for Kobo using NLP

## What it does
- Scans an ebook for characters, locations, and key items using NLP
- Generates short descriptions using a local LLM
- Embeds metadata into the book for use with a custom Kobo dictionary

## Status
🚧 Work in progress

## Tech Stack
- Python
- spaCy (Named Entity Recognition)
- Ollama (local LLM for description generation)
- Calibre Plugin API

## Progress
- [x] Basic text extraction from epub
  - Chapter filtering working (prologue, epilogue, parts)
  - Image tag stripping is working
- [x] NER with spaCy
  - Created NER map 
  - Need Aliase filtering and cleaning
- [ ] Character relationship mapping
- [ ] LLM description generation
- [ ] Calibre plugin wrapper
- [ ] Kobo metadata format

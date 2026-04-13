# 📖 kobo-xray-plugin

> Kindle's X-Ray feature, rebuilt for Kobo e-readers.

A Calibre plugin + standalone Python pipeline that replicates Kindle's X-Ray experience on Kobo devices. It extracts named entities from your EPUB using spaCy, generates AI summaries with a local Ollama model, and injects interactive footnote links directly into the book — no cloud, no API keys, no data leaving your machine.

---

## ✨ What it does

When you tap a character name, location, or faction while reading on your Kobo, a popup appears with an AI-generated summary of who or what that entity is — based entirely on what the book has revealed up to that point.

- **NER extraction** — spaCy (`en_core_web_trf`) identifies characters, locations, factions, and items
- **AI summarization** — Ollama (`qwen2.5:9b`) generates contextual summaries per entity
- **Spoiler prevention** — summaries are scoped to the chapter you're currently reading
- **EPUB injection** — footnote links injected directly into chapter HTML
- **Calibre integration** — runs as a right-click action inside your Calibre library with a live terminal progress window

---

## 🏗️ Architecture

```
Calibre Plugin (ui.py)
        │
        │  QProcess (subprocess)
        ▼
XRAY-ENGINE (PyInstaller .exe)
        │
        ├── Extractor.py   — reads EPUB spine, strips HTML, extracts chapter text
        ├── ner.py         — spaCy NER + substring & co-occurrence relation mapping
        ├── summary.py     — builds Ollama prompts, generates JSON summaries
        └── Injector.py    — injects xray_footnotes.xhtml + <a> links into EPUB
```

**Two components, one workflow:**
- The **Calibre plugin** is a thin UI — it locates the engine exe, launches it via `QProcess`, and streams stdout to a live progress terminal
- The **engine** is a fully self-contained Python pipeline distributed as a PyInstaller `--onedir` exe

---

## 📦 Pipeline Stages

### Stage 1 — Extraction (`Extractor.py`)
Reads the EPUB spine in reading order, filters to chapter/prologue/epilogue documents, strips images and HTML tags, and returns clean paragraph text per chapter.

### Stage 2 — NER (`ner.py`)
Runs `en_core_web_trf` over chunked paragraphs via `nlp.pipe()` for GPU-batched processing. Builds an entity map with:
- Type classification (`character`, `location`, `faction`, `item`)
- First occurrence chapter (for spoiler scoping)
- Up to 3 deduplicated context paragraphs
- Frequency tracking
- Alias linking via substring and co-occurrence relations

### Stage 3 — Summarization (`summary.py`)
Builds a rich prompt per entity including name, type, frequency, first occurrence, top aliases, and context paragraphs. Calls Ollama with `format="json"` and `think=False` for structured output.

### Stage 4 — Injection (`Injector.py`)
Generates `xray_footnotes.xhtml` with `<aside epub:type="footnote">` entries per entity. Walks text nodes in each chapter and wraps matched entity names in `<a epub:type="noteref">` links. Patches EPUB3 namespace, fixes ebooklib TOC UID bug, and writes the final EPUB.

---

## 🚀 Getting Started

### Requirements

- [Calibre](https://calibre-ebook.com) (5.0+)
- [Ollama](https://ollama.ai) with `qwen2.5:9b` pulled
- GPU recommended (RTX 4070 Mobile: ~42 min for a full novel)
- CUDA-compatible environment for `en_core_web_trf`

### Installation

1. Download the latest release from [Releases](#)
2. In Calibre → Preferences → Plugins → Load plugin from file → select the `.zip`
3. On first use, the plugin will prompt you to locate the engine `.exe`
4. Select a book in your library → right-click the X-Ray button → **Run X-Ray on EPUB**

---

## 🗺️ Roadmap

- [x] Chapter extraction with spine-ordered reading
- [x] spaCy NER with GPU batching
- [x] Substring + co-occurrence alias mapping
- [x] Ollama summarization with structured JSON output
- [x] EPUB footnote injection
- [x] Calibre plugin with live progress terminal
- [x] PyInstaller distribution
- [ ] Fix popup behavior (footnotes opening as full page instead of popup)
- [ ] Direct KEPUB injection for Kobo (bypass Calibre KEPUB converter stripping)
- [ ] Spoiler-aware summary serving by chapter
- [ ] Co-occurrence surname clustering (e.g. "Kholin" → correct full name)
- [ ] Community cloud cache for summaries (high-quality mode)
- [ ] Lightweight fallback model for lower-spec hardware (`qwen2.5:0.8b`)

---

## ⚠️ Known Issues

**Footnotes open as a full page instead of a popup on Kobo**
The Kobo firmware requires the footnote document to be in the manifest but *not* in the spine to trigger popup behavior. Calibre's KEPUB converter strips injected `epub:type="noteref"` attributes and inline styles during conversion. The current fix being explored is injecting directly into already-converted KEPUB files on the device via USB, bypassing the converter entirely.

---

## 🛠️ Development

```bash
# Create virtual environment (Python 3.11.9 required — spaCy/pydantic incompatibility with 3.14)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install spacy ebooklib beautifulsoup4 nltk ollama
python -m spacy download en_core_web_trf

# Run the pipeline directly
python main.py path/to/your/book.epub
```

**PyInstaller build:**
```bash
pyinstaller --onedir main.py --hidden-import spacy_curated_transformers
```

---

## 📜 License

MIT
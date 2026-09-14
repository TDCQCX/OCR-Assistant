# OCR Assistant

[简体中文](README.md) | [English](README.en.md)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![React](https://img.shields.io/badge/UI-React%2018-61DAFB?logo=react&logoColor=white)
![Tailwind](https://img.shields.io/badge/Style-Tailwind%20CSS-38BDF8?logo=tailwindcss&logoColor=white)
![pywebview](https://img.shields.io/badge/Shell-pywebview%20%2B%20Qt-41CD52?logo=qt&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey)
![Version](https://img.shields.io/badge/Version-2.4.0-orange)

> **OCR Assistant** — a desktop tool with three capture modes, cloud/local OCR and LLM-powered image-and-text Q&A.
> The interface is built with **React 18 + Tailwind CSS**; the backend is Python (capture / OCR / model calls / configuration).

Align the capture area over anything on screen (questions, documents, web pages, code...), then with one click it completes **capture → text recognition → LLM understanding & answering**. Results are shown in collapsible sections — no window switching required.

## Four Modes

| Mode | Description | Hotkey |
|---|---|---|
| **Overlay window** | An always-on-top transparent hole that is the capture area; **clicks pass through the hole** to the content behind | `Ctrl+1` |
| **Free snipping** | Full-screen mask; drag to select a region. The action bar embeds engine switches, language pair and the question box: **Recognize / Translate this area / Set as overlay area** | `Ctrl+Shift+A` / `Ctrl+3` |
| **Mini bar** | Icon toolbar plus a question input row; docked centered above the taskbar on first use and freely draggable | `Ctrl+2` |
| **Translate** | A hole-free window with enlarged OCR/translation panes; sentence/paragraph bilingual view and offline on-device translation | top switcher |

> Switch modes anytime from the top switcher or with hotkeys. `Ctrl+F1` triggers recognition in overlay mode and opens region selection in mini-bar mode.

## Features

- **Transparent-hole overlay**: only the hole is see-through, the rest is an opaque panel; drag to reposition, adjust hole width/height, window size is remembered
- **Click-through OCR region**: clicks inside the hole reach the content behind it, while the hole border stays visible
- **Dual OCR modes**: **Cloud** (recognized by the selected LLM, higher accuracy) or **Local** (built-in RapidOCR, offline & free, ~50 MB, CPU 100–300 ms), switchable from the main UI
- **Dual translation modes**: cloud LLM translation or offline on-device translation (Argos models, optionally local Ollama); the chosen language pair is injected into the request
- **Bilingual view**: OCR text is split into sentences/paragraphs, each original block followed by its translation; switch between bilingual / translation-only / source-only
- **Window edge resize**: drag any edge or corner to resize; size and position are remembered
- **Multiple AI platforms**: Alibaba Bailian / OpenAI / DeepSeek / Zhipu GLM / Kimi / Ollama plus custom platforms; configured and unconfigured platforms are grouped separately with hover-to-delete and editable names
- **Image-text Q&A**: both the OCR text and the screenshot are sent to the model, combined with structured question parsing (type / question / options); thinking mode can be disabled for speed
- **Local knowledge base**: keyword hits return answers instantly without calling the API; AI answers can be auto-added
- **Global theme + custom themes**: 5 presets (light / dark / gray / eyecare / high-contrast) with per-item colors (including panel / card / inset layer tokens), corner radius, font size, panel opacity and hole border style; themes can be exported/imported as JSON and stay in sync across all windows
- **Flat icon UI**: every icon is a built-in SVG (no emoji) with hover hints, keeping the layout compact
- **Recognition history**: the last 100 results can be reviewed, copied or cleared
- **Request history**: GitHub-style gray-to-green grid covering the last 20 weeks
- **Editable JSON request template**: live preview with validation, fully customizable model parameters
- **Question presets**: built-in examples (answer / translate / explain / summarize / find related info) with auto-saved custom input
- **More settings**: image compression limit, default question, custom hotkeys, cache & question storage paths, auto-add answers, connection test with response time

## Architecture

```
┌─────────── Frontend React 18 + Tailwind (built with Vite) ───────────┐
│  index.html?view=overlay | mini | settings        selector.html      │
│  components: Overlay / MiniBar / Settings / Snip / ui / theme        │
└──────────────────────────────┬──────────────────────────────────────┘
                     pywebview js_api (JSON bridge)
┌──────────────────────────────┴──────────────────────────────────────┐
│  Backend Python: manager (windows/modes/flow) · api (bridge)        │
│  capturer (mss) · agent (model calls) · worker (recognition flow)   │
│  question_parser · local_ocr · config / history / request_log       │
└─────────────────────────────────────────────────────────────────────┘
```

- Desktop shell: **pywebview** (Qt / WebEngine backend) providing transparency, frameless always-on-top windows, dragging and global hotkeys
- All window and WebView operations are marshalled to the Qt main thread through `app/mainthread.py`

## Requirements

- Windows 10 / 11
- Python 3.10+ *(only needed for running from source; the packaged build needs no Python)*
- Node.js 18+ *(only needed for frontend development)*

## Installation & Running

### Option 1: Packaged build (recommended)

Download the executable for your version from [Releases](../../releases) and double-click to run.

### Option 2: Run from source

```powershell
git clone https://github.com/TDCQCX/OCR-Assistant.git
cd OCR-Assistant

# Create a virtual environment and install dependencies
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Run (or double-click start.bat)
.\.venv\Scripts\python.exe main.py
```

### Frontend development (optional)

```powershell
cd frontend
npm install
npm run build     # builds into app/webui, loaded automatically by the backend
npm run dev       # hot-reload debugging in the browser
```

## Quick Start

1. On launch the app opens in **overlay mode**; the area with the red border is the capture hole.
2. **Position**: drag the top/bottom panels to align the hole with the target, or set the hole width/height precisely at the bottom.
3. Type your question in the **Question / Instruction** box (default: "请给出该题目的答案").
4. Click **Capture & Recognize** (or press `Ctrl+F1`) to see 【Recognition Result】and【Answer】within seconds.
5. For a one-off selection press `Ctrl+Shift+A` for **free snipping mode**, drag a region and choose **Recognize** or **Set as overlay area**.

> Before first use, open **Settings → Model Settings** and fill in the **API Key** and **Model ID** for the selected platform (stored locally in `config.json`, never uploaded).

## Configuration

Click **Settings** at the top to open the settings window (left navigation):

- **Model Settings**: AI platform management (configured/unconfigured sections, hover to delete, custom platforms) plus detailed settings (name, connection test, note, homepage, API Key, Model ID, Base URL, thinking mode, JSON request preview and template editing)
- **General Settings**: AI settings (cloud/local OCR, max response time, retry count, image compression limit), storage (cache/question directories, auto-add), behavior & hotkeys, prompts
- **Appearance & Themes**: 5 presets + custom color editor + radius / font size / panel opacity / hole border + theme import & export
- **Recognition History**: review and clear results
- **About**: version info, request history grid, GitHub & QQ group, open-source license

`config.json` is grouped by purpose: `active_provider` / `providers` / `prompts` / `request_template` / `mode` / `ui` / `window` / `capture` / `timeout` / `retry` / `ocr` / `knowledge` / `hotkeys` / `behavior` / `storage` / `app`.

## Hotkeys

| Hotkey | Function |
|---|---|
| `Ctrl+F1` | Recognize (overlay) / start region selection (mini bar) |
| `Ctrl+Shift+A` | Free snipping mode |
| `Ctrl+1` / `Ctrl+2` / `Ctrl+3` | Switch overlay / mini bar / free snipping |
| `Ctrl+Q` | Quit |

Configurable under **Settings → General Settings → Behavior & Hotkeys**.

## FAQ

- **"API Key not configured"**: fill in the Key for the current platform under Settings → Model Settings (settings are saved automatically when the window closes).
- **401/403 errors**: invalid API Key or no permission for the model; use **Test connection** to diagnose quickly.
- **Local OCR errors**: make sure `rapidocr_onnxruntime` is installed in the source environment.
- **Capture area not matching the hole**: the app is Per-Monitor V2 DPI aware and supports multi-monitor setups with different scaling; adjust the hole size and retry if it looks off.
- **How to change prompts / request template**: Settings → General Settings (prompts) and Model Settings (JSON preview → Edit Template).

## Contact & Community

- GitHub: [https://github.com/TDCQCX/OCR-Assistant](https://github.com/TDCQCX/OCR-Assistant)
- QQ Group: **1108236960**

## License

Licensed under **[CC BY-NC 4.0](LICENSE) (Attribution-NonCommercial 4.0 International)**:

- **Non-commercial only** — you may not sell, paywall, or embed this project in a commercial product;
- **Attribution required** — any redistribution, mirror or derivative work must credit the original author
  and link to [https://github.com/TDCQCX/OCR-Assistant](https://github.com/TDCQCX/OCR-Assistant),
  and must keep this license text intact;
- Personal, academic and other non-commercial use (including modification and redistribution) is welcome.

> Note: CC BY-NC 4.0 is not an OSI-approved open-source license. The NLLB-200 models used by the
> balanced/full on-device translation tiers are themselves CC BY-NC 4.0. Third-party components
> (PySide6/Qt, RapidOCR, etc.) remain under their own licenses — see [LICENSE](LICENSE).

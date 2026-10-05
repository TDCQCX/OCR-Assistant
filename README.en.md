# OCR Assistant

[简体中文](README.md) | [English](README.en.md)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![React](https://img.shields.io/badge/UI-React%2018-61DAFB?logo=react&logoColor=white)
![Tailwind](https://img.shields.io/badge/Style-Tailwind%20CSS-38BDF8?logo=tailwindcss&logoColor=white)
![pywebview](https://img.shields.io/badge/Shell-pywebview%20%2B%20Qt-41CD52?logo=qt&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey)
![Version](https://img.shields.io/badge/Version-2.6.10-orange)

> **OCR Assistant** — a desktop tool with four modes (overlay / free snipping / mini bar / translate), cloud & on-device OCR and LLM-powered image-and-text Q&A.
> The interface is built with **React 18 + Tailwind CSS**; the backend is Python (capture / OCR / model calls / configuration).

Align the capture area over anything on screen (questions, documents, web pages, code...), then with one click it completes **capture → text recognition → LLM understanding & answering**. The recognized text and the answer are shown side by side on white cards, both directly selectable and copyable, while the bottom status bar reports the engine, model and timings used. No window switching required.

## Four Modes

| Mode | Description | Hotkey |
|---|---|---|
| **Overlay window** | An always-on-top transparent hole that is the capture area; **clicks pass through the hole** to the content behind; drag any edge or corner to resize | `Ctrl+1` |
| **Free snipping** | Full-screen mask; drag to select a region. The action bar embeds engine switches, language pair and the question box: **Recognize / Translate this area / Set as overlay area** | `Ctrl+Shift+A` / `Ctrl+3` |
| **Mini bar** | Icon toolbar plus a single-line question input row; docked centered above the taskbar on first use and freely draggable; a minimum width keeps the top-right buttons from being squeezed out | `Ctrl+2` |
| **Translate** | A hole-free window with the source and translation in **two side-by-side columns**, white cards, selectable and independently scrollable; offline on-device translation supported | `Ctrl+4` |

> Switch modes anytime from the top switcher or with hotkeys. `Ctrl+F1` triggers recognition in overlay mode and opens region selection in mini-bar mode.
> All four mode windows use the theme corner radius (the settings window excepted).

## Features

- **Built-in onboarding guide (speech bubble + arrow)**: a step-by-step walkthrough for each mode (the four capture modes plus the settings window), started automatically the first time you enter a mode. The target control is outlined while the rest is dimmed, the bubble explains the step and an arrow points at it; Previous / Next / Skip are supported. Click-through of the hole is paused during the guide and restored afterwards. Settings → Guide lets you replay any mode or reset all guides
- **Transparent-hole overlay**: only the hole is see-through, the rest is an opaque panel; drag to reposition; window size and position are remembered
- **Click-through OCR region**: clicks inside the hole reach the content behind it, while the hole border stays visible
- **Dual OCR modes**: **Cloud** (recognized by the selected LLM, higher accuracy) or **Local** (built-in RapidOCR, offline & free, ~50 MB, CPU 100–300 ms), switchable from the main UI
- **Dual translation modes**: cloud LLM translation or offline on-device translation (Argos models, optionally local Ollama); the chosen language pair is injected into the request
- **Bilingual view**: OCR text is split into sentences/paragraphs, each original block followed by its translation; switch between bilingual / translation-only / source-only
- **Window edge resize**: drag any edge or corner to resize; size and position are remembered (correctly converted under high DPI scaling)
- **Multiple AI platforms**: Alibaba Bailian / OpenAI / DeepSeek / Zhipu GLM / Kimi / Ollama plus custom platforms; configured and unconfigured platforms are grouped separately with hover-to-delete and editable names
- **Image-text Q&A**: both the OCR text and the screenshot are sent to the model, combined with structured question parsing (type / question / options); thinking mode can be disabled for speed
- **Local knowledge base**: keyword hits return answers instantly without calling the API; AI answers can be auto-added
- **Global theme + custom themes**: 5 presets (light / dark / gray / eyecare / high-contrast) with per-item colors (including panel / card / inset layer tokens), corner radius, font size, panel opacity and hole border style; themes can be exported/imported as JSON and stay in sync across all windows
- **Custom background image**: lay a local image behind the panels and tune opacity, blur, dimming and fit independently; the overlay hole always stays transparent, so click-through and capture are unaffected
- **Flat icon UI**: every icon is a built-in SVG (no emoji) with hover hints that automatically avoid the hole, keeping the layout compact
- **Recognition history (timeline)**: vertical axis with relative timestamps, stat cards for total records / knowledge-base hit rate / average duration, filtering by all / Q&A / translation / knowledge base, per-entry expand and copy
- **Request history**: GitHub-style gray-to-green grid plus total / failed / success-rate / average-duration stat cards
- **Editable JSON request template**: live preview with validation, fully customizable model parameters
- **Single-line question input**: every mode uses a single-line input; **Enter triggers the matching action** (overlay → recognize, translate → re-translate, mini bar → snipping recognition, snipping → recognize). Your own input is remembered automatically and the presets are editable in Settings
- **Cloud / on-device segmented switch**: the engine switch in the top bar is a two-segment capsule with the active side highlighted; switching to on-device also updates the model chip to the on-device tier instead of still showing the cloud model
- **Modal settings window**: while Settings is open the main window disables input, so you cannot mis-click it; it is restored as soon as Settings closes
- **More settings**: image compression limit, default question, **8 customizable hotkeys (captured by pressing keys)**, cache & question storage paths, auto-add answers, connection test with response time

## Architecture

```
┌─────────── Frontend React 18 + Tailwind (built with Vite) ───────────┐
│  index.html?view=overlay | mini | translate | settings              │
│  selector.html (full-screen region picking)                          │
│  components: Overlay / MiniBar / Translate / Settings / Snip /       │
│              Guide / QuitDialog / ui (controls) / theme / bridge     │
└──────────────────────────────┬──────────────────────────────────────┘
                     pywebview js_api (JSON bridge)
┌──────────────────────────────┴──────────────────────────────────────┐
│  Backend Python                                                     │
│   manager (windows/modes/flow/tray/hotkeys) · api (bridge)          │
│   mainthread (Qt main-thread marshalling)                           │
│   capturer (mss capture) · winutil (DPI & hole-region maths)        │
│   agent (model calls) · worker (recognition/translation flow)       │
│   question_parser · local_ocr · local_mt/local_hf (on-device)       │
│   local_translate · local_models · config / history / request_log   │
└─────────────────────────────────────────────────────────────────────┘
```

- Desktop shell: **pywebview** (Qt / WebEngine backend) providing transparency, frameless always-on-top windows, dragging and global hotkeys
- All window and WebView operations are marshalled to the Qt main thread through `app/mainthread.py`
- Capture coordinates and hole regions are converted in one place (`app/winutil.py`) between logical and physical pixels, so high-DPI and multi-monitor setups line up

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
2. **Position**: drag the top/bottom panels to align the hole with the target; resize the window by dragging any edge or corner.
3. Type your question in the **Question / Instruction** box (default: "请给出该题目的答案") and press `Enter`, or click **Recognize**.
4. Within seconds you will see 【Recognition Result】and【Answer】. Both panes are selectable and copyable, and the status bar shows the engine, model and timings for this run.
5. For a one-off selection press `Ctrl+Shift+A` for **free snipping mode**, drag a region and choose **Recognize**, **Translate this area** or **Set as overlay area**.

> Before first use, open **Settings → Model Settings** and fill in the **API Key** and **Model ID** for the selected platform (stored locally in `config.json`, never uploaded).

## Configuration

Click **Settings** at the top to open the settings window (left navigation):

- **Model Settings**: the AI platform list on the left stays fixed (only that list scrolls on its own) while the form scrolls on the right; configured/unconfigured sections, a radio to pick the active platform, a common-model dropdown, connection test, note, homepage, API Key, Model ID, Base URL, thinking mode, JSON request preview and template editing
- **General Settings**: AI settings (cloud/local OCR, max response time, retry count, image compression limit), storage (cache/question directories, auto-add), behavior & **8 hotkeys (click a field and press the key combination to record it)**, prompts
- **Translate Settings**: translation engine (cloud/on-device), on-device engine, default language pair, display mode, **on-device model management (download / switch tier / delete on demand)**, auto refresh, question and prompts
- **Appearance & Themes**: 5 presets + custom color editor + radius / font size / panel opacity / hole border + **custom background image** + theme import & export
- **Recognition History**: timeline review (stat cards + filtering + expand + copy) and clearing
- **Guide**: replay the walkthrough for any mode, reset all
- **About**: version info, request-history grid and stats, GitHub & QQ group, open-source license

`config.json` is grouped by purpose: `active_provider` / `providers` / `prompts` / `request_template` / `mode` / `ui` (theme and background image) / `window` / `capture` / `timeout` / `retry` / `ocr` / `translate` / `local` (on-device tiers and download source) / `knowledge` / `hotkeys` / `behavior` / `storage` / `app`.
Before each write the previous file is kept as `config.json.bak`, so a mistyped key or a corrupted config can be recovered.

## Hotkeys

| Hotkey | Function |
|---|---|
| `Ctrl+F1` | Recognize (overlay) / start region selection (mini bar) |
| `Ctrl+Shift+A` | Free snipping mode |
| `Ctrl+1` / `Ctrl+2` / `Ctrl+3` / `Ctrl+4` | Switch overlay / mini bar / free snipping / translate |
| `Ctrl+T` | Toggle always-on-top |
| `Ctrl+Q` | Quit |

All 8 are configurable under **Settings → General Settings → Behavior & Hotkeys**: click a field and press the key combination to record it (shown live), `Backspace` clears it and each field has a one-click reset to default. Changes take effect immediately.

## FAQ

- **"API Key not configured"**: fill in the Key for the current platform under Settings → Model Settings (settings are saved automatically when the window closes).
- **401/403 errors**: invalid API Key or no permission for the model; use **Test connection** to diagnose quickly.
- **Local OCR errors**: make sure `rapidocr_onnxruntime` is installed in the source environment.
- **Capture area not matching the hole**: the app is Per-Monitor V2 DPI aware, supports multi-monitor setups with different scaling, and converts window coordinates to physical pixels in one place; if it still looks off, please report your scaling factor and window position.
- **Settings pages feel slow to switch**: the on-device model status now caches directory-size scans and refines them in the background (`models/` often holds thousands of files). The very first visit may still take a moment, then it is instant.
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

## On-device (offline) models

On-device OCR and translation are **offline and free**. Models are not bundled; they are downloaded on demand:

- Open **Settings → Translate Settings → On-device model management** and download what you need:
  - **OCR recognition** in three tiers: Light (~16 MB) / Balanced (~120 MB, recommended) / Full (~196 MB);
  - **On-device translation**: Light (dedicated small model) / Balanced / Full (official NLLB-200 — better quality, larger and slower);
  - **Inference runtime**: ~62 MB for the Light tier; the Balanced/Full tiers need the official runtime (~2.5 GB, one-time).
- On slow networks, switch the download source to **hf-mirror** in the same panel.
- Alternatively use a local [Ollama](https://ollama.com) instance (Settings → Translate Settings → on-device engine → Ollama).
- The source environment still keeps `argostranslate` as a fallback engine (optional):
  `.\\.venv\\Scripts\\python.exe -m pip install argostranslate`

# OCR Assistant

[简体中文](README.md) | [English](README.en.md)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green?logo=qt&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Version](https://img.shields.io/badge/Version-1.0.0-orange)

> **OCR Assistant** — a desktop tool with a transparent capture hole, cloud/local OCR recognition and LLM-powered image-and-text Q&A.

Align the transparent hole of the floating window over anything on screen (questions, documents, code...), then with one click it completes **capture → text recognition → LLM understanding & answering**. Results are shown in collapsible sections — no window switching required.

## Features

- **Transparent capture window**: only the hole is see-through; the rest is an opaque panel. Drag to position, drag edges to resize (size is remembered). Result/answer sections are collapsible; the window height follows content while the capture hole stays unchanged.
- **Dual OCR modes**:
  - **Cloud**: uses the selected LLM for recognition (higher accuracy, consumes tokens).
  - **Local**: built-in RapidOCR (ONNX Runtime, PP-OCR models, ~50 MB, offline & free, CPU 100-300 ms).
- **Multiple AI platforms**: one-click switching among Alibaba Bailian / OpenAI / DeepSeek / Zhipu GLM / Kimi / Ollama, plus custom platforms (editable name/logo, deletable). Unconfigured platforms are shown dimmed.
- **Image-text Q&A**: both the OCR text and the screenshot are sent to the model, combined with structured question parsing (type / question / options) for better answers; thinking mode can be disabled for speed.
- **Local knowledge base**: keyword hits return answers instantly without calling the API (millisecond-level, zero cost); AI answers can be auto-added to the knowledge base.
- **Editable JSON request template**: the request body is fully template-driven with live preview and customizable model parameters.
- **Multiple themes**: black / white / gray presets plus image backgrounds with live preview.
- **Global hotkeys**: `Ctrl+F1` capture & recognize, `Ctrl+Q` quit (configurable).
- **Settings UI**: left-mid-right navigation with rounded cards; Model / General / About pages; auto-save on close.
- **Request history**: GitHub-style gray-to-green 5-level grid showing request activity over the last 20 weeks.

## Requirements

- Windows 10 / 11
- Python 3.10+ *(only needed for running from source; the packaged build needs no Python)*

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

# Run (or double-click start.bat; launches in background without a console window)
.\.venv\Scripts\python.exe main.py
```

## Quick Start

1. Launch the app; the red rectangle in the middle of the always-on-top window is the transparent capture hole.
2. **Position**: drag the top/bottom bars to align the hole with the target area.
3. **Resize**: drag the window edges/corners to adjust the hole size (auto-remembered).
4. Click **Capture & Recognize** (or press `Ctrl+F1`) — it automatically runs: capture → OCR → question parsing → local knowledge base / LLM answer.
5. Results are shown in sections: 【Recognition Result】and【Answer】are collapsible; type and timing appear on the button row.

> Before first use, open **Settings → Model Settings** and fill in the **API Key** and **Model ID** for the selected platform (stored locally in `config.json`, never uploaded).

## Configuration

Click **Settings** at the top to open the dialog (left navigation: Model / General / About):

- **Model Settings**: AI platform management in the middle (configured/unconfigured sections, hover to delete, add custom platforms); detailed settings on the right (editable platform name, connection test, note, homepage, API Key with eye toggle, Model ID, Base URL, enable thinking, JSON request preview).
- **General Settings**: storage (cache/question directories, auto-add answers to knowledge base), AI settings (**cloud/local OCR mode**, max response time, retry count), prompts (OCR / answer).
- **About**: app info, request history, website & community, open-source license.

`config.json` is grouped by purpose: `providers` / `prompts` / `request_template` / `window` / `theme` / `capture` / `timeout` / `retry` / `ocr` / `knowledge` / `hotkeys` / `behavior` / `app`.

## Hotkeys

| Hotkey | Function |
|---|---|
| `Ctrl+F1` | Capture & recognize |
| `Ctrl+Q` | Quit |

Can be changed in `config.json` → `hotkeys`.

## FAQ

- **Status shows "Key not configured"**: fill in the API Key for the current platform under Settings → Model Settings.
- **401/403 errors**: invalid API Key or no permission for the model.
- **Local OCR errors**: make sure dependencies are installed (`pip install rapidocr_onnxruntime`).
- **Capture area not matching the hole**: the app is Per-Monitor V2 DPI aware and supports multi-monitor setups with different scaling.
- **How to change prompts / request template**: Settings dialog (Prompts, JSON Request Preview → Edit Template) or edit `config.json` directly.

## Contact & Community

- GitHub: [https://github.com/TDCQCX/OCR-Assistant](https://github.com/TDCQCX/OCR-Assistant)
- QQ Group: **1108236960**

## License

Licensed under the [MIT License](LICENSE).

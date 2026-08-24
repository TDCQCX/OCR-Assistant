# OCR 助手

[简体中文](README.md) | [English](README.en.md)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![PySide6](https://img.shields.io/badge/GUI-PySide6-green?logo=qt&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Version](https://img.shields.io/badge/Version-1.0.0-orange)

> **OCR 助手** — 透明洞口截图 · 云端/本地 OCR 识别 · 大模型图文答题的桌面工具。

把透明悬浮窗的洞口对准屏幕上的任何内容(题目、文档、代码…),一键完成 **截图 → 文字识别 → 大模型理解回答**,结果分区块展示、可折叠,全程无需切换窗口。

## 功能特性

- **透明洞口悬浮窗**:仅洞口区域透明透看目标,其余为不透明面板;可拖动定位、拖边缘缩放,窗口尺寸自动记忆;识别结果/回答区可折叠,折叠时窗口高度跟随、洞口大小不变
- **双 OCR 模式**:
  - **云端**:调用所选大模型识别(精度更高,消耗 token)
  - **本地**:内置 RapidOCR(ONNX Runtime,PP-OCR 模型,约 50MB,离线免费,CPU 100-300ms)
- **多 AI 平台**:阿里云百炼 / OpenAI / DeepSeek / 智谱 GLM / Kimi / Ollama 等主流服务商一键切换,支持自定义平台(可编辑名称/logo、删除);未配置平台以暗色区分
- **图文答题**:OCR 文字 + 截图图片同时发给模型,结合题目结构化解析(题型/题目/选项),回答更准确;可关闭思考模式提升速度
- **本地知识库**:关键词命中即返回答案,免 API 调用(毫秒级、零费用);AI 回答可自动入库
- **可编辑 JSON 请求模板**:请求体完全由模板驱动,实时预览,支持自定义模型参数
- **多主题**:黑/白/灰三色预设 + 图片背景,实时预览
- **全局快捷键**:`Ctrl+F1` 截图识别、`Ctrl+Q` 退出(可自定义)
- **配置界面**:左中右导航 + 圆角卡片,模型/常规/关于应用分页;关闭窗口自动保存
- **请求记录**:GitHub 风格灰→绿 5 级方格图,展示最近 20 周请求情况

## 环境要求

- Windows 10 / 11
- Python 3.10+ *(仅源码运行需要;直接使用打包版无需 Python)*

## 安装与运行

### 方式一:直接使用打包版(推荐)

从 [Releases](../../releases) 下载对应版本的可执行文件,双击运行即可。

### 方式二:源码运行

```powershell
git clone https://github.com/TDCQCX/OCR-Assistant.git
cd OCR-Assistant

# 创建虚拟环境并安装依赖
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 启动(或双击 start.bat;以无控制台方式后台启动,cmd 自动关闭)
.\.venv\Scripts\python.exe main.py
```

## 快速开始

1. 打开程序,置顶悬浮窗中部红色矩形为透明洞口。
2. **定位**:按住上/下栏空白处拖动窗口,使洞口对准目标区域。
3. **缩放**:拖拽窗口边缘/角落调整洞口大小(自动记忆)。
4. 点「截图并识别」(或按 `Ctrl+F1`),自动完成:截图 → OCR 识别 → 题目解析 → 本地知识库/大模型回答。
5. 回复区分区块展示:【识别结果】可折叠、【回答】可折叠,类型与耗时显示在按钮行。

> 首次使用请先在「配置 → 模型设置」中为所选平台填写 **API Key 与模型ID**(保存于本地 `config.json`,不会上传)。

## 配置说明

点击顶部「配置」打开设置对话框(左侧导航:模型设置 / 常规设置 / 关于应用):

- **模型设置**:中部 AI平台管理(已配置/未配置分区,悬浮可删除,可添加自定义平台);右侧具体设置(平台名称可编辑、测试连通性、备注、官网、API Key(眼睛显隐)、模型ID、Base URL、是否开启思考、JSON 请求预览)
- **常规设置**:保存设置(缓存/题目保存位置、AI 回答自动入库)、AI设置(**是否启用云端OCR** 云端/本地、模型最长响应时间、失败自动尝试次数)、提示词设置
- **关于应用**:应用信息、请求记录、网站与社区、开源许可证

`config.json` 配置按用途分组:`providers`(多平台)/ `prompts` / `request_template` / `window` / `theme` / `capture` / `timeout` / `retry` / `ocr` / `knowledge` / `hotkeys` / `behavior` / `app`。

## 快捷键

| 快捷键 | 功能 |
|---|---|
| `Ctrl+F1` | 截图并识别 |
| `Ctrl+Q` | 退出程序 |

可在 `config.json` 的 `hotkeys` 中修改。

## 常见问题

- **状态栏显示"Key 未配置"**:在「配置 → 模型设置」为当前平台填写 API Key。
- **接口返回 401/403**:API Key 无效或无该模型权限。
- **本地 OCR 报错**:确认已安装依赖 `pip install rapidocr_onnxruntime`。
- **截图区域与洞口不一致**:程序已做 Per-Monitor V2 DPI 感知,支持多显示器与不同缩放。
- **提示词/请求模板如何改**:设置对话框「提示词」「JSON 请求预览 → 编辑模板」或直接编辑 `config.json`。

## 联系与社区

- GitHub: [https://github.com/TDCQCX/OCR-Assistant](https://github.com/TDCQCX/OCR-Assistant)
- QQ 群: **1108236960**

## 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。

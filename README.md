# OCR 助手

[简体中文](README.md) | [English](README.en.md)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![React](https://img.shields.io/badge/UI-React%2018-61DAFB?logo=react&logoColor=white)
![Tailwind](https://img.shields.io/badge/Style-Tailwind%20CSS-38BDF8?logo=tailwindcss&logoColor=white)
![pywebview](https://img.shields.io/badge/Shell-pywebview%20%2B%20Qt-41CD52?logo=qt&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey)
![Version](https://img.shields.io/badge/Version-2.5.0-orange)

> **OCR 助手** — 三种截图模式 · 云端/本地双 OCR · 大模型图文答题的桌面工具。
> 界面由 **React 18 + Tailwind CSS** 构建,后端为 Python(截图 / OCR / 模型调用 / 配置)。

把捕获区对准屏幕上的任何内容(题目、文档、网页、代码…),一键完成 **截图 → 文字识别 → 大模型理解回答**,结果分区块折叠展示,全程无需切换窗口。

## 四种模式

| 模式 | 说明 | 快捷键 |
|---|---|---|
| **悬浮窗模式** | 透明洞口常驻置顶,洞内即捕获区;**洞内鼠标可直接穿透**,点击直达后方内容 | `Ctrl+1` |
| **自由截图模式** | 全屏半透明遮罩,拖拽框选任意区域;操作条内嵌引擎开关/语言方向/提问,可「识别 / 翻译此区域 / 设为悬浮窗区域」 | `Ctrl+Shift+A` / `Ctrl+3` |
| **迷你条模式** | 图标工具条 + 提问输入行(悬停显示说明),首次自动居中停靠在任务栏上方,可自由拖动 | `Ctrl+2` |
| **翻译模式** | 无洞口窗口,识别区与译文区放大;按句/段双语对照,支持端侧离线翻译 | 顶部切换器 |

> 顶部切换器或快捷键可随时切换模式;`Ctrl+F1` 在悬浮窗模式触发识别,在迷你条模式直接进入框选。

## 功能特性

- **透明洞口悬浮窗**:仅洞口透看目标,其余为不透明面板;拖动定位、洞口宽高可调,窗口尺寸自动记忆
- **洞口鼠标穿透**:洞内点击直达后方内容(可一边看题一边作答),洞口边框仍保持可见
- **窗口拖边缩放**:四边/四角都可拖动改变大小,尺寸与位置自动记忆;洞口尺寸可精确设定
- **双 OCR 模式**:云端(所选大模型识别,精度高)/ 本地(内置 RapidOCR,离线免费,约 50MB,CPU 100-300ms);主界面一键切换
- **双翻译模式**:云端大模型翻译 / 端侧离线翻译(Argos 端侧模型,可选本机 Ollama),语言方向可选并注入请求
- **双语对照**:识别原文按句/段切分,原文一段、译文紧随其下;可切换双语 / 仅译文 / 仅原文
- **多 AI 平台**:阿里云百炼 / OpenAI / DeepSeek / 智谱 GLM / Kimi / Ollama,支持自定义平台;已配置与未配置分区显示、悬浮删除、名称可编辑
- **图文答题**:OCR 文字 + 截图图片同时发送模型,并结合题目结构化解析(题型 / 题目 / 选项);可关闭思考模式提速
- **本地知识库**:关键词命中即返回答案,免 API 调用;AI 回答可自动入库
- **全局主题 + 自定义主题**:浅色 / 深色 / 灰色 / 护眼 / 高对比 5 套预设,支持逐项配色(含面板/卡片/内嵌区三层分区色)、圆角、字号、面板不透明度、洞口边框样式;主题可导出/导入 JSON,所有窗口实时同步
- **扁平图标界面**:全部图标为内置 SVG(无 emoji),悬停显示文字说明,紧凑不占空间
- **识别历史**:最近 100 条结果可回看、复制、清空
- **请求记录**:GitHub 风格灰→绿方格图(最近 20 周)
- **可编辑 JSON 请求模板**:实时预览 + 格式校验,支持自定义模型参数
- **提问示例**:内置「请回答/请翻译/请解释/请总结/请搜索关联内容」等示例,自输入内容自动保存
- **更多设置**:图片压缩上限、默认提问、快捷键自定义、缓存与题目保存位置、回答自动入库、连通性测试(含响应耗时)

## 技术架构

```
┌────────────── 前端 React 18 + Tailwind(Vite 构建) ──────────────┐
│  index.html?view=overlay | mini | settings      selector.html    │
│  组件:Overlay / MiniBar / Settings / Snip / ui / theme           │
└─────────────────────────────┬───────────────────────────────────┘
                     pywebview js_api(JSON 桥)
┌─────────────────────────────┴───────────────────────────────────┐
│  后端 Python:manager(窗口/模式/流程) · api(桥) · capturer(mss) │
│  agent(模型调用) · worker(识别流程) · question_parser · local_ocr│
│  config / history / request_log                                  │
└─────────────────────────────────────────────────────────────────┘
```

- 桌面容器:**pywebview**(Qt / WebEngine 后端),支持透明、无边框、置顶、拖拽与全局热键
- 窗口与 WebView 操作统一通过 `app/mainthread.py` 排队到 Qt 主线程执行

## 环境要求

- Windows 10 / 11
- Python 3.10+ *(仅源码运行需要;打包版无需 Python)*
- Node.js 18+ *(仅二次开发前端时需要)*

## 安装与运行

### 方式一:打包版(推荐)

从 [Releases](../../releases) 下载对应版本的可执行文件,双击运行。

### 方式二:源码运行

```powershell
git clone https://github.com/TDCQCX/OCR-Assistant.git
cd OCR-Assistant

# 创建虚拟环境并安装依赖
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 启动(或双击 start.bat)
.\.venv\Scripts\python.exe main.py
```

### 前端开发(可选)

```powershell
cd frontend
npm install
npm run build     # 构建到 app/webui,后端自动加载
npm run dev       # 浏览器热更新调试
```

## 快速开始

1. 启动后进入**悬浮窗模式**,中部红色边框区域即捕获洞口。
2. **定位**:按住顶部/底部面板拖动窗口,使洞口对准目标;也可在底部输入洞口宽高精确设定。
3. 在「提问/指令」框填写问题(默认:请给出该题目的答案)。
4. 点击「截图并识别」或按 `Ctrl+F1`,数秒内即可看到【识别结果】与【回答】。
5. 需要临时框选时按 `Ctrl+Shift+A` 进入自由截图模式,拖拽框选后选择「识别」或「设为悬浮窗区域」。

> 首次使用请先在「设置 → 模型设置」中为所选平台填写 **API Key 与模型 ID**(仅保存在本地 `config.json`)。

## 配置说明

点击顶部「设置」打开设置窗口(左侧导航):

- **模型设置**:AI平台管理(已配置/未配置分区、悬浮删除、自定义平台)+ 具体设置(名称、连通性测试、备注、官网、API Key、模型ID、Base URL、思考模式、JSON 请求预览与模板编辑)
- **常规设置**:AI设置(云端/本地 OCR、最长响应时间、重试次数、图片压缩上限)、保存设置(缓存/题目目录、自动入库)、行为与快捷键、提示词设置
- **外观主题**:5 套预设 + 自定义配色编辑器 + 圆角/字号/面板不透明度/洞口边框 + 主题导入导出
- **识别历史**:结果回看与清理
- **关于应用**:版本信息、请求记录图、GitHub 与 QQ 群、开源许可证

配置按用途分组:`active_provider` / `providers` / `prompts` / `request_template` / `mode` / `ui` / `window` / `capture` / `timeout` / `retry` / `ocr` / `knowledge` / `hotkeys` / `behavior` / `storage` / `app`。

## 快捷键

| 快捷键 | 功能 |
|---|---|
| `Ctrl+F1` | 识别(悬浮窗)/ 进入框选(迷你条) |
| `Ctrl+Shift+A` | 自由截图模式 |
| `Ctrl+1` / `Ctrl+2` / `Ctrl+3` | 切换悬浮窗 / 迷你条 / 自由截图 |
| `Ctrl+Q` | 退出程序 |

可在「设置 → 常规设置 → 行为与快捷键」中修改。

## 常见问题

- **提示"未配置 API Key"**:在「设置 → 模型设置」为当前平台填写 Key 并保存(关闭设置窗口即自动保存)。
- **接口返回 401/403**:API Key 无效或无该模型权限;可用「测试连通性」快速排查。
- **本地 OCR 报错**:确认为源码环境安装了 `rapidocr_onnxruntime`。
- **截图区域与洞口不一致**:程序已做 Per-Monitor V2 DPI 感知,支持多显示器与不同缩放;如显示异常可调整洞口尺寸后重试。
- **提示词 / 请求模板如何改**:设置 → 常规设置(提示词)、模型设置(JSON 预览 → 编辑模板)。

## 联系与社区

- GitHub: [https://github.com/TDCQCX/OCR-Assistant](https://github.com/TDCQCX/OCR-Assistant)
- QQ 群: **1108236960**

## 许可证

本项目采用 **[CC BY-NC 4.0](LICENSE)(署名—非商业性使用 4.0 国际)** 许可:

- **禁止商业使用**:不得用于出售、付费分发、商业产品集成或任何以营利为目的的场景;商业授权请联系作者;
- **转载必须标明出处**:任何转载、镜像、二次分发或衍生作品,须标注原作者与项目名,并给出原始仓库地址
  [https://github.com/TDCQCX/OCR-Assistant](https://github.com/TDCQCX/OCR-Assistant),且保留许可协议全文;
- 个人学习、研究、教学等非商业用途可自由使用、修改与分发。

> 说明:该协议不属于 OSI 认可的开源许可(OSI 要求不得限制使用领域)。另外,端侧翻译的
> 均衡/全量档使用的 NLLB-200 模型本身即为 CC BY-NC 4.0(禁止商用),与本项目协议一致;
> 其他第三方组件(PySide6/Qt、RapidOCR 等)仍按其各自许可执行,详见 [LICENSE](LICENSE)。

## 端侧(离线)翻译

翻译模式的「端侧翻译」不联网、免费,需要在本机安装端侧模型(仅源码运行需要,打包版会在检测到后自动启用):

`powershell
.\\.venv\\Scripts\\python.exe -m pip install argostranslate
`

安装后在「设置 → 翻译设置 → 端侧模型状态」中点击「下载当前语言包」即可(每对语言约 100MB,只需一次)。
也可以改用本机 [Ollama](https://ollama.com)(设置 → 翻译设置 → 端侧引擎选 Ollama)。

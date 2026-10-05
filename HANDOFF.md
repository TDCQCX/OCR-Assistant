# 交接文档(给下一个智能体)

> 目的:让接手的人在**不重新踩坑**的前提下继续这个项目。
> 读完本文 + `CHANGELOG.md` 最近 3 个版本,应当能直接上手改代码。
> 最后更新:2026-10-01(对应 v2.6.10)

---

## 0. 三十秒速览

**OCR 助手** —— Windows 桌面工具。屏幕上圈一块区域 → OCR 识别 → 交给大模型问答/翻译。

- **形态**:无边框多窗口桌面应用(pywebview + Qt WebEngine 承载 React 前端)
- **后端**:Python(窗口编排、截图、模型调用、端侧推理)
- **前端**:React 18 + Tailwind CSS(Vite 构建,产物进 `app/webui/`)
- **四种模式**:悬浮窗 / 翻译 / 自由框选 / 迷你条
- **双引擎**:OCR 与翻译都支持 **云端(大模型)** 与 **端侧(离线模型)**
- **当前版本**:`2.6.10`(单一来源见 `app/config.py` 的 `APP_VERSION`)
- **许可证**:CC BY-NC 4.0(禁止商用;端侧 NLLB 模型同为该协议)

---

## 1. 先做这几件事(接手 checklist)

```powershell
# 1) 用项目自带的 venv,不要用系统 python
.\.venv\Scripts\python.exe -c "import webview, PySide6; print('ok')"

# 2) 【一条命令】测试基准 + 改动审计(改完必跑)
.\.venv\Scripts\python.exe tools\check.py
#    需要真窗口验证时:tools\check.py --gui

# 3) 前端构建(改完前端必跑)
cd frontend; npm run build

# 4) 启动
.\.venv\Scripts\python.exe main.py      # 或双击 start.bat
```

**重要**:本环境 `apply_patch` 工具**不可用**(调用会失败),所有文件改动请用 shell
(`Set-Content` / 写临时 `.py` 脚本执行)。同样的规则写在用户级 `AGENTS.md`
(`C:\Users\<你的用户名>\.codex\AGENTS.md`,不在本仓库内)。

> `tests/` 与 `tools/` 是 2026-10-01 新加的验证基建。动手前先读仓库根的 **`AGENTS.md`**
> (硬性约定:每次改动都要 `tools/check.py`,不允许为了过审而放宽规则)。

---

## 2. 目录与职责

```
tests/                   测试基准(144 项,pytest;不碰真实配置,见 conftest.sandbox)
tools/
  check.py               一条命令:先测试基准,再审计改动(可 --gui 追加真窗口冒烟)
  audit_changes.py       改动审计:对照历史踩坑清单,BLOCK/WARN/INFO 三级
  gui_smoke.py           真窗口冒烟:模式互切/洞口/迷你条还原/退出链路/按需窗口
main.py                 入口:设置 QTWEBENGINE_CHROMIUM_FLAGS 后启动 App
app/
  manager.py     (1556) 窗口编排 / 模式切换 / 流程调度 / 托盘 / 全局热键 ←核心
  api.py          (753) pywebview JS 桥(80 个公开方法),前端唯一入口
  config.py       (380) 默认配置、服务商预设、提示词模板、APP_VERSION
  winutil.py      (188) DPI 换算 + 洞口区域(SetWindowRgn)计算 ←平台层
  local_models.py (773) 端侧模型:档位、下载、体积统计(带缓存)
  local_translate.py(352) 端侧翻译:分段、Argos/Ollama/小模型调度
  local_mt.py     (173) CTranslate2 推理(轻量档)
  local_hf.py     (171) 官方 NLLB 推理(均衡/全量档,transformers)
  local_ocr.py    (106) RapidOCR 端侧识别
  agent.py        (245) 云端模型客户端(请求模板、重试、错误提示)
  worker.py       (186) 识别/翻译流水线线程
  question_parser.py(165) 把 OCR 文本解析成 题型/题目/选项
  capturer.py      (48) mss 截屏
  clipboard.py     (47) 系统剪贴板
  history.py       (38) 最近 100 条结果
  request_log.py   (68) 请求日志(绿块图数据)
  mainthread.py    (56) 把子线程调用排队回 Qt 主线程
frontend/src/
  main.jsx        (163) 应用根 / 全局状态 / 事件分发
  Overlay.jsx     (348) 悬浮窗模式
  Translate.jsx   (240) 翻译模式
  MiniBar.jsx     (175) 迷你条模式
  Snip.jsx        (165) 自由框选(独立入口 selector.html)
  Settings.jsx   (1441) 设置页(7 个分页,最大文件)
  Guide.jsx       (302) 新手教程(气泡+箭头)
  QuitDialog.jsx  (127) 退出确认
  ui.jsx          (819) 通用控件(Icon/Btn/QBox/EngineSwitch/下载弹窗…)
  theme.js        (131) 主题与背景图 CSS 变量
  bridge.js        (60) pywebview 桥 + 事件总入口
  index.css      (1002) 设计令牌 + 全部组件样式
```

**数据文件**(均不入版本库):`config.json`(+`.bak`)、`history.json`、
`request_log.json`、`models/`、`cache/`、`questions/`。

---

## 3. 架构:数据是怎么流动的

```
React 组件
   │  call('方法名', ...)            ← bridge.js,自动等 pywebview 就绪
   ▼
Api(app/api.py)  ──80 个方法──►  App(app/manager.py)
   ▲                                    │
   │  window.__ocrEvent({type, ...})    │  push() → 独立线程 → evaluate_js
   └──────── 事件(17 种) ◄──────────────┘
```

**两条铁律**(违反必出难查的 bug):

1. **所有窗口/WebView 操作必须经 `run_in_main()`** 排到 Qt 主线程。
   在子线程直接调 `win.move()` 会随机失败或死锁。
2. **推送事件必须在非 GUI 线程做**(`manager.push()` 用的是专门的 push 线程)。
   在 Qt 主线程里 `evaluate_js` 会阻塞等待 JS 返回 → 界面卡死。

### 事件类型(后端 → 前端)

`status`(AI 运行状态,显示在状态灯旁)、`notice`(界面操作反馈,2.2s 轻提示)、
`result`、`error`、`busy`、`config`、`history`、`download`、`pack`、`conn`、
`models`、`modalBlock`、`hideBorder`、`hotkeyCapture`、`guideStart`、`quitHint`、
`confirmQuit`。

> **`status` 与 `notice` 必须分清**:把"已切换到悬浮窗模式"这类界面文案写进 `status`,
> 会一直挂在状态灯旁边不消失(这是真实踩过的坑)。

### 视图入口

`index.html?view=overlay|mini|translate|settings`,以及独立入口 `selector.html`(框选)。
`main.jsx` 的 `Root()` 按 `location.pathname` / `view` 分发。

---

## 4. 必须知道的平台层知识(踩坑重灾区)

### 4.1 逻辑像素 vs 物理像素

- pywebview/Qt 的 `win.x / win.y / win.width` 是**逻辑像素(DIP)**
- `mss` 抓屏与 `SetWindowRgn` 用**物理像素**
- 125% 缩放下两者差 1.25 倍。直接把逻辑坐标喂给截图 → 捕获区域整体偏移
  (实测窗口在 (508,254) 时偏 **127×64 px**)

**规矩**:凡涉及坐标/尺寸换算,一律走 `app/winutil.py`:
`screen_scale()` / `physical_origin(win)` / `client_origin(win)` / `apply_hole_region()`。
不要自己乘 `devicePixelRatio`。

### 4.2 洞口穿透

悬浮窗中部是"洞口"——用 `SetWindowRgn` 把它从窗口区域里**挖掉**,鼠标才能点到后面的内容。
因此:

- 洞口区域**不能铺任何底色**(窗口根是透明的)
- **弹窗/教程期间必须临时取消挖洞**(`pause_hole(True)`),否则居中的弹窗会被裁掉、点不到
- 前端上报洞口用 `set_hole_region(rect)`,内部会复用计算并缓存

### 4.3 pywebview 的已知坑

| 现象 | 原因 / 处理 |
|---|---|
| 多窗口页面加载不出来、整窗空白 | `private_mode` 必须为 **True**;否则 Qt 为每个窗口建同名持久化 Profile 争抢缓存 |
| `win.on_top = x` 后另一个窗口冒出来 | pywebview 内部会无条件 `show()`;设完要再调 `_sync_visibility()` |
| 迷你条高度"还原不了" | pywebview 默认 `min_size=(200,100)` 顶高;已显式设 `min_size=(640,56)` |
| `win.hidden` / `win.visible` 值不准 | `hidden` 是**创建参数**,不随 `show/hide` 更新;要判断可见性用 **`win.native.isVisible()`** |
| 页面还没就绪就 `evaluate_js` | 会阻塞 ~20s 后抛错,堵住事件队列;推送前先查 `win.events._pywebviewready.is_set()` |

### 4.4 前端圆角与背景图

- 每个模式的根是 `.window-shell`(圆角外壳);**只有设置窗口**才铺不透明底色
  (`.app-surface`),其它窗口用 `surface-transparent`,否则圆角外会露出方形棱角
- **悬浮窗例外**(`.view-overlay`):只有窗口四角圆角,内部面板/卡片/结果框一律不圆角
  —— 这是用户明确要求的设计
- 背景图:有图时给 `body` 加 `.has-bg`,外壳让位、面板/卡片半透明透出图片;
  CSS 变量由 `theme.js` 的 `applyBackgroundImage()` 写入

---

## 5. 关键约定(改代码前请先读)

1. **版本号单一来源**是 `app/config.py` 的 `APP_VERSION`。发版时同步:
   `version_info.txt`、`frontend/package.json`、`README*.md` 徽章、`TUTORIAL.md` 里的
   exe 名、`OCR助手-vX.Y.Z.spec` 文件名与内容(把 X.Y.Z 换成实际版本)。
2. **配置写入前自动备份**为 `config.json.bak`(见 `config.save_config`)。
3. **不要依赖 `cfg.mode` 判断"当前是哪个窗口"**:配置广播到各窗口有延迟,窗口刚显示时
   `cfg.mode` 可能是旧值。事件里要显式带上目标(例如 `confirmQuit` 带 `mode` 字段)。
   > 这是真实缺陷:退出按钮在翻译模式点不动,就是被这个延迟坑的。
4. **启动速度/内存相关**:`main.py` 里设了 Chromium flags(禁 GPU、限渲染进程、限堆);
   设置窗口与框选窗口是**按需创建、用完销毁**(各占 ~65MB 渲染进程)。
5. **端侧模型目录扫描有代价**:`models/` 下实测 3492 个文件,递归 stat 一次 300ms+。
   `local_models._dir_size()` 做了 TTL 缓存 + 快速估算 + 后台补精确值,**不要**改成同步全量遍历。
6. **迷你条尺寸**(`app/manager.py` 顶部两个常量):
   - `MINI_MIN_WIDTH = 640` —— 宽度下限,保证右上角那组按钮不会被挤出窗口;
   - `MINI_MODAL_EXTRA = 58` —— 退出提示浮层在迷你条**上方**预留的高度(窗口向上扩展,
     本体位置不变);迷你条本体高度由前端实测内容后 `set_mini_height()` 锁定;
   - 弹窗一律"向上借空间",**不要**把迷你条本体加高(加高后很难还原,历史踩过)。
7. 前端入口 `bridge.js` 里的 `window.__ocrEvent` 是**事件总入口**——独立入口
   (`selector.html`)也会加载它,新增事件请在 `window.__ocrEvent` 或组件内的
   `window.addEventListener('ocr-event', ...)` 上处理,别另起一套。

---

## 6. 已修复但**容易复发**的缺陷(改相关代码时重点回归)

| 症状 | 根因 | 现在的做法 |
|---|---|---|
| 识别到的内容与洞口不一致 | 逻辑/物理像素混用 | 统一走 `winutil.physical_origin()` |
| 点「翻译此区域/设为悬浮窗区域」没反应 | 前端把 action 塞进 sel,参数错位 | 后端有 `normalize_snip_args()` 归一化 |
| 翻译模式点退出没反应 | 靠有延迟的 `cfg.mode` 判身份 | 事件显式带 `mode`,前端只认它 |
| 迷你条点退出把窗口撑开且回不来 | 关闭时因"模式已变"提前 return;隐藏窗口来不及清理 | 还原**无条件执行** + 离开迷你条时后端兜底还原 |
| 切到「识别历史」页卡 4 秒 | 端侧状态每次都全量遍历 models/ | `_dir_size` 缓存 + 快速估算 |
| 设置页切换卡顿 | 背景图伪元素未提升合成层、`blur(0)` 仍建滤镜层 | 已提升 + `blur=0` 用 `none` |
| 悬浮窗顶栏控件互相压住 | 单行放不下 4 组控件 | 顶栏密度三档(`full/compact/stacked`)自动降级 |
| 迷你条状态点旁显示的是识别结果 | 语义混用 | 状态点旁只放 AI 状态,结果放第三行带「结果」标签 |

---

## 7. 当前状态与下一步

**已完成**:功能齐备(四模式、双引擎、多平台、端侧三档、主题+背景图、教程、托盘、
历史时间线、请求统计);v2.6.10 修掉退出按钮缺陷并通过全逻辑审计。

**验证基建(2026-10-01 建立)**:

- `tests/` —— 140 项基准用例,约 4s 跑完;`sandbox` fixture 把配置/历史/请求日志全部
  重定向到临时目录,不会污染真实数据
- `tools/audit_changes.py` —— 按历史踩坑清单审计改动(build.sync / version.sync /
  bridge.methods / bridge.events / ui.dpi / hole.pause_pair / event.semantics /
  py.silent_except / css.classes / repo.hygiene)
- `tools/gui_smoke.py` —— 真窗口冒烟,覆盖模式互切/洞口/迷你条还原/退出链路/按需窗口
- `tools/check.py` —— 一条命令:先跑测试,再审计改动;`--gui` 追加真窗口
- 仓库根 `AGENTS.md` —— 上面这套的硬性约定(每次改动都要跑)

**本轮审计发现的既有缺陷(已登记为已知问题,写进用例注释,尚未修)**:

| 位置 | 问题 | 影响 | 修复方向 |
|---|---|---|---|
| `app/question_parser.py` `_detect_type` | 无选项时用单个字 `对\|错` 兜底判断题 | "解释一下相对论"会被判成判断题,影响题型展示与知识库匹配键 | 去掉单字兜底,只留 `正确\|错误\|是否` 等多字提示(带选项的判断题已由选项内容覆盖) |
| `app/worker.py` `_run_translate` | 空提问被兜底成 `DEFAULT_QUESTION` 后追加"附加要求:请回答识别到的内容" | 与翻译指令语义相反,可能让云端模型去"回答"而不是"翻译" | 兜底只在 `task == "answer"` 时生效 |
| `app/local_translate.py` `segment_text` | docstring 说超长段会按 `max_len` 拆开,实际不拆 | 单行超长文本整段进模型,`local_hf` 侧 `max_length=400` 会静默截断丢内容 | 真的要切分时,同步改 `test_segment_long_line_is_not_split` |
| `frontend/src/MiniBar.jsx` / `main.jsx` | `anim-pop` 在 JSX 里但 CSS 未定义(本轮已补回) | 弹入动画静默缺失 | 已修;审计新增 `css.classes` 规则防复发 |

> 上面每一条都有对应用例固定"现状",修好后请把断言翻过来 —— 别让测试通过掩盖缺陷。

**未做 / 待办**:

- **没有重新打包 exe**(`OCR助手-v2.6.10.spec` 已就绪,可直接 `pyinstaller` 打包)
- `git` 工作区有大量未提交改动(源码 + `app/webui/` 构建产物),**尚未 commit**
- 可继续深化的方向:
  - `api.py` 只校验了"方法名存在",没有做**参数级**校验
  - `manager.py` 中仍有多处 `except Exception: pass`(本轮已给四处补注释并登记白名单,
    其余位置在刻意为之的白名单文件里)
  - 设置页 `Settings.jsx` 已 1441 行,建议按分页拆文件

**验证环境**(供复现参考):Windows,125% 缩放屏,1920×1200 物理 / 1536×960 逻辑。

---

## 8. 改完必须做的验证(最少成本清单)

> **一条命令**:`./.venv/Scripts/python.exe tools/check.py`(测试基准 → 改动审计,详见 `AGENTS.md`)
> 需要真窗口验证时加 `--gui`。

```powershell
# 手动方式(等价,任选其一)
.\.venv\Scripts\python.exe -m pytest tests -q                  # 140 项基准用例,约 4s
.\.venv\Scripts\python.exe tools\audit_changes.py              # 对照历史踩坑清单审计改动
.\.venv\Scripts\python.exe tools\gui_smoke.py                  # 真窗口冒烟(约 20s,会短暂弹窗)
.\.venv\Scripts\python.exe -c "import py_compile,pathlib; [py_compile.compile(str(p),doraise=True) for p in list(pathlib.Path('app').glob('*.py'))+[pathlib.Path('main.py')]]; print('OK')"
# 前端构建(改了 frontend/ 必做)
cd frontend; npm run build
```

**审计的关键词**:`BLOCK` 必须修(`build.sync` 会在"改了前端没重建"时直接拦住);
`WARN` 逐条确认,确属有意为之的要在代码里写注释并加入 `tools/audit_changes.py` 的白名单
(`tests/test_audit_tool.py` 会检查白名单是否腐坏)。

### 自动化已经覆盖的(不必再手工点)

`tools/gui_smoke.py` 覆盖:三窗口加载、桥接面精简且可用、模式互切只有当前窗口可见、
洞口挖洞生效与暂停恢复、迷你条浮层向上扩展且精确还原、离开迷你条兜底还原、
退出链路(`confirmQuit` 带 mode / `quitHint`)、设置窗口按需创建+关闭销毁+模态拦截、
框选窗口按缩放比换算。

### 仍需人工确认的(自动化覆盖不到的)

1. 悬浮窗:洞口对准内容 → 识别 → 结果与洞口内容**一致**(需要真实屏幕内容)
2. 拖动顶栏**空白处** → 窗口跟着动(不是只有图标处能拖)
3. 点退出 → 弹确认;三个选项(托盘/关闭/再想想)都生效
4. 设置页:7 个分页切换不卡;主题/背景图即时生效
5. 端侧翻译:对话框里选好档位能**切到本地**并真的翻出结果(需要已下载模型)
6. 动画观感(入场/弹窗/拖动流畅度)——这类只能靠眼看

---

## 9. 给下一个智能体的三条提醒

1. **不要相信我的总结,去读代码**。本文是地图,`app/manager.py` 与
   `frontend/src/Settings.jsx` 才是现场。
2. **改动前后都跑 `tools/check.py`**(测试基准 + 改动审计);涉及窗口/模式/洞口时加 `--gui`。
   这个项目的历史几乎全是"改 A 坏 B",过去几轮里有 4 次是我自己引入的回归
   (圆角、洞口、迷你条高度、退出判定)。审计里的 `BLOCK` 一律必须修。
3. **UI 需求按字面执行但先量化**。用户说的"卡顿"有时根因在 4 秒的目录扫描,
   不在动画;先去量,再动手。

> 第 4 条(新增):**别为了过审放宽规则**。如果审计报的问题确实是有意为之,
> 就在代码里写清楚理由,并把位置加进 `tools/audit_changes.py` 的白名单 ——
> 每条白名单都要有 `tests/test_audit_tool.py` 的兜底检查,防止它随时间腐坏。

# -*- coding: utf-8 -*-
"""配置读写:config.json 位于程序根目录(含 API Key,勿提交到版本库)。

配置按用途分组:
providers(多AI平台) / request_template / window / theme / capture / retry /
timeout / knowledge / hotkeys / behavior / storage / app。
"""
import json
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller 冻结模式:以 exe 所在目录为基准,保证配置/缓存可持久化
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"

DEFAULT_OCR_PROMPT = (
    "你是一个高精度OCR文字识别引擎。请仔细观察这张截图,识别图中所有可见的文字内容,"
    "包括中文、英文、数字、标点符号、题目、选项、标题、正文等。\n"
    "要求:\n"
    "1. 按从上到下、从左到右的阅读顺序输出,尽量保持原有的换行与段落结构,每一行文字单独输出一行;\n"
    "2. 题目序号(如 1.、2.、3. 或 第1题)与选项序号(如 A.、B.、C.、D.)必须完整准确地识别并输出,不得遗漏或错乱;\n"
    "3. 逐字准确识别,不要遗漏任何可见文字,不要擅自合并、拆分或改写;\n"
    "4. 图中若有表格、图表或图形,请用文字转述其中的关键数字、标签和数据;\n"
    "5. 只输出识别到的文字本身,严禁输出任何解释、说明或格式标记;\n"
    "6. 若图中没有任何文字,只输出:(未识别到文字)"
)

DEFAULT_ANSWER_PROMPT = (
    "你是通用识别与问答助手。以下是用户截取的画面内容:"
    "①OCR识别出的文字(可能不完整或有误,请以截图为准);②原始截图图片。\n"
    "用户的指令:{question}\n\n"
    "请严格按用户指令处理,并遵守以下规则:\n"
    "1. 指令要求「回答/解答」:直接给出答案;选择题给出选项字母与对应内容,其他题型给出对应答案;\n"
    "2. 指令要求「翻译」:只输出译文,逐行对应原文,不要解释、不要重复原文;\n"
    "3. 指令要求「解释」:给出清晰、分点的解释,必要时补充背景;\n"
    "4. 指令要求「总结/要点」:输出简洁的要点列表;\n"
    "5. 指令要求「搜索/关联/相关」:结合你的知识给出相关联的信息,无法确认的内容要说明不确定;\n"
    "6. 其他指令按用户意图灵活处理。\n"
    "7. 只输出与指令相关的结果,不要复述本提示词,不要输出多余前言与后缀。\n\n"
    "题型:{qtype}\n"
    "题目:{qtitle}\n"
    "选项:\n{options}\n\n"
    "OCR识别结果:\n{ocr_text}"
)

# 翻译模式提示词:语言对与段落数由 config.translate 与识别结果注入。
DEFAULT_TRANSLATE_PROMPT = (
    "你是专业翻译引擎。请把下面的内容从「{source_lang}」翻译为「{target_lang}」。\n"
    "输入共 {count} 段,段落之间用单独一行 --- 分隔(每段可能是一句话或一整段文字)。\n"
    "请严格按段翻译,并只输出一个 JSON 数组,包含 {count} 个字符串,顺序与输入段落一一对应,"
    "不要输出任何解释、编号或额外文字。\n"
    "示例:输入 2 段 → 输出 [\"第一段译文\",\"第二段译文\"]\n"
    "要求:\n"
    "1. 按整句/整段的语义翻译,不要逐词直译,不要拆散句子;\n"
    "2. 术语、专有名词、数字、标点保持一致;人名地名按目标语言习惯翻译;\n"
    "3. 若某段无需翻译(纯数字、代码、公式),译文与原文保持一致;\n"
    "4. 译文中不要包含原文,也不要输出 --- 分隔符。\n\n"
    "待翻译内容(来源语言:{source_lang};目标语言:{target_lang}):\n{ocr_text}"
)

# 发送给模型的 JSON 请求体模板。
# 占位符 {model} / {prompt} / {image_url} 会被替换为「JSON 转义后的完整值」(自动带引号),
# 因此模板中不要给占位符加引号。enable_thinking 由所选平台的「是否开启思考」自动注入。
DEFAULT_REQUEST_TEMPLATE = (
    '{\n'
    '  "model": {model},\n'
    '  "messages": [\n'
    '    {\n'
    '      "role": "user",\n'
    '      "content": [\n'
    '        {"type": "text", "text": {prompt}},\n'
    '        {"type": "image_url", "image_url": {"url": {image_url}}}\n'
    '      ]\n'
    '    }\n'
    '  ],\n'
    '  "temperature": 0,\n'
    '  "enable_thinking": false\n'
    '}'
)

# 主流 AI 服务商预设。
# 未配置模型的 备注/APIKey/模型ID 均为空,仅保留 官网链接 与 baseURL,由用户自行填写。
PROVIDER_PRESETS = [
    {
        "id": "bailian", "name": "阿里云百炼", "color": "#FF6A00", "logo": "",
        "note": "",
        "homepage": "https://bailian.console.aliyun.com/",
        "api_key": "", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "model": "", "enable_thinking": False,
    },
    {
        "id": "openai", "name": "OpenAI", "color": "#10A37F", "logo": "",
        "note": "", "homepage": "https://platform.openai.com/",
        "api_key": "", "base_url": "https://api.openai.com/v1",
        "model": "", "enable_thinking": False,
    },
    {
        "id": "deepseek", "name": "DeepSeek", "color": "#4D6BFE", "logo": "",
        "note": "", "homepage": "https://platform.deepseek.com/",
        "api_key": "", "base_url": "https://api.deepseek.com/v1",
        "model": "", "enable_thinking": False,
    },
    {
        "id": "zhipu", "name": "智谱 GLM", "color": "#3859FF", "logo": "",
        "note": "", "homepage": "https://open.bigmodel.cn/",
        "api_key": "", "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "", "enable_thinking": False,
    },
    {
        "id": "moonshot", "name": "月之暗面 Kimi", "color": "#232323", "logo": "",
        "note": "", "homepage": "https://platform.moonshot.cn/",
        "api_key": "", "base_url": "https://api.moonshot.cn/v1",
        "model": "", "enable_thinking": False,
    },
    {
        "id": "ollama", "name": "Ollama 本地", "color": "#6B7280", "logo": "",
        "note": "", "homepage": "https://ollama.com/",
        "api_key": "", "base_url": "http://localhost:11434/v1",
        "model": "", "enable_thinking": False,
    },
]

DEFAULT_CONFIG = {
    "active_provider": "bailian",      # 当前使用的服务商 id
    "providers": [dict(p) for p in PROVIDER_PRESETS],
    "prompts": {
        "ocr": DEFAULT_OCR_PROMPT,
        "answer": DEFAULT_ANSWER_PROMPT,
        "translate": DEFAULT_TRANSLATE_PROMPT,
    },
    "request_template": DEFAULT_REQUEST_TEMPLATE,
    "mode": "overlay",                 # 运行模式: overlay=悬浮窗 / translate=翻译 / snip=自由截图 / mini=迷你条
    "ui": {
        "theme": "light",              # light / dark / gray / eyecare / contrast / custom
        "customTheme": None,           # 自定义主题(theme=custom 时生效)
        "radius": 12,                  # 全局圆角
        "fontSize": 13,                # 全局字号
        "panelOpacity": 96,            # 面板不透明度(%)
        "holeColor": "#FF5252",        # 洞口边框颜色
        "holeStyle": "dashed",         # solid / dashed / dotted
        "holeRadius": 4,               # 洞口边框圆角
    },
    "window": {
        "always_on_top": True,
        "width": 640,                  # 启动时的窗口尺寸(拖动后自动记忆更新)
        "height": 680,
        "x": None,                     # 悬浮窗位置(拖动后自动记忆)
        "y": None,
        "miniWidth": 420,              # 迷你条尺寸(图标行 + 提问输入行)
        "miniHeight": 78,
        "mini_x": None,                # 迷你条位置;为空时首次进入自动居中于任务栏上方
        "mini_y": None,
        "translateWidth": 760,         # 翻译模式窗口尺寸
        "translateHeight": 620,
        "translate_x": None,
        "translate_y": None,
        "holeWidth": None,             # 洞口(OCR 区域)尺寸
        "holeHeight": None,
        "chromeHeight": 300,           # 窗口非洞口部分高度(标题栏+底部面板,由前端上报)
    },
    "capture": {
        "max_side": 2048,              # 发送前图片长边压缩上限(px)
        "flash_delay_ms": 80,          # 截图瞬隐时长(毫秒)
        "last_rect": None,             # 最近一次框选区域(翻译模式复用)
    },
    "timeout": 180,                    # 模型最长响应时间(秒)
    "retry": {
        "max_retries": 3,              # 失败自动尝试次数
        "backoff": 0.8,                # 重试退避基数(秒,指数增长)
    },
    "ocr": {
        "mode": "cloud",               # OCR 方式: cloud=云端(所选大模型识别) / local=本地(RapidOCR)
    },
    "translate": {
        "source_lang": "自动检测",      # 来源语言
        "target_lang": "中文",         # 目标语言
        "mode": "cloud",               # 翻译方式: cloud=云端大模型 / local=端侧模型
        "engine": "auto",              # 本地引擎: auto / argos(端侧离线模型) / ollama(本地大模型)
        "display": "bilingual",        # 展示方式: bilingual=双语逐行对照 / translated=仅译文
        "auto_refresh": False,         # 自动刷新:定时重新捕获并翻译
        "auto_interval_ms": 2500,      # 自动刷新间隔(毫秒)
    },
    "knowledge": [],                   # 本地知识库:[{keys:[...], answer, detail}]
    "hotkeys": {
        "capture": "ctrl+f1",          # 截图并识别
        "exit": "ctrl+q",              # 退出程序
    },
    "behavior": {
        "default_question": "请回答识别到的内容",
        # 示例提问(界面下拉可选,可在设置中编辑)
        "question_presets": [
            "请回答识别到的内容",
            "请翻译识别到的内容",
            "请解释识别到的内容",
            "请总结识别到的内容的要点",
            "请搜索并告诉我相关联的内容",
            "请给出该题目的答案",
            "请把识别到的内容整理成表格",
        ],
        "question_history": [],        # 用户自输入的提问(自动保存,最多 20 条)
    },
    "storage": {
        "cache_dir": str(ROOT / "cache"),        # 应用缓存位置(真实路径,自动创建)
        "questions_dir": str(ROOT / "questions"),  # 题目保存位置(真实路径,自动创建)
        "add_to_knowledge": False,               # 是否将 AI 回答自动添加到本地知识库
    },
    "app": {
        "version": "2.2.0",
        "github": "https://github.com/TDCQCX/OCR-Assistant",  # 关于页跳转地址
        "qq_group": "1108236960",
        "license": "MIT",
        "features": "悬浮窗/翻译/框选/迷你条 · 端侧+云端双OCR/翻译 · 双语对照 · 多平台 · 全局主题",
    },
}

# 语言列表(界面下拉与端侧模型语言码映射)
LANGUAGES = ["自动检测", "中文", "英语", "日语", "韩语", "法语", "德语", "俄语",
             "西班牙语", "葡萄牙语", "意大利语", "阿拉伯语", "泰语", "越南语"]

LANG_CODES = {
    "中文": "zh", "英语": "en", "日语": "ja", "韩语": "ko", "法语": "fr", "德语": "de",
    "俄语": "ru", "西班牙语": "es", "葡萄牙语": "pt", "意大利语": "it",
    "阿拉伯语": "ar", "泰语": "th", "越南语": "vi",
}


def active_provider(cfg: dict) -> dict:
    """返回当前激活的服务商配置。"""
    active = cfg.get("active_provider", "")
    for p in cfg.get("providers", []):
        if p.get("id") == active:
            return p
    return cfg.get("providers", [{}])[0]


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并:override 中的嵌套 dict 与 base 合并,其余覆盖。"""
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG, ensure_ascii=False))
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            cfg = _deep_merge(cfg, data)
        except Exception:
            pass  # 配置损坏时使用默认值
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )

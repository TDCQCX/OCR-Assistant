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
    "你是答题助手。以下是用户截取的题目区域:①OCR识别出的文字(可能不完整或有误,"
    "以截图为准,请自行核实);②原始截图图片。\n"
    "题型:{qtype}\n"
    "题目:{qtitle}\n"
    "选项:\n{options}\n"
    "请结合截图中的题目内容与OCR识别文字,回答下面的问题/指令。\n"
    "要求:只输出最终答案本身,不要任何前言、解释、后缀,不要重复粘贴OCR内容。"
    "若是选择题,请给出选项字母及对应选项内容;若是其他题型,请给出对应答案。\n\n"
    "问题/指令:{question}\n\n"
    "OCR识别结果:\n{ocr_text}"
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
    },
    "request_template": DEFAULT_REQUEST_TEMPLATE,
    "window": {
        "always_on_top": True,
        "width": 640,                  # 启动时的窗口尺寸(拖动后自动记忆更新)
        "height": 680,
        "corner_radius": 12,           # 窗口圆角
        "border_color": "#FF5252",     # 洞口边框颜色
    },
    "theme": {
        "preset": "light",             # dark=黑色 / light=白色 / gray=灰色
        "image": "",                   # 背景图片路径(空=纯色)
        "image_scale": 100,            # 图片缩放百分比
        "image_offset_x": 0,           # 图片 X 偏移
        "image_offset_y": 0,           # 图片 Y 偏移
    },
    "capture": {
        "max_side": 2048,              # 发送前图片长边压缩上限(px)
        "flash_delay_ms": 60,          # 截图时边框瞬隐时长(毫秒)
    },
    "timeout": 180,                    # 模型最长响应时间(秒)
    "retry": {
        "max_retries": 3,              # 失败自动尝试次数
        "backoff": 0.8,                # 重试退避基数(秒,指数增长)
    },
    "ocr": {
        "mode": "cloud",               # OCR 方式: cloud=云端(所选大模型识别) / local=本地(RapidOCR)
    },
    "knowledge": [],                   # 本地知识库:[{keys:[...], answer, detail}]
    "hotkeys": {
        "capture": "ctrl+f1",          # 截图并识别
        "exit": "ctrl+q",              # 退出程序
    },
    "behavior": {
        "default_question": "请给出该题目的答案",
    },
    "storage": {
        "cache_dir": str(ROOT / "cache"),        # 应用缓存位置(真实路径,自动创建)
        "questions_dir": str(ROOT / "questions"),  # 题目保存位置(真实路径,自动创建)
        "add_to_knowledge": False,               # 是否将 AI 回答自动添加到本地知识库
    },
    "app": {
        "version": "1.0.0",
        "github": "https://github.com/TDCQCX/OCR-Assistant",  # 关于页跳转地址
        "qq_group": "1108236960",
        "license": "MIT",
        "features": "透明洞口截图 · 云端/本地OCR · 图文答题 · 多平台 · 本地知识库",
    },
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

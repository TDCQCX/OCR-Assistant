# -*- coding: utf-8 -*-
"""对话框冒烟测试:构造并短暂显示 设置/主题 对话框,验证字段载入、JSON 预览与保存逻辑。

运行: .venv\\Scripts\\python scripts\\test_dialogs.py
"""
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.agent import AgentClient  # noqa: E402
from app.config import load_config  # noqa: E402
from app.dialogs import SettingsDialog, ThemeDialog  # noqa: E402


def main():
    app = QApplication(sys.argv)
    cfg = load_config()

    d1 = SettingsDialog(cfg)
    d2 = ThemeDialog(cfg)
    print("设置对话框构造 OK; 平台数:", len(d1.provider_btns))
    d1.show()
    d2.show()

    def check():
        app.processEvents()
        # 平台字段载入(选中平台字段与其配置一致)
        assert len(d1.provider_btns) >= 5, "平台数量不足"
        p_sel = cfg["providers"][d1._current]
        assert d1.model_edit.text() == p_sel.get("model", ""), "平台模型ID 未载入"
        assert d1.base_edit.text() == p_sel.get("base_url", ""), "平台 Base URL 未载入"
        assert d1.preview_edit.toPlainText().strip(), "JSON 预览为空"
        print("平台字段载入 OK; 预览首行:",
              d1.preview_edit.toPlainText().splitlines()[0])

        # 已配置/未配置分区:给首个平台填 Key 后重建,计数应与配置一致
        cfg["providers"][0]["api_key"] = "k"
        d1._rebuild_provider_cards()
        app.processEvents()
        names = [b.objectName() for b in d1.provider_btns]
        expected_conf = sum(1 for p in cfg["providers"] if (p.get("api_key") or "").strip())
        assert names.count("providerCard") == expected_conf, names
        assert names.count("providerCardDim") == len(cfg["providers"]) - expected_conf, names
        print(f"已配置/未配置分区 OK: 已配置={expected_conf}, 未配置={len(names) - expected_conf}")

        # 自定义平台:无弹窗,右侧空预设,JSON 为默认格式
        count_before = len(cfg["providers"])
        d1._add_provider()
        app.processEvents()
        assert len(cfg["providers"]) == count_before + 1, "未添加自定义平台"
        assert d1.model_edit.text() == "" and d1.key_edit.text() == "" and d1.base_edit.text() == ""
        assert '"model": ""' in d1.preview_edit.toPlainText(), "JSON 应为默认格式(空模型)"
        print("自定义平台(空预设) OK")

        # 平台名称可编辑提交
        d1.provider_name_edit.setText("测试平台X")
        d1._on_name_committed()
        assert cfg["providers"][-1]["name"] == "测试平台X", "名称修改未生效"
        print("名称编辑 OK")

        # 常规设置保存 + OCR 模式
        d1.timeout_spin.setValue(120)
        d1.retry_spin.setValue(2)
        d1.btn_ocr_local.setChecked(True)
        d1._save_all()
        assert cfg["timeout"] == 120, "超时设置未保存"
        assert cfg["retry"]["max_retries"] == 2, "重试设置未保存"
        assert cfg["ocr"]["mode"] == "local", "OCR 模式未保存"
        print("常规设置保存 OK: timeout=120, retries=2, ocr=local")

        # 思考开关注入模板
        buf = io.BytesIO()
        Image.new("RGB", (32, 32), "white").save(buf, format="PNG")
        client = AgentClient("k", "test-model", "http://x", cfg["request_template"],
                             enable_thinking=True)
        payload = client._build_payload("你好", buf.getvalue())
        assert payload["enable_thinking"] is True, "思考开关未注入"
        print("思考注入 + 模板构建 OK")

        # 主题对话框(默认应为白色)
        print("ThemeDialog 构造 OK; 当前预设:",
              [k for k, b in d2.swatch.items() if b.isChecked()])
        assert cfg["theme"]["preset"] == "light", "默认主题应为白色"
        print("默认主题 = light OK")
        app.quit()

    QTimer.singleShot(800, check)
    app.exec()
    print("对话框冒烟测试完成")


if __name__ == "__main__":
    main()

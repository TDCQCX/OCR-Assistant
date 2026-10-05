# DS-code 工作约定(本仓库)

> 这份文件对本仓库生效,**优先级高于个人默认规则**里与验证相关的部分。
> 上层还有用户级 `AGENTS.md`(`C:\Users\<用户名>\.zcode\AGENTS.md`),两者冲突时以本文为准。

## 1. 每次改动都必须跑验证(硬性)

改完代码(含只改文档以外的任何文件)**必须**执行:

```bash
./.venv/Scripts/python.exe tools/check.py
```

它做两件事,顺序固定 —— **先测试基准,再审计这次改动**:

| 步骤 | 内容 | 退出码 |
|---|---|---|
| 测试基准 | `pytest tests/`(140 项:配置/历史/请求日志/题目解析/端侧翻译/云端客户端/流水线/桥接契约/发版同步/平台层) | 非 0 即有失败 |
| 改动审计 | `tools/audit_changes.py` 按历史踩坑清单核对工作区改动 | 有 BLOCK 即非 0 |

需要时追加参数:

```bash
./.venv/Scripts/python.exe tools/check.py --gui          # 追加真窗口冒烟(会短暂弹窗 ~20s)
./.venv/Scripts/python.exe tools/check.py --base HEAD~1  # 审计最近一次提交
./.venv/Scripts/python.exe tools/check.py -k worker      # 只跑名字含 worker 的用例
```

单独运行:

```bash
./.venv/Scripts/python.exe -m pytest tests -q             # 只跑测试
./.venv/Scripts/python.exe tools/audit_changes.py         # 只跑审计
./.venv/Scripts/python.exe tools/audit_changes.py --all   # 全量体检(不限改动范围)
./.venv/Scripts/python.exe tools/gui_smoke.py            # 只跑真窗口冒烟
```

**改前端之后额外必做**:`cd frontend && npm run build`
(审计的 `build.sync` 规则会在"改了 `frontend/src` 但没重建 `app/webui`"时直接 BLOCK。)

## 2. 审计结论怎么处理

| 级别 | 含义 | 要求 |
|---|---|---|
| `BLOCK` | 大概率出缺陷(构建未同步、桥接方法不存在、事件没人处理、把界面文案写进 status) | **必须修掉才能提交** |
| `WARN` | 有风险、需要人工判断(新增静默吞异常、用了没定义的 CSS 类、窗口坐标算术) | 逐条确认;若确属有意为之,在代码里写清理由并加入 `tools/audit_changes.py` 的对应白名单 |
| `INFO` | 提示(版本号变更、工作区未提交) | 不需要动作 |

**不许为了让它通过而放宽规则**:白名单只能加"代码里有注释说明理由"的项,
每条都要有对应的测试兜着(`tests/test_audit_tool.py` 会检查白名单是否已腐坏)。

## 3. 测试基准的边界

- `tests/` 里的用例**绝不读写仓库里的真实数据**:`config.json` / `history.json` /
  `request_log.json` / `questions/` 全部由 `tests/conftest.py` 的 `sandbox` fixture 重定向到临时目录。
  新写用例请沿用这个 fixture。
- 需要网络或端侧模型的用例必须 `monkeypatch` 掉外部依赖(参考 `tests/test_local_translate.py`)。
- 已知缺陷不要直接写"正确"的断言:先按**现状**写成用例,在 docstring 里标 `已知缺陷` + 修复方向,
  修好后再把断言翻过来。这样缺陷不会在无人知晓的情况下被"测试通过"掩盖。
- 真窗口相关的验证只放在 `tools/gui_smoke.py`,不要写进 `tests/`(CI/无显示环境会挂)。

## 4. 提交前

```bash
git status --short          # 只 add 自己改过的文件,不要 git add -A
```

- 不要提交 `app/webui/` 之外的构建中间产物;`.mimosa/`、`.pytest_cache/` 已在 `.gitignore`。
- 版本号一旦变动,`version.sync` 规则会检查:spec 文件名、`version_info.txt`、
  `frontend/package.json`、README 徽章、CHANGELOG、TUTORIAL 里的 exe 名,缺一处就报错。

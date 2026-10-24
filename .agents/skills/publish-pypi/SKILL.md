---
name: publish-pypi
description: 发布 ashare-data-lite 的新版本到 PyPI；用于本仓库的版本升级、打包验证、标签推送、GitHub Actions 可信发布和发布后安装检查。
---

# 发布 ashare-data-lite

发行名为 `ashare-data-lite`，Python 导入名为 `ashare_data`，仓库为 `https://github.com/zhangjw777/ashare-data-lite`。版本唯一来源为 `src/ashare_data/__init__.py` 中的 `__version__`，`pyproject.toml` 动态读取该值。

用户明确要求发布时，执行下列流程；仅检查或编辑文档的请求保持在其授权范围内。

1. 确认实际仓库路径、`main` 分支、`origin`、工作区及本地/远程标签。保留已有修改，审阅变更后只提交本次发布所需文件。检查暂存文件中的凭据、`.env` 和本地环境文件。
2. 查询 `https://pypi.org/pypi/ashare-data-lite/json` 的已有版本；结合用户要求选择新的 `X.Y.Z` 版本。首次发布从可用的 `0.1.0` 开始。现有版本与标签保持不可变。
3. 安装开发工具：`python -m pip install -e ".[dev]"`。工作区干净后执行 `python scripts/release.py X.Y.Z`。该命令会验证 wheel、sdist、元数据、干净环境安装、公开导入、全部测试及 README 示例，并推送提交与版本标签。`--check-only` 可只执行检查。
4. 查看 `.github/workflows/publish.yml` 对应标签的运行状态。构建任务和发布任务独立；发布任务必须使用 GitHub Environment `pypi`、`id-token: write` 和 `pypa/gh-action-pypi-publish` 的 OIDC 认证。
5. 使用已认证的 `gh run list/view/watch` 或 GitHub 连接工具读取运行结果及失败日志。GitHub 连接工具 `fetch` 支持工作流 REST 查询地址；查询以实际提交和标签为准。发布配置应匹配仓库 `zhangjw777/ashare-data-lite`、文件 `publish.yml` 和 Environment `pypi`。
6. 如果是网络或平台瞬时故障，修复环境后可重试同一运行。如果发行内容或工作流需要改动，提交修复并用新版本和新标签发布。完成最多三次有具体错误依据的修复重试后，遇到账户权限、环境审批或可信发布者配置阻碍时，报告准确原因及用户最少操作。
7. 成功后查询 PyPI 的指定版本 JSON，创建新的虚拟环境，从 `https://pypi.org/simple` 安装 `ashare-data-lite==X.Y.Z`，确认发行版本等于 `ashare_data.__version__`，并实际调用 `get_etf_quote("159941")`。实时源异常时，将安装/导入结果与网络调用结果分别报告。

最终交付包名、版本、导入名、PyPI 地址、工作流运行地址、安装命令、已验证示例和下次版本发布命令。账户凭据通过环境变量与 OIDC 使用，Git 提交与发行文件仅保存项目代码及公开配置。

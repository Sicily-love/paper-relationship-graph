# Paper Atlas

Paper Atlas 是一个本地论文库工具。它用时间泳道展示分类、年份和库内引用关系，并把最新 arXiv、领域高被引与共同引用论文放进同一个待审核列表。

![Paper Atlas v1.2.0 时间泳道界面](preview.png)

当前版本是 [v1.2.0](https://github.com/Sicily-love/paper-relationship-graph/releases/tag/v1.2.0)。点击 App 侧栏底部的版本号，可以直接查看由 [CHANGELOG.md](CHANGELOG.md) 生成的历次更新内容。

## 当前发布状态

v1.2.0 Release 提供 GitHub 自动生成的源码归档，不提供 DMG 或 SHA-256 附件。仓库根目录下的 `Paper Atlas.app` 和 `dist/` 是本机构建产物，不会提交到 Git。

本地执行 `make release` 可以生成临时签名的测试 DMG；它没有 Developer ID 签名和 Apple 公证，只适合自己使用。正式公开安装包仍需完成签名和公证后再上传。

## 运行方式

### macOS 原生 App

如果已经在本地构建了 `Paper Atlas.app`，将它移动到固定位置后再打开。首次运行会要求选择论文库根目录。v1.2.0 尚未提供“新建空论文库”向导；所选目录应当已经包含下文列出的 10 个分类目录和至少一篇已分类 PDF。

原生 App 使用内置 WebKit 直接显示界面，不启动 localhost 服务，也不需要默认浏览器或常驻终端。它内置通用架构 Python 与 PDF 读取组件，运行时不会再安装 Python 依赖。程序代码和可变配置保存在：

```text
~/Library/Application Support/Paper Atlas/runtime
```

论文 PDF 始终保存在首次选择的论文库中。自动任务安装在 `~/Library/LaunchAgents`；因此应先把 App 放到 `/Applications` 等固定位置，再在“自动化与数据”中点击“保存并启用”。

当前本地测试构建是临时签名版本，macOS 可能阻止直接打开。可在 Finder 中右键 App 并选择“打开”。这不等同于 Developer ID 签名或 Apple 公证。

### 从源码运行

源码模式需要 Python 3.10 或更高版本。论文库位于仓库的上一级目录时，可以运行：

```bash
make start
```

使用其他论文库位置时，直接指定路径：

```bash
python3 scripts/start_app.py --papers-dir "/path/to/paper-library"
```

Windows 可以双击 `platform/windows/start-paper-atlas.bat`；该脚本同样默认使用仓库的上一级目录作为论文库。源码模式首次运行会在项目内创建 `.venv` 并联网安装依赖，然后启动只监听 `127.0.0.1` 的本地服务并打开系统默认浏览器。关闭终端会停止服务。

原生 App 与源码模式不会共用候选、搜索主题、图谱缓存或任务配置：前者使用 `Application Support`，后者直接使用仓库中的 `config/`、`web/data/` 和 `.cache/`。因此在仓库运行 `make update` 不会更新已安装 App 中的图谱；App 内应使用“重新检查并构建”。

## 时间泳道

- 横向位置表示年份，纵向泳道表示分类。
- 节点大小按库内被引用次数缩放，并设有最小和最大尺寸。每个类别中库内被引最多的论文是主节点；并列时优先选择年份更早的论文。
- 单击节点只显示它的一阶引用关系；双击打开论文详情。
- 选中论文后，橙色连线与光环表示“本文引用”，蓝色表示“引用本文”。
- 页面没有“全部引用”开关。未选中论文时，引用线只作为低透明度背景；选中后，仅该论文的一阶关系以高对比度显示。
- 详情中的引用条目会显示本地标题匹配的可信度和证据。

图谱节点目前只来自分类目录中的 PDF。PPTX 会被分类检查识别，但不会生成图谱节点、摘要或引用关系。

## 论文发现与归档

候选来自三套独立来源：

- arXiv 搜索按主题获取近期论文，并根据标题、摘要、关键词和领域信号计算相关性。低相关结果不会进入候选列表。
- 领域高被引按同一组主题搜索 OpenAlex，再按引用量排序；默认要求至少被引 50 次，可在“发现论文”菜单中调整下限，每个主题最多保留 5 篇。这个设置会保存下来，并由每天 11:00 的任务继续使用。
- 共同引用通过 OpenAlex 中与库内论文对应的参考文献列表，找出被多篇库内论文共同引用、但尚未归档的论文。共同引用次数下限也在“发现论文”菜单中设置。

三个来源会合并去重，已存在于论文库中的同标题论文不会再次进入候选。待审核论文按发布时间倒序排列；选择候选后可在右侧切换摘要、元数据和推荐依据。高被引候选优先根据标题和摘要分类，证据不足时使用命中的搜索主题给出待确认建议。

“搜索主题”提供与 10 个分类对应的模板。“保存并立即发现”会同时搜索最新 arXiv 与领域高被引，并合并去重；共同引用仍需从“发现论文”菜单单独运行。“清空待审核”只删除尚未处理的候选，不删除已有审核决策。

点击“加入论文库”后，Paper Atlas 会下载并验证 PDF、检查内容重复、归档到确认后的类别、保存审核决策并重建图谱。没有可下载 PDF 的候选只能先打开来源页人工获取。

归档和决策写入属于同一事务：写入失败时文件会回到原位置。图谱重建失败不会删除已经归档的论文，而是标记为待重试，可以在“运行与数据”中重新构建。

## 每日任务

“自动化与数据”中的“App 本机每日任务”可以管理两项任务：

- 论文分类整理：每天 10:30。只自动移动高置信度结果，其余文件留待确认。
- 主题论文发现：每天 11:00，同时获取最新 arXiv 与领域高被引候选。

macOS 原生 App 使用 `launchd`，关闭 Paper Atlas 后任务仍可按时运行。修改开关或时间后，只有点击“保存并启用”才会安装或更新本机任务。Windows、Linux 和源码浏览器模式不会自动安装定时任务。

每项任务会保留最后一次运行结果。点击“运行日志”可在浮动面板中查看完整输出，点击面板外部或按 Esc 即可收起。

如果仍保留 Codex 中的同名定时任务，请只启用其中一套调度方式，避免重复执行。App 中显示“尚未安装”时，本机 `launchd` 不会运行这些任务。

## 数据检查与备份

应用启动时会检查：

- 分类目录和本地 PDF 是否对应图谱节点；
- 引用边是否指向有效论文；
- JSON 与页面使用的 JS 数据是否一致；
- 已归档论文是否仍等待图谱更新；
- 候选数据和审核决策是否可读。

“导出备份”保存搜索主题、候选、审核决策、任务配置和只读图谱清单，不包含论文 PDF，也不复制图谱文件。“恢复备份”只接受 Paper Atlas 自己生成的 JSON 文件；恢复后需要再次点击“保存并启用”，才会把任务时间写入 `launchd`。

## 当前分类

```text
01_模型架构与训练优化
02_注意力机制与长上下文
03_MoE与稀疏模型
04_量化与低精度计算
05_分布式训练与数据基础设施
06_GPU内核_编译器与性能工程
07_GPU内核智能体与自动调优
08_通用智能体与自主学习
09_生成模型与视频系统
10_大模型技术报告与推理训练
```

## 常用命令

| 命令 | 用途 |
| --- | --- |
| `make start` | 启动浏览器版本 |
| `make classify` | 保守分类新增论文并重建图谱 |
| `make update` | 检查分类并重建图谱，不启动浏览器 |
| `make update-preview` | 重建图谱，再用 macOS WebKit 更新 README 预览图 |
| `make health` | 检查本地文件与生成数据 |
| `make discover` | 搜索最新 arXiv 与领域高被引论文 |
| `make discover-highly-cited` | 只生成领域高被引候选 |
| `make discover-shared` | 生成共同引用候选 |
| `make release-notes` | 从 CHANGELOG 生成 App 内更新记录 |
| `make test` | 运行自动测试 |
| `make python-runtime` | 下载并校验官方通用架构 Python 构建运行时 |
| `make mac-app` | 生成内置 Python 与 PDF 组件的通用架构 macOS 应用 |
| `make release` | 在本机 `dist/` 生成临时签名测试 DMG 和 SHA-256 |
| `make release-public` | 生成正式 DMG；强制要求 Developer ID 和 Apple 公证 |
| `make release-check` | 执行发布一致性检查 |

## 数据来源与隐私

论文库节点的标题来自 PDF 文件名，年份、作者和摘要从本地 PDF 尝试提取；候选元数据来自 arXiv 或 OpenAlex。外部引用和引用量来自 OpenAlex，库内引用由本地 PDF 的参考文献标题匹配得到。自动提取和匹配都可能有误，候选应在归档前人工核对。

论文 PDF 不会上传到仓库或第三方。论文整理、图谱浏览和已下载 PDF 解析可以完全离线运行；执行论文发现时仍需联网，论文标题会发送给 OpenAlex 用于引用匹配，搜索关键词会发送给 arXiv 和 OpenAlex。应用没有用户账户、遥测或云同步。

打包时会为应用内运行目录生成干净的初始状态：自定义搜索主题、推荐候选和审核记录全部清空，并检查是否残留用户绝对路径。这个过程只修改应用包，不会删除本地论文库或 `Application Support` 中的现有状态。

仓库包含应用代码、当前图谱元数据和候选数据快照，不包含论文 PDF。构建 App 时会生成干净的初始候选状态，因此新初始化的 App 运行目录不会继承仓库中的搜索主题、候选或审核记录。

## 常见问题

### 应用打不开

确认打开的是本机构建的 `Paper Atlas.app`，而不是 GitHub 源码压缩包。临时签名构建可能需要在 Finder 中右键 App 并选择“打开”。当前 v1.2.0 Release 没有 DMG；公开安装包必须先通过 Developer ID 签名和 Apple 公证。

### 页面提示管理功能未连接

退出并重新打开应用。浏览器版本请使用 `make start`，不要直接打开 `web/index.html`。

### 论文已归档但图谱没有更新

打开“运行与数据”，查看具体错误并点击“重新检查并构建”。已下载的 PDF 和审核决策会保留。

### 每日任务运行了两次

检查是否同时启用了 Paper Atlas 的 `launchd` 任务和 Codex 定时任务，只保留一套。仅在 App 中设置了时间、但没有点击“保存并启用”，不会安装 `launchd` 任务。

### 为什么之前会出现 Chrome 意外退出

旧版 README 截图工具会在开发者手动运行 `make update-preview` 时启动无头 Chrome，个别 macOS 环境会因此出现崩溃提示。当前截图工具已改用系统 WebKit；每日任务和原生 App 也不调用 Chrome。只有源码模式的 `make start` 会按设计打开系统默认浏览器，如果默认浏览器是 Chrome，它仍会正常启动 Chrome。

### arXiv 结果偏离主题

在“搜索主题”中使用更具体的多词关键词，并添加排除词。候选卡片会显示实际命中位置和相关性分数。

## 开发与发布

macOS App 构建需要 Xcode Command Line Tools、Python 3.10 或更高版本，以及首次下载 Python.org 运行时所需的网络连接。

```bash
python3 -m pip install -r requirements.txt
make test
make mac-app
```

`make mac-app` 首次运行会下载并验证 Python.org 的通用架构 Python 3.12 运行时，之后复用 `.cache/python-runtime`。前端不需要 npm 构建。修改 `web/` 后刷新页面即可；修改 `CHANGELOG.md` 或 `VERSION` 后先运行 `make release-notes`，生成的更新记录会同时进入源码页面和 App。

`Paper Atlas.app` 和 `dist/` 都是本机构建产物，不提交到仓库。GitHub Actions 只验证源码能否通过测试、构建和发布检查，不保存临时签名安装包。

生成本地测试 DMG：

```bash
make release
```

生成允许公开上传的 Developer ID 签名、公证版本：

```bash
PAPER_ATLAS_SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" \
PAPER_ATLAS_NOTARY_PROFILE="paper-atlas-notary" \
make release-public
```

`PAPER_ATLAS_NOTARY_PROFILE` 需要先用 `xcrun notarytool store-credentials` 保存。`make release-public` 会在缺少证书、公证配置或公证票据时直接失败；没有 Apple Developer 证书时只能使用 `make release` 生成不对外发布的测试包。

项目采用 MIT License，版本变化见 [CHANGELOG.md](CHANGELOG.md)。

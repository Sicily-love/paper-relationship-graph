# Paper Relationship Graph

从本地分类论文库生成可交互的球状关系图。项目不上传或复制 PDF，只把标题、年份、类别和论文库内部关系写入静态数据文件。

![类别高亮与方向边示例](preview.png)

## 图谱规则

- 一个节点代表一篇唯一论文；SHA-256 完全相同的 PDF 会合并。
- 每个类别选择一个主节点：在当前论文库中被其他论文引用次数最多的论文。
- 节点大小表示库内被引用次数，并使用固定的最小、最大半径防止极端尺寸。
- 引用边方向为 `引用论文 -> 被引用论文`。
- 时间不使用连线：年份决定三维球壳半径，较早论文靠近球心，较新论文靠近外层；二维投影不要求严格保持远近顺序。
- 不生成内容相似边，避免与类别关系重复。
- 点击论文会将球体旋转到该论文位于中心的位置，并聚焦一阶关系。
- 右侧详情面板显示作者、摘要、年份、类别，以及库内引用和被引用论文；关系列表中的论文可以继续点击跳转。
- 通过本地服务打开时，可以从详情面板直接打开论文库中的 PDF；PDF 不会被复制进仓库。
- 从类别下拉框选择类别后，会高亮该类别并将类别主节点旋转到中心。

## 本地生成

需要 Python 3.10+。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make build PAPERS_DIR=..
```

生成结果：

- `web/data/graph.json`：可复用的结构化数据
- `web/data/graph-data.js`：浏览器直接加载的数据

### 新增论文后的完整更新

论文完成分类后，运行：

```bash
make update PAPERS_DIR=..
```

该命令会检查所有 PDF/PPTX 是否位于 10 个标准类别中，识别新增和移除文件，重新提取年份、作者、摘要和内部引用，重选类别主节点，并更新图数据与 `preview.png`。如果还有论文散落在根目录或未知文件夹，命令会列出文件并停止，避免图谱悄悄漏掉论文。

`preview.png` 使用本机 Chrome/Chromium 生成；未安装浏览器时，数据仍可通过 `make build` 单独生成。

### 本地查看与打开 PDF

直接打开 `web/index.html` 可以查看图谱。若要从详情面板打开本地 PDF，请启动带安全 PDF 路由的本地服务：

```bash
make serve
```

然后访问 <http://localhost:8000>。

本地服务仅监听 `127.0.0.1`，并且只允许 `/papers/` 路径读取指定论文目录中的 PDF。

## 使用其他论文目录

论文目录需要按 `数字_类别名/*.pdf` 组织：

```bash
python scripts/build_graph.py \
  --papers-dir /path/to/paper-library \
  --output-json web/data/graph.json \
  --output-js web/data/graph-data.js
```

## 校验

```bash
make test
```

当前引用关系通过本地 PDF 参考文献标题匹配得到。若后续加入外部推荐论文，可再用 Semantic Scholar 或 OpenAlex 对引用关系和外部引用量进行校验。

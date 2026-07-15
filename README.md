# Paper Relationship Graph

从本地分类论文库生成可交互的球状关系图。项目不上传或复制 PDF，只把标题、年份、类别和论文库内部关系写入静态数据文件。

![类别高亮与方向边示例](preview.png)

## 图谱规则

- 一个节点代表一篇唯一论文；SHA-256 完全相同的 PDF 会合并。
- 每个类别选择一个主节点：在当前论文库中被其他论文引用次数最多的论文。
- 节点大小表示库内被引用次数，并使用固定的最小、最大半径防止极端尺寸。
- 引用边方向为 `引用论文 -> 被引用论文`。
- 时间不使用连线：较早论文靠近球心，较新论文靠近外层。
- 不生成内容相似边，避免与类别关系重复。
- 点击论文会将球体旋转到该论文位于中心的位置，并聚焦一阶关系。
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

直接打开 `web/index.html` 即可查看，也可以启动本地服务器：

```bash
make serve
```

然后访问 <http://localhost:8000>。

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

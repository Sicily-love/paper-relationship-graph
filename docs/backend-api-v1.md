# Paper Atlas 后端 API v1

这份文档描述本地 App 与源码浏览器共用的 API 契约。API 是离线优先的：原生 App 通过常驻 Python Worker 调用，源码模式通过只监听回环地址的 HTTP 适配器调用。发现、分类、图谱和备份算法仍由 `scripts/` 中的现有实现提供。

## 传输协议

请求统一包含 `method`、`path`、JSON `body` 和 `request_id`。HTTP 模式支持 `X-Paper-Atlas-Token`；原生模式使用等价的 Worker 帧。Objective-C 不应根据业务命令解释响应，只负责转发。

成功响应：

```json
{
  "data": {},
  "meta": {"api_version": "1", "request_id": "req_...", "revision": "..."}
}
```

错误响应：

```json
{
  "error": {
    "code": "validation_failed",
    "message": "请求参数无效",
    "retryable": false,
    "details": {}
  },
  "meta": {"api_version": "1", "request_id": "req_..."}
}
```

## 核心资源

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/bootstrap` | 能力、revision、数量摘要 |
| GET/PUT | `/api/v1/topics` | 读取或保存搜索主题 |
| GET | `/api/v1/graph` | 当前图谱快照 |
| GET | `/api/v1/candidates` | 分页读取候选，支持 `status/source/category/limit` |
| POST | `/api/v1/discovery-runs` | 创建一次多来源发现任务 |
| POST | `/api/v1/candidates/{id}/decision` | 原子提交推荐反馈与审核决定 |
| DELETE | `/api/v1/candidates` | 清空指定状态候选 |
| GET | `/api/v1/classification-reviews` | 分类待审核队列 |
| POST | `/api/v1/classification-reviews/{id}/decision` | 确认分类并更新图谱 |
| POST | `/api/v1/graph-builds` | 创建图谱重建任务 |
| DELETE | `/api/v1/graph/nodes/{id}` | 归档节点对应的论文文件 |
| GET | `/api/v1/jobs/{id}` | 查询任务状态与进度 |
| GET | `/api/v1/jobs` | 查询任务列表 |
| POST | `/api/v1/jobs/{id}/cancel` | 取消尚未开始的任务 |
| GET | `/api/v1/logs` | 读取分页运行日志 |
| POST | `/api/v1/diagnostic-runs` | 创建诊断任务 |
| POST | `/api/v1/maintenance-runs` | 创建维护任务 |
| POST | `/api/v1/backups` | 创建备份任务 |

论文发现、下载归档、图谱重建、分类整理、诊断和备份恢复都返回 `202` 与 Job。Job 状态为 `queued`、`running`、`succeeded`、`failed`、`cancelled` 或 `interrupted`。

## 一致性规则

- 变更请求支持 `Idempotency-Key`；重复加入候选只能得到同一个结果。
- 资源更新带 `revision` 或 `expected_revision`，不一致时返回 `409`。
- 论文库和候选数据使用跨进程数据锁；App、浏览器和每日任务共享同一锁文件。
- 原子写入和现有回滚逻辑继续保留，SQLite 只保存运行状态、任务和事件，不取代 PDF 与图谱快照。
- `/api/*` 旧路径已停止服务，避免两套语义继续分叉；所有传输都通过 `api_contract.py` 中的操作表统一分派。

## 错误代码

`validation_failed`（422）、`not_found`（404）、`job_conflict`（409）、`revision_conflict`（409）、`provider_rate_limited`（429）、`storage_unavailable`（503）、`job_timeout`（504）和 `internal_error`（500）。前端只依赖 `code` 和 `retryable`，不解析中文错误文本。

# 多栏目 / 多剧集架构（PR-01）

## 实施状态

本 PR 引入可运行的栏目与剧集隔离（数据 + API + 初版 Streamlit UI），**不等于** 已有并行视频 Worker 或云端租户权限。所有调用仍为离线、无付费 API 模式。

## 层级与归属

```text
Factory
 ├── Column (栏目)：标识、名称、默认制作风格、栏目定位
 │    ├── Series (剧集，现有 projects 表的兼容名称)
 │    │    ├── StoryBible（不可变版本）
 │    │    ├── series_assets（actor / scene / voice / prop，不可变版本）
 │    │    └── Episode → Production runs
 │    └── Series ...
 └── Column ...
```

- **栏目**可以同时拥有多部剧；栏目负责分组，绝不默认共用人物。
- **剧集**是演员、场景、声音、道具的默认归属范围。资产名 `heroine` 可在多个剧集出现，但 `asset_id` 全局唯一。
- **分集**及其运行任务通过已有 `project_id` / `episode_id` 外键归属到剧集。
- **资产版本**：每次 POST 同名资产创建新 `version` 和新 `asset_id`，不修改已使用的资产 ID；镜头可以绑定精确版本。
- **Story Bible**：每剧独立、追加版本，不直接原位覆盖。
- **跨剧复用**：当前不开放；未来经明确授权后实现克隆或只读共享，不通过同名自动共享。

## 向后兼容和旧数据库升级

- 旧的 `POST /api/v1/projects` 依然可用，未传 `column_id` 时归入 `col_default`（默认栏目）。
- `projects.id` 继续作为对外 `series_id` 使用；当前版本**不重命名 projects 表**，免得破坏已有 API / 外键。
- 打开旧 SQLite 时自动添加 `projects.column_id`、将旧项目归入默认栏目；数据库初始化可重复执行。
- 已存在的 `episodes` / `productions` 保留原有主键和关系；`series_assets` 与 `story_bibles` 为新表。
- 旧数据库上的 `column_id` 因 SQLite `ALTER TABLE` 约束而容许空值定义，但通过插入/更新触发器禁止未来写入空栏目。
- 数据仍在 SQLite；迁至 Turso 前要增加正式 SQL 迁移编号和备份策略。

## API 契约

| 方法 | 路径 | 说明 |
|---|---|---|
| POST / GET | `/api/v1/columns` | 创建/列出栏目 |
| POST / GET | `/api/v1/columns/{column_id}/series` | 创建/列出栏目下剧集 |
| GET | `/api/v1/series/{series_id}` | 查看剧集 |
| POST / GET | `/api/v1/series/{series_id}/assets` | 保存/列出当前剧集专属资产与版本 |
| POST / GET | `/api/v1/series/{series_id}/story-bibles` | 追加/列出剧情圣经版本 |
| POST / GET | `/api/v1/projects` | 旧项目接口兼容，GET 支持 `column_id` |
| POST | `/api/v1/projects/{project_id}/episodes` | 新增分集时校验每个镜头的演员、场景、参考资产均属于本剧 |
| GET | `/api/v1/productions` | 可选 `column_id`、`series_id` 过滤 |

**重要注意**：栏目/剧集作用域是数据完整性约束，不是租户级安全认证。目前 FastAPI 无身份认证，不能将内部 API 公开到互联网。配额、细粒度授权、并发 Worker 都是后续 M3/M5 阶段实现。

## 小说分支

小说上传 / 权益校验继续独立工作；后续 PR-04 在小说改编的审核通过阶段关联 `series_id`，写入指定剧集的 Story Bible 和分集，不自动混入某个栏目。未授权原文仍禁止发送到模型。

## 最小验收

1. 两个栏目可以各自拥有多个剧集；同一个栏目两部剧也有独立素材。
2. 两部剧都可以使用 `heroine` 这样的资产名，但不能互引对方的资产 ID。
3. `actor` 引用只能指向当前剧集的演员；`scene` 引用只能指向当前剧集的场景；Voice 绑定也只能在剧内进行。
4. 新资产保存为新版本，旧版本可以被历史分集稳定引用。
5. 打开已有 SQLite 数据库，不删除任何旧项目或分集。
6. 两剧任务可以分别创建、查询与审核；真正的并发视频执行尚未声称完成。
# PR-07b2｜原创分镜、剧本确认与制作审批（本机 UI）

## 真实改进

在既有 **「本机审片」** 功能之前，Streamlit 新增 **「分镜与审批」** 工作台。操作员可以：

1. 在当前栏目选择原创剧集，创建/选择 Story Bible（全剧设定）。
2. 从当前剧集已登记的演员/场景版本生成**待人工填写的** 1–12 镜草稿；每镜 1–30 秒，总长度最多 90 秒。每个镜头需要写真实动作、摄影方式、人物/道具连续性；可添加原始 `dialogue` 对白，必须遵守 `screenplay.zh.v1` 的角色与时槽规则。
3. 用既有 `POST /api/v1/series/{series_id}/screenplays/validate` 无副作用检查内容、镜头时长、Story Bible/场景/人物归属；将服务器成功返回的验证结果与当前草稿的**规范化 SHA256** 一并保存于当前 Streamlit session。草稿或剧集一旦变化，不能沿用旧的验证结果。
4. 亲自阅读审查并勾选 **人工确认** 后才调用既有 `/commit`，以不可原地覆盖的 Episode 版本保存；重复分集编号由服务端唯一约束拒绝，不能把仅校验成功当作审批。
5. 为选定 Episode 创建 Production。先查看完整保存的剧本、独立确认并调用 `approve-script`；再查看所引用的本剧角色/场景规格、独立确认并调用 `approve-characters`。只有两级都过，才能去「本机审片」渲染并播放带字幕的真正离线 MP4。

UI 所有创建与审批行为都使用**现有 FastAPI 路由**；没有新增绕过版权/状态机的服务端端点，也没有自动按顺序批准、多步自动提交或自动发行。

## 分镜草稿的性质

`frontend/workflow.py` 生成仅含草稿动作提示的**人工起点**，不自动创作或发送原著文本给第三方。ID 的基本格式先本机拦截，远端是否属于所选剧集仍由 `check_screenplay_scope` 实际验证。规范化 SHA256 的作用仅是防止本机用户在验证后修改文本却继续提交旧验证记录；**不是授权签名、身份认证或服务端发布许可**。

## 验收和持续限制

`tests/test_local_screenplay_wizard.py` 覆盖草稿生成、长度边界、重复 ID、非法场景/角色、跨剧集服务器拒绝、修改后验证作废、显式人工确认、重复 Episode 阻断，以及真正产生可播放 H.264/AAC/mov_text MP4 并从独立本机 QA 审片器通过。要求四项 CI 全绿。

仍是 `127.0.0.1` 开发用 Streamlit/API 原型，没有角色登录或公网权限。不允许外网公开。此页不制作真正人物影像、台词语音或商业发行许可证，没有供应商请求、付费模型、云数据库迁移和不可逆外部发布；原实验的一次性收费工作流保持锁定。

## 本机运行

安装 `pip install -e '.[frontend,render]'` 并安装本机 FFmpeg；两个终端运行 `drama-factory-api` 与 `streamlit run frontend/app.py --server.address 127.0.0.1`。让 Streamlit 与 API 共用 `DRAMA_FACTORY_DATA_DIR=./data`，离线预览默认存于 `./artifacts/offline-reviews`，或通过 `DRAMA_OFFLINE_RENDER_ROOT` 选择仅本机目录。依次打开「原创短剧」、「资产与生产任务」、「分镜与审批」、「本机审片」。不要误把占位 MP4 视为真实 AI 发行级成片。

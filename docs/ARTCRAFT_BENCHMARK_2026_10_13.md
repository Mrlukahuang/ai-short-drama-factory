# ArtCraft 对照研究与 AI 短剧工厂可借鉴路线（2026-10-13）

- 对象：[storytold/artcraft](https://github.com/storytold/artcraft)，GitHub Rust/Tauri + React/TypeScript 开源桌面 AI 图像/视频创作平台。
- 对照项目：[Mrlukahuang/ai-short-drama-factory](https://github.com/Mrlukahuang/ai-short-drama-factory)，Python/FastAPI/SQLite、离线 FFmpeg、私有 Google Drive 和独立 Turso 元数据映射的短剧生产后端。
- **研究范围**：公开 GitHub README/ROADMAP/AGENTS.md、许可证和下列**实际源码**；不代表 ArtCraft 产品完整压测、功能购买体验或实测模型计费。GitHub Star 数量是关注度，不是可靠性、质量或收入证明。
- **决策**：学习创作交互与组件适配边界；现有 Python 工作流、审核/预算/版权和云资产账本仍作为权威，不整体替换为 ArtCraft/Rust。

## 可复核源码证据

| 主题 | 代码/文档路径 | 确认的事实与边界 |
| --- | --- | --- |
| 产品定位 | [README](https://github.com/storytold/artcraft/blob/main/README.md) | 以艺术家 IDE 为核心，强调先构图、3D 摆位、人物姿态、相机，再生成；展示大量可视化 GIF/视频以及多模型目录。多模型表中标记 †/‡ 的部分模型处于禁用/受限状态，不可简单视为全部可实时调用。 |
| 实际技术架构 | [AGENTS.md](https://github.com/storytold/artcraft/blob/main/AGENTS.md)、[Cargo.toml](https://github.com/storytold/artcraft/blob/main/Cargo.toml) | 桌面主程序为 Tauri + Rust、React/Vite/Zustand/Three.js；另有纯 Rust egui 实验/原生应用。后端服务、网站和公司内部工具**在独立 artcraft-services 仓库**，不能将此公开桌面仓库当作完全自托管生成平台。 |
| 分镜原型 | [StoryboardStore.ts](https://github.com/storytold/artcraft/blob/main/frontend/apps/artcraft/app/src/pages/PageStoryboard/StoryboardStore.ts)、[Storyboard.tsx](https://github.com/storytold/artcraft/blob/main/frontend/apps/artcraft/app/src/pages/PageStoryboard/Storyboard.tsx) | Board 包含 shotNumber、图片、对白、动作、导演备注和 duration；支持新增、删除、选择、重排序号；编辑页提供镜头预览、绘制、上传、时间轴。其 Store 是 Zustand 内存状态，**单独看不到持久多端分镜权威存储**，不宜直接当我们的生产数据库。 |
| 3D 场景编辑 | [PageScene.tsx](https://github.com/storytold/artcraft/blob/main/frontend/apps/artcraft/app/src/pages/PageScene/PageScene.tsx)、[pagescene Stage3D](https://github.com/storytold/artcraft/tree/main/frontend/libs/components/pagescene/src/lib) | Stage3D 包装为可注入宿主适配器的组件，有独立场景序列化回调、摄像机、变换、场景树、撤销等部件；基于 Three.js。桌面端 scene/save 的宿主接口见 `useTauriPageSceneAdapter.tsx`。 |
| 实际网络依赖 | [useTauriPageSceneAdapter.tsx](https://github.com/storytold/artcraft/blob/main/frontend/apps/artcraft/app/src/pages/PageScene/useTauriPageSceneAdapter.tsx) | save/load/素材查询/生成请求调用 ArtCraft 的 host/API/media/CDN，独立 3D 编辑 UI 不能自动替代我们现有 Drive/Turso/Provider。值得借鉴的是 **Adapter 接口与场景序列化**，不是绑定它的云端服务。 |
| 视觉参考板 | [moodboard src/index.ts](https://github.com/storytold/artcraft/blob/main/frontend/libs/components/moodboard/src/index.ts) | 将 Grid/自由布局/演示、Board 数据结构、拖入素材、序列化和持久化 Adapter 区分。与我们的角色/服装/场景版本化审片契约契合。 |
| 时间线编辑器 | [video-editor src/index.ts](https://github.com/storytold/artcraft/blob/main/frontend/libs/components/video-editor/src/index.ts)、[宿主页面](https://github.com/storytold/artcraft/blob/main/frontend/apps/artcraft/app/src/pages/PageVideoEditor/index.tsx) | 拆分 ProjectStorage/MediaSource/AssetGallery/ExportSink/Authorization Adapter；把拖动、缩放、关键帧、时间线时间单位封装在独立组件/控制器中。页面宿主可插入不同的存储/导出目标。 |
| 相机角度编辑 | [Angles.tsx](https://github.com/storytold/artcraft/blob/main/frontend/apps/artcraft/app/src/pages/PageAngles/Angles.tsx) | 有旋转/倾斜/缩放参数与生成历史、模型选择及预估 Credits 显示；镜头角度调节与模型调用分离。 |
| 任务持久化 | [SQLite SQLx](https://github.com/storytold/artcraft/tree/main/crates/schema/database/sqlite_tasks/src/queries) | 本地已有生成任务表、provider task ID 与状态查询；不是我们需要的三层预算/提交意图安全设计的证据，也不证明可取代 Python/Turso。 |
| 权利边界 | [MIT](https://github.com/storytold/artcraft/blob/main/LICENSE-MIT)、[Apache-2.0](https://github.com/storytold/artcraft/blob/main/LICENSE-APACHE)、[NOTICE](https://github.com/storytold/artcraft/blob/main/NOTICE) | 双许可适用于项目自己有权授权的源码，但 ArtCraft 名称/商标不授权；NOTICE 明确列出游戏音效、贴图、动图/部分动作数据等**不适用该双许可**的第三方资产。不可直接复制其品牌或全量素材目录。 |

## 两个项目的互补定位

**ArtCraft 的明显优势**：可立即看到的图形创作界面，3D 角色/镜头、画布、编辑器、多模型选择、素材库与可回看的生成历史。GitHub README 的 GIF/视频让人不用读源码也明白“能做什么”。

**我们已建立的后端优势**：Column → Series → Episode → Shot Job 的数据归属与审核、小说版权门禁、已确认供应商调用意图与幂等字段、栏目/剧集/Provider 三级预算、FFmpeg 真 MP4、Drive 双向 SHA-256、Turso 单条元数据回执真云端验收（PR-30b/30c）。**这些不能靠把 ArtCraft UI 嵌进来替代**；本地生产 SQLite → Turso 迁移仍在 PR-31 安全演练阶段。

真正的产品缺口不是缺少更多模型按钮，而是用户在**制作前**无法方便地看到镜头、摆演员与相机、复用场景、逐镜头修订、审片与决定是否付费。

## 借鉴优先顺序（建议独立 PR，不在本次研究中直接实施）

| 顺位 | 我们应实现的功能 | 建议范围 | 风险和验收 |
| --- | --- | --- | --- |
| P0 / VIS-01 | **只读的分镜卡片/时间轴**：镜头序号、时长、对白、角色/场景 ID、参考图、审核状态、已生成视频预览；读取现有 Episode/Shot Job/Drive 的可靠数据，不能用浏览器临时状态充当权威 | 先单集、离线 Streamlit 或独立前端 Viewer；如需修改，走现有审核提交接口 | 测试跨 Series 隔离、引用版本、时间轴总时长、缺失资源降级，默认不付费 |
| P0 / VIS-02 | **场景与相机的可复用 JSON 契约**：camera position/rotation/focal length、角色/道具 transform、构图和参考图版本锁、shot_id、scene_version、时间轴关键帧 | 单独定义不可绕过审核的 typed schema + 本地序列化/反序列化验证；场景有稳定 ID 与版本，先不增加真实生成 | Roundtrip 保真、镜头归属和 asset 引用校验；避免更换场景却静默复用旧缓存 |
| P1 / VIS-03 | **Godot 作为可视化导演工作台**，保留 Streamlit 只读总览，通过显式「在 Godot 编辑」打开特定 scene/shot，保存后返回 JSON + 参考帧给 Python 审核 | **借鉴** Stage3D 的 Adapter 设计，不强行把基于 Three.js 的 ArtCraft WebView 移植到 Godot，也不直接绑定 ArtCraft 后端 | 明确 Godot 可编辑权限/本地文件交接，参考帧/源资产校验；需实测 Godot 操作与 Mac 交互性能 |
| P1 / VIS-04 | **审片与素材 Moodboard**：角色一致性参考、服装/场景材质、带来源/版权许可的图像、一次性冻结进具体镜头 | 优先读现有 `asset_references`、`series_assets`、`stored_artifacts`；不复制 ArtCraft 的第三方资源 | 验收素材许可、Series scope、版本锁和引用失效提示 |
| P1 / VIS-05 | **可见的生成预估与历史**：用户在“生成这个镜头”前看到 Provider、模型、最大确认费用、已预留额度、当前任务状态及失败恢复而非一次性批量生成 | 接现有预算/任务账本的只读视图，后续收费生成接口仍需独立授权和可靠提交意图 | 防止前端绕过预算/人工审核，区分预估价、预留价、真实账单 |
| P2 / VIS-06 | **剪辑时间线升级**：拖动、播放头、转场、文本/配音、导出 | MVP 继续用现有 FFmpeg，按需求再评估移植适配层、独立编辑器或 Remotion | 不宜早期引入整个 Tauri/React/TypeScript/Rust 依赖树；须实测时间线性能 |
| P2 / LAUNCH-01 | **可复现 Demo + 视频/图片 README**：一个原创 60 秒剧情 Demo、明确镜头前后对比、动画/文档、简单安装与真实能力边界 | 无付费调用的技术 Demo + 单独许可的可公开视频；公开项目或发布内容前另行批准 | 关注度增长的原因不能只归于 README，但可视化展示有利于让用户理解产品价值 |

## 不建议照搬

1. **不要为追 Star 一口气支持几十个模型**。ArtCraft README 多模型目录中有禁用/受限标签；我们的产品应该先做到镜头一致性、审核、可靠可重复生成，再扩展 Provider。
2. **不要直接换成 Rust/Tauri 或替代 Python/Turso 账本**。我们的差异化在自动短剧流水线；替换引擎会把并发/预算/版权/云存储的已建门禁推翻，投入大、短期无收益。
3. **不要直接依赖 ArtCraft 后端服务或复制其云 API/账号系统**。其后台在独立仓库且真实访问需要 ArtCraft 自己的服务/认证；若要复用组件须评估其内部包依赖和本地可运行性。
4. **不要复制 NOTICE 标记的第三方资产、品牌、音效、角色**；借鉴结构及个别明确许可源码，保留 attribution，自己制作可商用原创素材。
5. **不要把分镜 Zustand 内存 Store 当作持久生产账本**。任何正式镜头变更必须经我们已定义的 schema、审核与版本/哈希校验。

## 关于 Star 快速增长的解释边界

公开 GitHub API 于 2026-10-13 查询约 **21,305 Star、3,459 Fork**。第三方趋势页 [Trendshift](https://trendshift.io/repositories/19042) 记录 2026-08-13 至 2026-10-12 期间约 **+16,706 Star**；来源采集时间及增长窗口与 GitHub 实时快照不同，不能将两者相减计算日增。README 的视频演示、清晰“艺术家 IDE”定位、跨 Mac/Windows 发行、Discord/YouTube 社区等都可能帮助传播，**不能仅凭 Star 证明产品留存、视频质量或商业收入**。

**推荐方向**：保留我们已验证的生产后端，加一层“导演可视化工作台”。第一项优先是 **VIS-01 分镜 Viewer + VIS-02 场景 JSON 契约**，比直接引进 ArtCraft 全栈更匹配短剧工厂目标。

# 当前交接状态（2026-10-18 NZT）

## 当前阶段与方向

G4 MVP / R4.1，未进入G5。所有者本轮明确「基于 GPT」推进；Sol作为临时开发基线，正式主备选型未定。Gemini HTTP400单独排查，不阻塞GPT主线。本轮零新增收费调用、零视频生成、未新增密钥。

## 最新交付：视频请求准备

- #153已合并5d88967，6项CI全绿；真实Sol响应已在独立SQLite测试项目完成导入、拒绝未审提交、测试批准建档，1剧集/0production/0新增调用。不是正式生产资产。
- 本次补build_screenplay_video_plan纯离线转换：12镜或连续子集，不调用F3旧六镜故事、不混用预设旧服装，不授予付费权限。
- 真实Sol12镜60秒输出估算USD2.02755；按10秒/镜场景USD4.05510。首3镜目标15秒估算USD0.5068875；10秒/镜场景USD1.013775。均不含输入等，非账单、非完整预算。
- 360p每秒成本为仓库旧快照，本次官方价格页只明确720p换算，未独立重证360p token换算；total_budget_verified=false，执行仍禁止。
- 109项相关离线测试通过；两份真实计划已准备，无新增收费调用/视频。详见docs/SCREENPLAY_VIDEO_PLAN.md。
- 下一步：准备首3镜独立测试的完整输入/思考费用边界、外观/道具版本和执行入口；先不放行整集，不复用已消费F3或first3 claim。

## 已交付：GPT待审入口

- 新增离线GPT响应导入：POST /api/v1/series/{series_id}/screenplays/from-openai-response/validate，Sol默认、兼容Luna。
- 使用当前系列Bible及资产校验输出，返回Screenplay和EpisodeDraft待审预览；不写DB、不自动批准、不创建production。
- 人工修改后复用既有validate/commit；明确reviewed_by_operator=true才创建剧集草稿，后续生产审批仍独立。
- 导入来源是operator_supplied；不宣称响应真实性或原请求绑定已获验证。缓存写入计费尚待修正，因此此入口费用返回null，保留token信息。
- 本地96项相关测试通过，涵盖SQLite+FastAPI真实人工门禁、跨系列/缺资产拒绝、截断/拒绝/model不符等。
- 重用Run39035812309的真实响应做离线回放：Sol12镜60秒、Luna8镜60秒均可转待审预览；未生成新稿，未评定创作质量。比较fixture IDs不自动改写成真实项目ID。
- 详见docs/GPT_SCREENPLAY_REVIEW.md。

## 既有证据与边界

- main基线8bdf0f0，#152已合并，六项CI全绿；已补Google白名单status/field诊断，但旧400正文丢失，根因仍未知，不能称Gemini已修复。端点与官方及既有视频Interactions接口一致。
- Run39035812309：Sol/Luna真实生成通过结构校验，Flash400；artifact12102675304。原first3 claim已消耗，禁止整批重跑，剩余15未放行。
- 原report估算USD0.0534832漏缓存写入差额；两份GPT补算目录价估算USD0.0540418，非实际账单。新导入入口不传播旧费用估算。
- TokenUpperBound.verified是外部可信证据断言，不是模块验证或账单封顶。Google输出含思考cap有文档依据，完整18任务仍须独立执行前检查。
- F3视频Run38931439653原型已接受、不返工；#137实际账单待核，US$1.75896721仅视频输出估算；一次性授权已使用，不重跑。

## 下一步

GPT待审接线#153已合并；选定真实项目Bible和演员场景资产后形成并人工审核该项目剧本。新文本生成必须另走已审预算/授权路径；本次没有增加付费生成入口。G4退出、商业发布、中文对白/字幕验收均未完成。

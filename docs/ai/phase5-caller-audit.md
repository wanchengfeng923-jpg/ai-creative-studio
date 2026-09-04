# Phase 5 旧路径 caller 审计

审计基线：2026-09-04，源码目录 `src/creative_studio`，测试目录 `tests`。生产分类只统计
`StudioApplication` 默认 composition root 可到达的调用；测试和历史导入不等同于生产 caller。

| 旧项 | production | test | history/import | dead/结论 |
|---|---|---|---|---|
| `LegacyCreativeGenerationAdapter` | 0（不再由服务默认构造，仅显式兼容测试可注入） | `tests/test_generation_service.py` 元数据与兼容回归 | 旧视觉/轮播兼容输入 | 保留；三个替代 Module 均稳定且保留期结束后删除 |
| `VisualRecommendationSchema` | 0（active Module 使用 typed contract validator） | `tests/test_schemas.py` 直接校验旧形状 | 旧视觉/轮播历史读取仍可能依赖 | 保留；迁移历史读取并完成回归后删除 |
| `load_ai_visual_first_frame_prompt()` | 0；Phase 5 已移除 loader | 无运行时调用 | retired registry inventory 保留提示词文件 | 代码已删除；提示词文件待保留期/registry 清理时处理 |
| `load_ai_visual_follow_up_prompt()` | 0；Phase 5 已移除 loader | 无运行时调用 | retired registry inventory 保留提示词文件 | 代码已删除；提示词文件待保留期/registry 清理时处理 |
| `complete_visual_generation()` | 0；轮播 service 使用 `RunStorePort.complete_run()` | repository/image/API 回归直接调用 | 旧视觉/轮播持久化兼容 | 保留为历史测试/读取兼容；迁移历史并完成保留期后删除 |

审计约束由 `tests/test_phase5_governance.py` 锁定：retired loader 不得出现运行时调用，registry
production caller 必须恰好是 `narrative`、`static`、`carousel` 各一个。该审计不授权删除仍有兼容或
历史读取用途的代码。

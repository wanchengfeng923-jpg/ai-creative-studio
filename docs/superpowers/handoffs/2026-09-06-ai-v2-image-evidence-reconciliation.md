# AI v2 图片证据核对

日期：2026-09-06

## 结论

`.scratch/ai-v2-real-image-eval/` 不是单次实验的不可变输出目录。至少存在两套写报告路径：

- `finalize_unknown_report.py`：在静态 provider unknown 后写入 `status=not_exercised`、静态提交 1、轮播提交 0。
- `run_image_eval.py`：正常完成时按 transport 计数写入静态/轮播报告；异常时也会覆盖两份报告。

因此当前目录中的 `static-real-image-report.json` 和 `carousel-real-image-report.json` 不能单独证明一次完整实验。特别是静态报告的提交数与 unknown 交接一致，而报告字段又包含另一轮成功运行的结构；轮播报告的提交数 0 与成功帧字段也互相冲突。

## 处理决定

- 不修改或删除现有 scratch 文件，保留其作为历史调试证据。
- 不把当前 JSON 描述为 static/carousel 完整成功，也不把它描述为唯一 unknown 结果；最终状态为 `evidence_conflicted`。
- 下一次真实图片评测必须使用新的不可复用目录，并在启动前写入 run manifest：run id、模型、最大提交数、临时数据库/图片/job 目录、停止条件和报告路径。
- 每次实验只允许写自己的报告；unknown 终止时不得覆盖先前 run 的报告。
- 重新评测仍须使用 launcher 的代理桥，按 static -> carousel 顺序，最多 3 次供应商提交；认证失败、连续 unknown 或超预算立即停止。

## 2026-09-06 隔离重测结果

- 新 run：`.scratch/ai-v2-real-image-eval-20260906/`；模型 `gpt-5-6-mini`；文字调用 0；供应商提交总数 3（static 1、carousel 2）。
- Static：成功，1 session、1 attempt、1 artifact、PNG；重复点击复用 attempt，未重复提交。
- Carousel：先请求第 2 帧得到 `frame_order_conflict`；第 1/2 帧成功，共用 1 session、revision=2；第 2 帧携带参考图和 cursor；重复请求幂等。
- 两类公开 DTO 私有字段泄露数均为 0；8791 网关和 7896 relay 已停止，无监听残留。
- 评测脚本发现并修正累计提交数写入错误：旧报告静态写 3/轮播写 0，实际提交为静态 1/轮播 2；本 run 报告已按 transport submission metadata 更正。

## 当前可采信证据

- deterministic static/carousel 测试和 AI v2 contract gate：可重复、通过。
- 真实图片链路：以上隔离 run 可采信为受控图片状态机证据；不构成 production Prompt 或模型质量批准。
- Prompt、caller、live 和正式发布：仍未批准。

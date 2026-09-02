# 创意类提示词工程：权威一手资料与社区实践

- 研究日期：2026-09-02
- 范围：文本/图像创意提示词、提示词评估、agent/workflow 提示词
- 原则：优先官方文档、源码、课程与原始社区项目；二手转述只作补充

## 一句话结论

创意类提示词正在从“写得更像魔法咒语”转向“写成可测试的规格”：先把角色、边界、输出合同、示例和评估集定下来，再迭代提示词本身。

## 一手来源共识

| 来源 | 日期 | 关键结论 |
| --- | --- | --- |
| [OpenAI Prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering) | 无明确日期，访问于 2026-09-02 | GPT 系列更吃“精确指令”和清晰约束；少量高质量示例有效；重复可复用内容放在前面有助于缓存。 |
| [OpenAI Reasoning best practices](https://developers.openai.com/api/docs/guides/reasoning-best-practices) | 无明确日期，访问于 2026-09-02 | 推理模型更适合直接、简洁的提示；“think step by step”不一定更好；先零样本，再按需少样本。 |
| [OpenAI GPT-4.1 Prompting Guide](https://developers.openai.com/cookbook/examples/gpt4-1_prompting_guide) | 2025-04-14 | 更强调清晰、具体、带上下文的指令；可用显式规划提示提升 agent 型任务表现。 |
| [Anthropic Prompting best practices](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices) | 无明确日期，访问于 2026-09-02 | 推荐 3-5 个相关且多样的示例、XML 分隔、角色提示、长上下文时把长文放前面，并要求先引用关键片段。 |
| [Anthropic Define success criteria and build evaluations](https://docs.anthropic.com/en/docs/build-with-claude/develop-tests) | 无明确日期，访问于 2026-09-02 | 先定义可测成功标准，再做 eval；prompt engineering 不应脱离测试。 |
| [Google Prompt design strategies](https://ai.google.dev/gemini-api/docs/prompting-strategies) | 2026-06-10（页面展示日期） | 提示工程是迭代式的；模板只是起点，要根据实际响应不断修正。 |
| [Microsoft Prompt engineering techniques](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/prompt-engineering) | 2026-05-13 | 要具体、描述性强、重复关键指令时机要对，且顺序会影响结果；要给模型“退出口”。 |
| [Microsoft System message design](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/advanced-prompt-engineering) | 2026-05-13 | system message 应明确角色、边界、输出格式、when unsure 策略；但仍需测试与迭代。 |
| [Microsoft Image prompt engineering techniques](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/gpt-4-v-prompt-engineering) | 2026-07-29 | 图像/视觉提示同样适用：加上下文、明确任务、给示例、拆分复杂请求、定义输出格式。 |
| [OpenAI DALL·E 3](https://openai.com/index/dall-e-3/) | 2023-10-31 | 更详细的自然语言描述能直接提高图像贴合度；ChatGPT 可先把创意想法扩成更细的提示词。 |
| [DeepLearning.AI ChatGPT Prompt Engineering for Developers](https://www.deeplearning.ai/courses/chatgpt-prompt-eng) | 2023-05-03（课程公告） | 把 prompt engineering 作为开发技能来教，覆盖总结、推断、转换、扩写等典型任务。 |

## 社区实践信号

| 来源 | 证据 |
| --- | --- |
| [Promptfoo docs](https://www.promptfoo.dev/docs/intro/) | 明确主张“test-driven prompt engineering”优于试错。 |
| [Promptfoo GitHub repo](https://github.com/promptfoo/promptfoo) | 支持自动评估、red teaming、CI/CD 检查和 PR 扫描。 |
| [DSPy docs](https://dspy.ai/) / [GitHub](https://github.com/stanfordnlp/dspy) | 核心立场是“program, don’t prompt”；用结构化 signature 和优化器管理 prompts/weights。 |
| [r/MachineLearning thread](https://www.reddit.com/r/MachineLearning/comments/1ez60wf/d_robustnessreliability_issues_in_llms/) | 社区讨论也在强调：RAG/提示词优化都要配系统化 eval，Promptfoo 常被拿来做回归测试。 |

## 对创意提示词的可执行结论

1. 先写规格，再写文案：角色、受众、风格、边界、输出格式、拒答条件先定死。
2. 把“灵感”拆成结构：指令、上下文、示例、负例、输出模板分开写。
3. 示例比形容词更有用：少量高质量、覆盖边界的 few-shot 往往比长篇形容更稳。
4. 创意图像提示词要加任务语境：用途、镜头/构图、材质、情绪、输出尺寸/格式都要明确。
5. 每次改 prompt 都要跑固定 eval 集；没有回归测试的 prompt 只是在碰运气。
6. 面向 reasoning models 时，保持短、直、明确；别默认“多写一步”一定更好。

## 备注

- 上面凡是没有明确发布日期的官方文档，都按“无明确日期，访问于 2026-09-02”处理。
- 社区项只作为实践信号，不替代一手规范。

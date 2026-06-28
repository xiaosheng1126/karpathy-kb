---
schema_version: "1"
status: draft
tags: [tts, voice-cloning, self-media, decision]
sources: []
created_at: 2026-06-24
updated_at: 2026-06-24
last_verified_at: 2026-06-24
valid_until: 2026-12
---

# 本机 TTS 方案对比

## 结论

**当前默认组合（2026-06，macOS Apple Silicon）**：

- **零样本声音克隆 + 多语种**：GPT-SoVITS（刚 star，MIT，已支持 Apple Silicon）
- **一键 GUI、不想折腾**：voice-pro（已 star，封装多模型 + Whisper + Demucs）
- **桌面应用、本地全栈**：OmniVoice-Studio（已 star，作为 ElevenLabs 替代）
- **国产高质量、纯中英**：VoxCPM（已 star，OpenBMB 自家模型）
- ❌ **不选**：IndexTTS（需 NVIDIA + CUDA 12.8，本机不可用）

如果只想跑通一次：先 voice-pro，因为它把模型选择成本降到最低。
如果要做内容生产管线：直接用 GPT-SoVITS 命令行，可脚本化。

## 适用场景

- 短视频配音、播客（中文为主，偶尔英文）
- 公众号文章朗读
- 个人项目里需要语音输出（TTS bot、提醒）
- 短时间样本克隆某个人声（5-30 秒）

不适用：

- 商业级多说话人客服（建议直接买 ElevenLabs / 火山）
- 需要实时低延迟的对话场景（本地模型延迟仍高）

## 判断依据

**判断**：本机 TTS 在 2026-06 已经达到"可用"水平，但没有"通吃赢家"。
- 置信度：high
- 有效期：2026-12
- 来源：[待补 raw]
- 不确定性：质量评估主观，需要听感对比

**判断**：GPT-SoVITS 是当前开源 TTS 的事实标准，多数其他工具内部都集成它。
- 置信度：high
- 有效期：2026-12
- 来源：voice-pro README 明确集成 GPT-SoVITS
- 不确定性：CosyVoice 在中文上可能更好，需自测

**判断**：voice-pro 适合"不想读论文、要快速出结果"的场景。
- 置信度：medium
- 有效期：2026-09
- 来源：[已 star，未深度使用]
- 不确定性：尚未上手；GUI 类项目可能掩盖底层模型差异

**判断**：OmniVoice-Studio 定位是 ElevenLabs 替代，桌面应用优先；功能比 voice-pro 重，启动成本更高。
- 置信度：medium
- 有效期：2026-09
- 来源：[已 star，未深度使用]
- 不确定性：未自测；功能宣传与实际可用度可能有差距

**判断**：VoxCPM 是模型层项目（不是应用），适合作为下游集成的备选模型。
- 置信度：medium
- 有效期：2026-09
- 来源：[已 star，OpenBMB 自家模型]
- 不确定性：是否在 Apple Silicon 上能跑、性能如何，需自测

**判断**：IndexTTS 在 macOS 不可用（需 NVIDIA CUDA）。
- 置信度：high
- 有效期：2027-06
- 来源：项目 README 明确硬件要求
- 不确定性：未来若出 ROCm / MLX 版本可重新评估

**判断**：商业 API（ElevenLabs / 火山 / 微软）在质量和稳定性上仍优于本地，按月计费成本通常 < 时间成本。
- 置信度：medium
- 有效期：2026-12
- 来源：行业共识
- 不确定性：本地模型迭代非常快，6 个月内可能反超

## 方法或流程

### 选型决策树

```
TTS 任务输入
  ├─ 是商业 / 高频 / 实时？
  │    └─ 是 → 用 ElevenLabs / 火山 等商业 API（不要硬刚本地）
  │
  ├─ 是个人项目 / 偶尔用 / 注重隐私？
  │    ├─ 想最快出声 → voice-pro GUI
  │    ├─ 想脚本化进 pipeline → GPT-SoVITS CLI
  │    └─ 想要桌面级体验 → OmniVoice-Studio
  │
  ├─ 需要克隆某个特定人声？
  │    ├─ 有 5-30 秒清晰样本 → GPT-SoVITS 零样本
  │    └─ 有 1+ 分钟样本 → GPT-SoVITS 微调
  │
  └─ 需要纯中英、追求自然韵律？
       └─ VoxCPM 试一次（可能比 GPT-SoVITS 中文更好）
```

### 评估新 TTS 工具的清单

收到推荐时按这 5 个问题筛选：

1. **硬件门槛**：Apple Silicon 能不能跑？需要多少显存？
2. **样本要求**：零样本还是必须微调？最少多少秒？
3. **语种**：中文支持质量？是不是只挂着支持但效果差？
4. **可脚本化**：能不能用 CLI 进 pipeline，不是只 GUI？
5. **许可证**：MIT/Apache vs GPL/CC-NC，能不能商用？

3 个不确定就先观察。

### 已淘汰 / 不再投入

- ~~**IndexTTS**~~（已观察，未 star）
  - 决策：硬件不兼容（需 NVIDIA + CUDA 12.8）
  - 时间：2026-06
  - 复活条件：出 MLX / Apple Silicon 版本

### 复活检查（重新评估的触发条件）

- voice-pro / OmniVoice-Studio 实测后发现质量明显劣于商业方案 → 重新评估"是否还坚持本地"
- 出现一个被多家集成的新模型（类似当年 GPT-SoVITS 取代 VITS）
- macOS 上有原生 TTS 模型（Apple 自家或 MLX 社区）质量过线
- 实际使用频次极低 → 简化决策，只留一个

## 限制

- 当前结论基于个人开发场景，未考虑团队 / 商业级 SLA
- 仅评估**本地可跑**的开源 TTS；商业 API 单独对比另写
- 缺少自测听感数据；多数判断置信度 medium，需后续实战补强
- 中文质量主观性强，不同场景（朗读 / 配音 / 对话）适配模型可能不同
- 模型迭代快，半年后这篇大概率需要重写

## 来源

- GitHub stars：
  - https://github.com/RVC-Boss/GPT-SoVITS
  - https://github.com/abus-aikorea/voice-pro
  - https://github.com/debpalash/OmniVoice-Studio
  - https://github.com/OpenBMB/VoxCPM
  - https://github.com/index-tts/index-tts （未 star，已淘汰）
- raw：[待沉淀]
  - 计划：实测 GPT-SoVITS 中文克隆，产出 1 篇 raw + 听感样本
  - 计划：voice-pro 与 OmniVoice-Studio 工作流对比，产出 1 篇 raw
- profile.md：当前主线包含自媒体 / 影视自建
- radar：`reports/stars_profile_2026-06-24.md`

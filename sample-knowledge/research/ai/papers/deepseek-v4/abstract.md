---
type: concept
description: "Preview of DeepSeek-V4 series featuring Mixture-of-Experts architectures optimized for million-token contexts"
topics: [llm, moe]
---

# Abstract — DeepSeek-V4 Preview

DeepSeek-V4 continues the MoE lineage of its predecessors but with significant architectural innovations enabling **million-token context windows**:

- **DeepSeekMoE architecture** — fine-grained expert segmentation combined with shared expert isolation, balancing model capacity and computational cost
- **Multi-token prediction (MTP)** — training objective that predicts multiple future tokens simultaneously, improving sample efficiency and inference speed
- **Long-context optimization** — attention mechanisms and positional encodings designed for sequences of 1M+ tokens

The Pro and Flash variants target different deployment scenarios — Pro for research and high-accuracy tasks, Flash for edge deployment and real-time applications.
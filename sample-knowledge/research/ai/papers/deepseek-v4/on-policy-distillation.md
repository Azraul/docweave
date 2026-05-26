---
type: concept
description: "On-policy distillation technique used to transfer knowledge from the larger Pro model to the smaller Flash model"
topics: [llm, distillation]
---

# On-Policy Distillation

Standard knowledge distillation trains a student model on **static** outputs from a teacher. On-policy distillation differs by training the student on **its own generated sequences** — correcting the distribution mismatch between training and inference.

The approach:

1. Generate text from the **student** (Flash model)
2. Score those generations using the **teacher** (Pro model) — what would Pro have output?
3. Train the student to match the teacher's distribution on the student's own outputs

This is particularly effective for MoE architectures where the routing decisions of the student and teacher can differ significantly. By training on student-generated sequences, the distillation aligns with the actual inference-time behavior, leading to better quality at a fraction of the compute cost.

The teacher model (Pro) itself builds on the [[research/ai/papers/attention-is-all-you-need/_index|Transformer]] architecture — making this an example of distilling a transformer-based MoE into a smaller one.
---
type: concept
description: "Residual learning framework that reformulates layers as learning residual functions with reference to layer inputs"
topics: [deep-learning, architecture]
---

# Abstract — Deep Residual Learning

The key insight: instead of learning an unreferenced mapping `H(x)`, let the stacked layers learn a **residual mapping** `F(x) = H(x) - x`. The original mapping becomes `F(x) + x`.

This reformulation makes deep networks easier to optimize. Why? Because if an identity mapping is optimal, the layers can simply push the residuals toward zero — far easier than learning the identity from scratch through multiple nonlinear layers.

Empirical result: a plain 56-layer network has higher training error than a 20-layer network (the degradation problem). With residual connections, the 56-layer network outperforms the 20-layer version.
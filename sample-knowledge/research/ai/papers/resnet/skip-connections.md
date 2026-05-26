---
type: concept
description: "Identity shortcuts that skip one or more layers, solving the vanishing gradient problem in deep networks"
topics: [deep-learning, architecture]
---

# Skip Connections

A skip connection (or shortcut connection) adds the input of a layer or block directly to its output, bypassing the intermediate transformations:

```python
def residual_block(x):
    # Two or more weight layers
    F = relu(W2 @ relu(W1 @ x + b1) + b2)
    # Add the input (identity shortcut)
    return relu(F + x)
```

This serves two critical purposes:

1. **Gradient flow** — gradients can bypass the nonlinear layers during backpropagation, mitigating the vanishing gradient problem
2. **Identity bias** — if the layer doesn't improve the representation, the network can simply set the weights near zero and pass the input through unchanged

Skip connections are now ubiquitous — not just in ResNet, but in [[research/ai/papers/attention-is-all-you-need/_index|Transformers]] (residual connections around each sub-layer), diffusion models (UNet skip connections), and essentially every modern deep architecture.
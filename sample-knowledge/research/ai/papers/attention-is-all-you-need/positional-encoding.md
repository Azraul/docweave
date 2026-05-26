---
type: concept
description: "Sinusoidal position encodings that give the Transformer awareness of token order without recurrence"
topics: [transformers, architecture]
---

# Positional Encoding

Because the Transformer has no recurrence or convolution, it needs a way to represent the **order of tokens**. The solution: add a positional encoding vector to each input embedding.

The original paper used **sinusoidal encodings**:

```python
PE(pos, 2i)   = sin(pos / 10000^(2i/d_model))
PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))
```

Why sinusoids? They allow the model to easily learn to attend by relative position, since `PE(pos+k)` can be represented as a linear function of `PE(pos)`. This also enables the model to generalize to sequence lengths longer than those seen during training — a practical advantage over learned position embeddings.

Later work (like RoPE in Llama 3) improved on this, but the sinusoidal encoding remains an elegant solution that works remarkably well.
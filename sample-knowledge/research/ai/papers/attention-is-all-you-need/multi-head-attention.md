---
type: concept
description: "Parallel attention layers that let the model jointly attend to information from different representation subspaces"
topics: [transformers, attention]
---

# Multi-Head Attention

Instead of computing a single attention function, the Transformer uses **multiple parallel attention heads**. Each head operates on a different learned linear projection of the queries, keys, and values.

```python
# Simplified: multi-head attention
def multi_head_attention(Q, K, V, num_heads=8):
    heads = []
    for i in range(num_heads):
        # Project Q, K, V through learned weight matrices
        Q_i = linear(Q, W_Q_i)
        K_i = linear(K, W_K_i)
        V_i = linear(V, W_V_i)
        # Compute scaled dot-product attention
        head = softmax(Q_i @ K_i.T / sqrt(d_k)) @ V_i
        heads.append(head)
    # Concatenate and project
    return linear(concat(heads), W_O)
```

Each head may learn different relationship types — syntactic structure, coreference, semantic similarity. The concatenated output is projected back to the model dimension, giving the model a richer representation than any single attention function could provide.
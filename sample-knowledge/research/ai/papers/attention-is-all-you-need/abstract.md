---
type: concept
description: "A novel architecture based solely on attention mechanisms, dispensing with recurrence and convolutions entirely"
topics: [transformers, architecture]
---

# Abstract — Attention Is All You Need

The Transformer is a sequence-to-sequence model built entirely on **self-attention** and **feed-forward layers**. It removes the recurrence found in LSTMs and GRUs, enabling:

- **Parallelization** — all tokens attend to each other simultaneously, making training significantly faster than RNNs
- **Long-range dependencies** — each token can directly attend to any other token, avoiding the vanishing gradient problem of recurrent models
- **Simpler architecture** — fewer inductive biases, letting the model learn positional relationships from data

The model uses an encoder-decoder structure where both encoder and decoder are stacks of identical layers, each containing multi-head self-attention and position-wise feed-forward networks.
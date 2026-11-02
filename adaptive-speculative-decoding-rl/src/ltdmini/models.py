"""Load a target/draft pair and check they share a tokenizer.

Special ids (no download, used by tests and the smoke pipeline):
    "random-tiny"        a small random Llama-style target model
    "random-tiny-draft"  a smaller model whose weights are a noisy copy of the target's
                         first layers, so acceptance rates are non-trivial
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import torch

from .device import pick_device, pick_dtype

TINY_VOCAB = 512


class ByteTokenizer:
    """Minimal tokenizer for random-tiny models: UTF-8 bytes + offset, ids < TINY_VOCAB."""
    eos_token_id = 1
    name_or_path = "byte-tokenizer"

    def __init__(self):
        self.vocab_size = TINY_VOCAB

    def encode(self, text: str) -> list[int]:
        return [2] + [b + 3 for b in text.encode("utf-8")][: 400]

    def decode(self, ids) -> str:
        return bytes([max(0, min(255, i - 3)) for i in ids if i >= 3]).decode("utf-8", errors="replace")

    def get_vocab(self) -> dict[str, int]:
        return {str(i): i for i in range(TINY_VOCAB)}


def _tiny_model(seed: int, layers: int, hidden: int, heads: int):
    from transformers import LlamaConfig, LlamaForCausalLM
    torch.manual_seed(seed)
    cfg = LlamaConfig(vocab_size=TINY_VOCAB, hidden_size=hidden, intermediate_size=hidden * 2,
                      num_hidden_layers=layers, num_attention_heads=heads, num_key_value_heads=heads,
                      max_position_embeddings=2048, tie_word_embeddings=False)
    return LlamaForCausalLM(cfg)


def make_tiny_pair(noise: float = 0.02):
    target = _tiny_model(0, layers=4, hidden=128, heads=4)
    draft = _tiny_model(1, layers=2, hidden=128, heads=4)
    with torch.no_grad():
        # draft = target's embeddings/head + first 2 layers, plus noise -> correlated predictions
        sd_t = target.state_dict()
        sd_d = draft.state_dict()
        for k in sd_d:
            if k in sd_t and sd_t[k].shape == sd_d[k].shape:
                sd_d[k] = sd_t[k] + noise * torch.randn_like(sd_t[k])
        draft.load_state_dict(sd_d)
    return target, draft


@dataclass
class ModelPair:
    target: torch.nn.Module
    draft: torch.nn.Module
    tokenizer: object
    device: torch.device
    dtype: torch.dtype
    vocab_size: int
    eos_ids: set[int]
    target_id: str
    draft_id: str


def vocab_fingerprint(tok) -> str:
    items = sorted(tok.get_vocab().items(), key=lambda kv: kv[1])
    return hashlib.sha256(repr(items).encode()).hexdigest()[:16]


def load_pair(target_id: str, draft_id: str, device: str = "auto", dtype: str = "auto",
              revision_target: str | None = None, revision_draft: str | None = None) -> ModelPair:
    dev = pick_device(device)
    dt = pick_dtype(dtype, dev)
    if target_id == "random-tiny":
        target, draft = make_tiny_pair()
        tok = ByteTokenizer()
        eos = {tok.eos_token_id}
    else:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        tok = AutoTokenizer.from_pretrained(target_id, revision=revision_target)
        tok_d = AutoTokenizer.from_pretrained(draft_id, revision=revision_draft)
        if vocab_fingerprint(tok) != vocab_fingerprint(tok_d):
            raise ValueError(f"Tokenizer mismatch: {target_id} vs {draft_id}. Speculative decoding "
                             "requires the draft and target to share one vocabulary.")
        target = AutoModelForCausalLM.from_pretrained(target_id, revision=revision_target, torch_dtype=dt)
        draft = AutoModelForCausalLM.from_pretrained(draft_id, revision=revision_draft, torch_dtype=dt)
        eos = set()
        for t in (tok.eos_token_id, getattr(target.generation_config, "eos_token_id", None)):
            if isinstance(t, int):
                eos.add(t)
            elif isinstance(t, (list, tuple)):
                eos.update(int(x) for x in t)
    target = target.to(dev, dt).eval()
    draft = draft.to(dev, dt).eval()
    vocab = int(target.get_output_embeddings().weight.shape[0])
    if int(draft.get_output_embeddings().weight.shape[0]) != vocab:
        raise ValueError("draft and target output vocab sizes differ")
    return ModelPair(target, draft, tok, dev, dt, vocab, eos, target_id, draft_id)


def encode_prompt(tok, text: str, max_tokens: int) -> list[int]:
    """Apply the chat template when the tokenizer has one (instruct models)."""
    if isinstance(tok, ByteTokenizer):
        return tok.encode(text)[:max_tokens]
    if getattr(tok, "chat_template", None):
        ids = tok.apply_chat_template([{"role": "user", "content": text}], add_generation_prompt=True,
                                      tokenize=True)
        if hasattr(ids, "keys"):          # newer transformers may return a BatchEncoding
            ids = ids["input_ids"]
    else:
        ids = tok(text)["input_ids"]
    return list(ids)[-max_tokens:]

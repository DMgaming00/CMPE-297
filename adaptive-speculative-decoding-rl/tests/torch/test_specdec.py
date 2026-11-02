"""Correctness of the real decoder, using tiny random models in fp32 on CPU (no download).

These tests are the core evidence that the implementation is right:
  1. Speculative decoding output == target greedy output, for many depth policies.
  2. Trace probes agree with what the real decoder accepts.
  3. The simulator replays a trace with EXACTLY the accepted counts the real decoder sees.
"""
import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")

from ltdmini.build_traces import build_traces
from ltdmini.models import load_pair
from ltdmini.policies import ConfidenceStop, EntropyStop, FixedDepth
from ltdmini.sim import SimCore
from ltdmini.specdec import draft_from_every_position, greedy_autoregressive, speculative_greedy
from ltdmini.timing import TimingModel

DMAX = 6
PROMPTS = ["def add(a, b):", "The quick brown fox", "Explain caching.", "x"]


@pytest.fixture(scope="module")
def pair():
    return load_pair("random-tiny", "random-tiny-draft", device="cpu", dtype="float32")


def _ids(pair, text):
    return pair.tokenizer.encode(text)


@pytest.mark.parametrize("policy", [FixedDepth(1, DMAX), FixedDepth(3, DMAX), FixedDepth(DMAX, DMAX),
                                    ConfidenceStop(0.3), EntropyStop(0.2)], ids=lambda p: p.name)
@pytest.mark.parametrize("prompt", PROMPTS)
def test_speculative_equals_greedy(pair, policy, prompt):
    ids = _ids(pair, prompt)
    ar = greedy_autoregressive(pair.target, ids, 40, set(), pair.device)
    sd = speculative_greedy(pair.target, pair.draft, ids, policy, 40, DMAX, set(), pair.vocab_size, pair.device)
    assert sd.tokens == ar.tokens
    assert all(1 <= c["depth"] <= DMAX and 0 <= c["accepted"] <= c["depth"] for c in sd.cycles)


def test_eos_stops_generation(pair):
    ids = _ids(pair, PROMPTS[0])
    ar = greedy_autoregressive(pair.target, ids, 30, set(), pair.device)
    eos = {ar.tokens[5]}
    ar2 = greedy_autoregressive(pair.target, ids, 30, eos, pair.device)
    sd = speculative_greedy(pair.target, pair.draft, ids, FixedDepth(4, DMAX), 30, DMAX, eos, pair.vocab_size, pair.device)
    assert sd.tokens == ar2.tokens and sd.tokens[-1] in eos


def test_probe_accept_lengths_match_real_first_cycle(pair):
    for prompt in PROMPTS:
        ids = _ids(pair, prompt)
        ar = greedy_autoregressive(pair.target, ids, 24, set(), pair.device)
        _, _, acc = draft_from_every_position(pair.draft, ids, ar.tokens, DMAX, pair.device)
        sd = speculative_greedy(pair.target, pair.draft, ids, FixedDepth(DMAX, DMAX), 24, DMAX, set(),
                                pair.vocab_size, pair.device)
        assert sd.cycles[0]["accepted"] == min(acc[0], DMAX)


@pytest.mark.parametrize("k", [1, 2, 4, DMAX])
def test_simulator_replays_real_decoder_exactly(pair, k):
    """Same policy, same prompt: the simulator's per-cycle (depth, accepted) sequence
    must equal the real decoder's. This is what makes simulator training valid."""
    ids = _ids(pair, PROMPTS[1])
    traces = build_traces(pair, [("t-0", PROMPTS[1])], 32, DMAX, 512)
    tr = traces[0]
    sd = speculative_greedy(pair.target, pair.draft, ids, FixedDepth(k, DMAX), 32, DMAX, set(), pair.vocab_size, pair.device)
    core = SimCore(TimingModel.synthetic(), pair.vocab_size, DMAX)
    obs, done = core.reset(tr), False
    pol = FixedDepth(k, DMAX)
    while not done:
        obs, _, done, _ = core.step(pol.should_continue(obs))
    real = [(c["depth"], c["accepted"]) for c in sd.cycles]
    sim = [(c.depth, c.accepted) for c in core.cycles]
    # The final cycle can differ: the trace stops at 32 tokens while the real decoder may
    # accept drafts beyond that point before truncating. Every earlier cycle must match.
    assert len(sim) >= 2
    assert sim[:-1] == real[: len(sim) - 1]


def test_trace_features_match_decoder_features(pair):
    """Top-1 probabilities recorded in traces equal those the decoder sees at depth 1."""
    ids = _ids(pair, PROMPTS[2])
    ar = greedy_autoregressive(pair.target, ids, 12, set(), pair.device)
    top1, _, _ = draft_from_every_position(pair.draft, ids, ar.tokens, DMAX, pair.device)
    out = pair.draft(input_ids=torch.tensor([ids]))
    p0 = torch.softmax(out.logits[0, -1].float(), -1).max().item()
    assert np.isclose(top1[0][0], p0, atol=1e-5)


@pytest.mark.skipif(not torch.backends.mps.is_available(), reason="MPS not available")
def test_mps_fp16_match_rate_report(record_property, capsys):
    """fp16 on MPS: batched verify and 1-token AR can round differently, so near-tied argmaxes may flip.
    We therefore do NOT assert equality here; we measure and report the token-match rate (exactness is asserted
    in fp32 on CPU above). Only sanity is asserted: cycles are well-formed and output lengths agree in bound."""
    mp = load_pair("random-tiny", "random-tiny-draft", device="mps", dtype="float16")
    total = matched = 0
    first_div = []
    for prompt in PROMPTS:
        ids = mp.tokenizer.encode(prompt)
        ar = greedy_autoregressive(mp.target, ids, 40, set(), mp.device)
        sd = speculative_greedy(mp.target, mp.draft, ids, FixedDepth(4, DMAX), 40, DMAX, set(), mp.vocab_size, mp.device)
        assert all(1 <= c["depth"] <= DMAX and 0 <= c["accepted"] <= c["depth"] for c in sd.cycles)
        n = min(len(ar.tokens), len(sd.tokens))
        assert n > 0
        eq = [a == b for a, b in zip(ar.tokens[:n], sd.tokens[:n])]
        total += n
        matched += sum(eq)
        first_div.append(eq.index(False) if not all(eq) else None)
    rate = matched / total
    record_property("mps_fp16_token_match_rate", rate)
    with capsys.disabled():
        print(f"\n[MPS fp16] positional token-match rate = {rate:.4f} ({matched}/{total}); "
              f"first divergence index per prompt = {first_div} (None = identical)")

# 21 — Hardware, GPU & Inference Economics: Decisions, Performance, Troubleshooting, Observability

> **Why this matters for FDEs:** [llm-slm.md](../llm-slm.md) covers GPU-days
> for *training/fine-tuning*. [notes/17](./17_observability_and_debugging_field.md)
> covers observability at the *app/GCP* layer. Neither answers the question
> you'll actually get asked in the field: *"should we self-host this model,
> what hardware, and why is it slow/expensive right now?"* This file is
> that answer — the inference-serving hardware layer sitting between the
> two.

---

## 1. The decision framework — API vs. self-hosted vs. edge

```
                        ┌─────────────────────────┐
                        │  Data residency /        │
                        │  air-gapped requirement? │
                        └───────────┬──────────────┘
                          YES│              │NO
                             ▼              ▼
                  ┌────────────────┐   ┌──────────────────────────┐
                  │ Self-host, no   │   │ Predictable, high volume  │
                  │ external call   │   │ (>~2-5M tokens/day        │
                  │ possible.       │   │ sustained)?               │
                  │ On-prem/edge.   │   └────────┬──────────────────┘
                  └────────────────┘      YES│         │NO
                                              ▼         ▼
                                   ┌────────────────┐ ┌─────────────────────┐
                                   │ Model runs the │ │ Frontier-model API   │
                                   │ same or better │ │ (Claude, etc.) —      │
                                   │ open-weight?   │ │ lower latency to      │
                                   └────┬───────────┘ │ ship, no ops burden,  │
                                    YES│      │NO      │ scales to zero.       │
                                       ▼      ▼        └─────────────────────┘
                              ┌──────────────┐ ┌──────────────────────┐
                              │ Self-host —  │ │ API, unless cost math │
                              │ cost math    │ │ in §3 says otherwise  │
                              │ in §3 likely │ └──────────────────────┘
                              │ favors it    │
                              └──────────────┘
```

**Self-hosting wins when:** data residency/compliance forces it (see
[governance-playbook.md](../governance-playbook.md)), volume is high and
steady enough that the fixed GPU cost beats per-token API pricing (§3),
latency needs to be sub-100ms and colocated with the caller, or an
open-weight model already matches quality at the task.

**API wins when:** volume is low/spiky (you'd be paying for idle GPUs),
you need frontier-model capability no open model matches, or the team has
no MLOps capacity to own GPU fleet health — self-hosting isn't just a
hardware decision, it's an ongoing operational commitment (see §5).

**Edge/on-device wins when:** connectivity is unreliable (see the
field-service copilot prompt in
[interview-drills.md](../interview-drills.md) §1.3), or per-inference
latency must be near-zero. This is [llm-slm.md](../llm-slm.md) §7's SLM
sweet spot — small models, CPU or a single consumer GPU, no network hop.

---

## 2. GPU selection guide

Specs below are approximate and cloud pricing moves constantly — treat the
$/hr column as "which order of magnitude," not a quote, and verify current
pricing with the cloud provider before sizing a customer's budget.

| GPU | VRAM | Class | Best for | Rough $/hr (on-demand, single GPU) |
|---|---|---|---|---|
| T4 | 16GB | Older (Turing) | Small model inference, batch/offline scoring, dev/test | ~$0.35–0.60 |
| L4 | 24GB | Ada Lovelace, inference-optimized | Cost-efficient production inference for 7B–13B models | ~$0.50–1.00 |
| A10G | 24GB | Ampere | General inference, common on AWS | ~$1.00–1.50 |
| L40S | 48GB | Ada Lovelace | Larger inference (13B–34B) or mixed inference+light fine-tuning | ~$1.50–2.50 |
| A100 40GB/80GB | 40/80GB HBM2e | Ampere, high bandwidth | Fine-tuning, larger model inference, multi-tenant serving | ~$2–5 |
| H100 80GB | 80GB HBM3 | Hopper, FP8 native | Frontier-scale serving/training, highest throughput per GPU | ~$4–8 |
| H200 | 141GB HBM3e | Hopper refresh | Memory-bound workloads (long context, large KV cache) | higher than H100 |

**Rule of thumb for picking:** start from VRAM headroom (§4.2), not raw
speed — an undersized GPU that OOMs is worse than a slightly slower one
that fits. For most FDE deployments (7B–34B open models, moderate
concurrency), **L4 or L40S is the pragmatic default**: A100/H100 is for
when the cost math in §3 or the latency budget genuinely demands it.

---

## 3. Cost-per-token economics

**Self-host breakeven, worked example:**

```
GPU: L4 at $0.80/hr, serving a 13B model
Sustained throughput (with continuous batching, see §4.1): ~2,000 tokens/sec
Tokens/day at 100% utilization: 2,000 * 86,400 = 172,800,000
Realistic utilization (bursty traffic, not 24/7 saturated): ~30%
Effective tokens/day: ~51.8M

Cost per day: $0.80 * 24 = $19.20
Effective cost per 1M tokens: $19.20 / 51.8 ≈ $0.37 per 1M tokens

Compare to a mid-tier hosted API at (illustrative) $1-3 per 1M tokens blended:
self-hosting wins once daily volume reliably clears the tens-of-millions-
of-tokens range — below that, the API's zero idle-cost and zero ops burden
usually wins even at a higher per-token rate.
```

**What this math misses (and why customers get burned by it):** the GPU
cost above is compute only. Add: engineering time to operate the serving
stack, redundancy (a single GPU is a single point of failure — see §6),
autoscaling headroom for traffic spikes, and the model-quality gap between
the open model you can afford and the frontier API you're comparing
against. Present both numbers to the customer, not just the compute line.

---

## 4. Performance tuning

### 4.1 Batching

- **Static batching** (naive): wait for N requests, run them together,
  return all N at once. Simple, but a slow request in the batch holds up
  every fast one — poor tail latency.
- **Continuous batching** (vLLM, TensorRT-LLM, SGLang — see
  [llm-slm.md](../llm-slm.md) §11.2): new requests join the batch
  mid-flight as slots free up. This is the default for any production
  self-hosted deployment — it's the single biggest throughput lever
  available, often 5-10x over naive batching.
- **Tuning knob:** `max_num_seqs` / max batch size trades throughput
  (higher = better GPU utilization) against per-request latency (higher =
  more contention for compute). Start conservative, raise it while
  watching P95 latency, stop when P95 breaches budget.

### 4.2 KV cache memory — the real VRAM constraint

Model weights are a fixed cost; the **KV cache grows with concurrency and
context length**, and it's what actually determines how many concurrent
requests a GPU can serve before OOM.

```
KV cache size (bytes) ≈ 2 × num_layers × num_kv_heads × head_dim
                         × seq_len × batch_size × bytes_per_element

Worked example — 7B model (32 layers, 32 kv heads, head_dim 128),
2048-token context, batch of 16, FP16 (2 bytes):

  2 × 32 × 32 × 128 × 2048 × 16 × 2 bytes ≈ 17.2 GB

That's on top of ~14GB for the FP16 weights themselves — a 7B model at
this concurrency needs ~31GB+ VRAM just for weights + KV cache, before
activation memory. This is why "the model fits on the GPU" and "the model
serves 16 concurrent 2K-context requests on the GPU" are different claims.
```

**Levers when KV cache is the bottleneck:** reduce max context length if
the use case allows it, use **grouped-query attention (GQA)** models
(fewer KV heads — most modern open models already do this), quantize the
KV cache itself (FP8 KV cache, supported by vLLM/TensorRT-LLM), or add
VRAM (bigger GPU, or tensor parallelism across GPUs, §4.4).

### 4.3 Quantization

| Precision | Memory vs. FP16 | Typical quality impact | When |
|---|---|---|---|
| BF16/FP16 | baseline | none (reference) | Default unless VRAM-constrained |
| FP8 | ~50% | minimal, if calibrated | H100/H200 native support — good default there |
| INT8 | ~50% | small | Broad hardware support, mature tooling |
| INT4 (GPTQ/AWQ) | ~25% | noticeable on complex reasoning, usually fine for extraction/classification | VRAM-constrained edge/single-GPU deployments |

**Field rule:** quantize the weights before you buy a bigger GPU — it's
free (no new hardware) and the quality hit is often smaller than
customers expect, especially for narrow, evaluated use cases. Always
re-run the [eval harness](../eval-driven-development.md)'s golden set
after quantizing; "should be fine" is not a substitute for measuring it.

### 4.4 Parallelism (when one GPU isn't enough)

- **Tensor parallelism (TP):** splits each layer's matrix math across
  GPUs. Needs fast interconnect (NVLink, not just PCIe) — the GPUs are
  constantly exchanging partial results. Use when the model doesn't fit on
  one GPU even quantized.
- **Pipeline parallelism (PP):** splits *layers* across GPUs — GPU 1 runs
  layers 1-10, GPU 2 runs 11-20, etc. Lower interconnect requirements than
  TP, but introduces a pipeline bubble (idle time) that hurts latency more
  than throughput.
- **Data parallelism:** just run N independent copies of the model, one
  per GPU (or GPU group), load-balanced. Simplest to operate, and the
  right default once a single model instance's serving unit is settled —
  scale *out* with data parallelism before you reach for TP/PP to scale a
  single instance *up*.

---

## 5. Troubleshooting playbook

Same format as [notes/17](./17_observability_and_debugging_field.md#5-the-fde-debugging-playbook--production-incidents)'s
issue table — this is the GPU/inference-layer continuation of it.

```
ISSUE: CUDA out of memory (OOM) during serving
  Symptom: Requests fail intermittently under load, or immediately at startup
  Diagnosis: nvidia-smi during the failure — check memory used vs. total;
             correlate with concurrent request count and context length
  Fix 1: Reduce max_num_seqs (concurrent batch size)
  Fix 2: Reduce max context length accepted
  Fix 3: Quantize weights and/or KV cache (§4.3)
  Fix 4: Move to a larger-VRAM GPU or add tensor parallelism (§4.4)
  Root cause check: KV cache math (§4.2) — was capacity ever actually
  sized for the traffic pattern, or was it sized for the demo?

ISSUE: Low GPU utilization (<40%) despite high request volume
  Symptom: nvidia-smi shows low SM utilization, but requests are queued/slow
  Diagnosis: Check whether batching is actually continuous (§4.1) — naive
             batching or a batch size of 1 leaves the GPU idle between requests
  Fix 1: Switch to a continuous-batching server (vLLM/TensorRT-LLM/SGLang)
  Fix 2: Raise max_num_seqs
  Fix 3: Check for a CPU-side bottleneck upstream (tokenization, network,
         a synchronous guardrail call blocking the GPU from ever being fed —
         see the eval_sampling_blocks_path fault in
         capstones/incident_debugging/ for exactly this class of bug)

ISSUE: Throughput cliff at a specific concurrency level
  Symptom: Latency is fine up to N concurrent requests, then degrades sharply
  Diagnosis: N is almost always a KV-cache-exhaustion boundary — compare
             against the §4.2 math for the deployed context length
  Fix: Either accept N as the hard concurrency ceiling and add
       horizontal replicas (data parallelism, §4.4), or reduce per-request
       KV cache footprint (shorter context, quantized KV cache)

ISSUE: Multi-GPU throughput doesn't scale linearly with GPU count
  Symptom: 2 GPUs give <2x the throughput of 1
  Diagnosis: Check interconnect — nvidia-smi topo -m to confirm NVLink vs.
             PCIe-only between GPUs; tensor parallelism over PCIe-only
             links is a common silent bottleneck
  Fix 1: If no NVLink, prefer data parallelism over tensor parallelism
  Fix 2: Confirm the serving framework's parallelism config matches the
         actual hardware topology, not a copy-pasted default

ISSUE: Latency spikes correlate with thermal/power events
  Symptom: Periodic latency spikes, not correlated with request volume
  Diagnosis: nvidia-smi -q -d TEMPERATURE,POWER, or DCGM (§6) history —
             check for thermal throttling or power-cap throttling
  Fix: Usually an infra/facilities issue, not a code fix — flag to the
       customer's infra team; this is a "your problem too" moment per
       README.md's "own the outcome, not the ticket"
```

---

## 6. GPU-level observability

[notes/17](./17_observability_and_debugging_field.md)'s "Four Signals"
stack (logs, metrics, traces, events) is complete at the *application*
layer but has no GPU signal in it. Add a fifth lane for anything
self-hosted:

```
┌─────────────────────────────────────────────────────────────────┐
│  GPU SIGNALS (extends notes/17's Four Signals)                   │
│                                                                   │
│  Utilization %    Memory used/total   Power draw   Temperature   │
│  (SM occupancy —  (the KV-cache OOM   (throttling   (throttling  │
│  low = batching   ceiling from §4.2)  risk)         risk)        │
│  problem, §5)                                                    │
│                                                                   │
│  TOOLING:                                                        │
│  nvidia-smi          — ad hoc, on-box, first thing to check       │
│  DCGM Exporter       — NVIDIA's Prometheus exporter, the          │
│                        production-grade path                     │
│  Prometheus+Grafana  — scrape DCGM, dashboard alongside app       │
│                        metrics                                   │
│  GKE GPU node pools  — Cloud Monitoring auto-collects             │
│                        kubernetes.io/container/accelerator/*      │
│  Vertex AI endpoints — GPU utilization surfaced in the endpoint's  │
│                        built-in monitoring, no extra setup        │
└─────────────────────────────────────────────────────────────────┘
```

### Quick commands

```bash
# Point-in-time check — always the first command when something's slow
nvidia-smi

# Continuous watch (refresh every 1s)
nvidia-smi -l 1

# Topology — confirm NVLink vs PCIe-only between GPUs (§5, multi-GPU issue)
nvidia-smi topo -m

# Temperature/power detail (thermal throttling diagnosis)
nvidia-smi -q -d TEMPERATURE,POWER
```

### DCGM Exporter + Prometheus (production path)

```yaml
# Minimal DCGM Exporter deployment on a GKE GPU node pool
# (run alongside the app metrics already flowing to Cloud Monitoring per notes/17)
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: dcgm-exporter
spec:
  selector:
    matchLabels: {app: dcgm-exporter}
  template:
    metadata:
      labels: {app: dcgm-exporter}
    spec:
      nodeSelector:
        cloud.google.com/gke-accelerator: "true"
      containers:
        - name: dcgm-exporter
          image: nvcr.io/nvidia/k8s/dcgm-exporter:latest
          ports:
            - containerPort: 9400
              name: metrics
```

### Essential GPU alerting checklist (extends notes/17 §3's checklist)

```
FOR EVERY SELF-HOSTED GPU DEPLOYMENT, ADD THESE ALERTS:

□ GPU memory utilization > 90% sustained (imminent OOM, see §5)
□ GPU utilization < 20% sustained during known-busy hours (batching
  misconfiguration or an upstream bottleneck, see §5)
□ GPU temperature > manufacturer throttle threshold (thermal risk)
□ Any GPU dropping off nvidia-smi's device list (hardware failure —
  page immediately, this is a hard outage for that replica)
□ KV-cache-exhaustion-triggered request rejections > 1% (concurrency
  ceiling reached — needs horizontal scaling per §4.4, not a restart)
```

---

## 7. Field checklist

```
BEFORE RECOMMENDING SELF-HOSTED GPU INFRASTRUCTURE TO A CUSTOMER:

□ Ran the decision framework (§1) — is self-hosting actually justified,
  or is this a default reached for without checking the API path?
□ Sized VRAM from the KV-cache math (§4.2), not just "model fits"
□ Priced the compute (§3) AND named the hidden ops cost — redundancy,
  on-call, autoscaling headroom
□ Chose the smallest GPU class that clears the headroom math (§2) —
  bigger isn't free, and an oversized GPU sitting at 20% utilization is
  the same waste as an undersized one that OOMs
□ Quantization evaluated against the golden set (§4.3) before buying
  more hardware to avoid it
□ GPU-level alerting wired (§6) before go-live, not after the first
  3am page
```

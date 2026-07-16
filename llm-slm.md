# The Ultimate Guide: Building Domain-Specific SLMs & LLMs From Scratch

*A principal-level field reference — strategy, data, architecture, training, adaptation, alignment, evaluation, deployment, and compliance. All claims anchored to primary papers (arXiv links in §14).*

---

## Table of Contents

1. [Strategic Decision Framework: Should You Even Train From Scratch?](#1-strategic-decision-framework)
2. [Scaling Laws & Compute Budgeting](#2-scaling-laws--compute-budgeting)
3. [Data Engineering: The 80% of the Work](#3-data-engineering)
4. [Tokenizer Design for Domain Models](#4-tokenizer-design)
5. [Model Architecture: The Modern Decoder Recipe](#5-model-architecture)
6. [Pretraining: Infrastructure & Training Dynamics](#6-pretraining)
7. [SLM-Specific Strategies (0.1B–7B)](#7-slm-specific-strategies)
8. [Domain Adaptation Playbook](#8-domain-adaptation-playbook)
9. [Post-Training: SFT, RLHF, DPO, Reasoning](#9-post-training)
10. [Evaluation & Benchmarking](#10-evaluation)
11. [Compression & Inference Optimization](#11-compression--inference)
12. [Safety, Governance & EU AI Act Compliance](#12-safety-governance--compliance)
13. [Cost Models, Reference Stack & 12-Month Roadmap](#13-cost-models--roadmap)
14. [Master Reference List](#14-master-reference-list)

---

## 1. Strategic Decision Framework

The first principal-level decision is **not** architectural — it is whether "from scratch" is justified at all. Frame this as an ADR with business KPIs, not technical preference.

### The Adaptation Ladder (cheapest → most expensive)

| Rung | Technique | Compute | Data Needed | When It Wins |
|---|---|---|---|---|
| 1 | Prompting + RAG | ~0 | Documents only | Knowledge is retrievable, changes frequently, provenance matters (BFSI audit trails) |
| 2 | PEFT / LoRA fine-tuning [Hu et al., 2021] | 1 GPU-days | 1k–100k examples | Style, format, task behavior on an open base model |
| 3 | Full SFT | 10–100 GPU-days | 10k–1M examples | Deep task specialization; base model license permits |
| 4 | Continued / Domain-Adaptive Pretraining (DAPT) [Gururangan et al., 2020] | 100–5,000 GPU-days | 1B–100B domain tokens | Domain vocabulary/distribution shift is large (legal, biomedical, quant finance) |
| 5 | **From-scratch pretraining** | 5,000–1M+ GPU-days | 100B–15T tokens | See criteria below |

### From-scratch is justified only when ≥2 of these hold:

1. **Data sovereignty / IP**: You cannot legally send data through third-party weights or APIs (BaFin outsourcing rules, DORA third-party risk, patient data under GDPR Art. 9). You need full provenance of every training token.
2. **Tokenizer mismatch is severe**: General tokenizers fragment your domain text badly (genomics, SMILES chemistry, legacy COBOL, non-Latin scripts, dense financial tickers). Token efficiency losses of 2–4× make general models economically worse forever.
3. **Distribution shift is extreme**: Your text barely resembles web text (protein sequences — ESM-2 [Lin et al., 2022]; code — StarCoder [Li et al., 2023]; time-series).
4. **Licensing/commercial constraints**: Llama-style licenses or acceptable-use policies conflict with your product (defense, some fintech use cases).
5. **Edge/latency budget forces a custom SLM**: You need a 0.5–3B model with maximum quality-per-parameter in one domain, where distillation from your own data pipeline beats adapting a general SLM.

**Counter-evidence to weigh honestly**: BloombergGPT [Wu et al., 2023] — 50B params, ~569B mixed tokens, trained from scratch on financial + general data — was later matched or beaten on many financial tasks by GPT-4 prompting and by fine-tuned open models at a fraction of the cost. The 2023–2026 trend strongly favors **continued pretraining of strong open bases (Llama 3, Qwen 2.5, Mistral, Gemma) + heavy post-training** over greenfield pretraining, except where criteria 1–5 dominate.

**Decision record**: Write this as an ADR — context (regulatory + data constraints), options (rungs 1–5), decision, consequences (cost, talent lock-in, refresh cadence). State confidence level and the eval that would falsify the choice.

---

## 2. Scaling Laws & Compute Budgeting

### 2.1 The core results

- **Kaplan et al., 2020** ("Scaling Laws for Neural Language Models"): loss follows power laws in parameters N, dataset size D, and compute C; early guidance over-weighted parameters.
- **Hoffmann et al., 2022 (Chinchilla)**: for compute-optimal *training*, scale N and D roughly equally — **≈20 tokens per parameter**. Chinchilla-70B (1.4T tokens) beat Gopher-280B.
- **Inference-aware ("over-training") regime**: if the model will serve billions of queries, train far past Chinchilla-optimal. Llama 3 8B was trained on ~15T tokens (~1,875 tokens/param) [Grattafiori et al., 2024]; small models keep improving log-linearly well past 20:1 because inference cost dominates TCO.
- **Data-constrained scaling** [Muennighoff et al., 2023]: repeating data up to ~4 epochs is nearly as good as fresh data; beyond ~16 epochs returns collapse. Critical for domain corpora, which are usually small.

### 2.2 Practical compute math

Approximate training FLOPs: **C ≈ 6 · N · D** (forward+backward).

Worked example — a 3B-param domain SLM on 600B tokens:
- C ≈ 6 × 3e9 × 6e11 ≈ **1.08e22 FLOPs**
- H100 (SXM, bf16 dense) sustained ~400 TFLOPs/GPU at ~40% MFU → ~1.08e22 / 4e14 ≈ 2.7e7 GPU-seconds ≈ **~7,500 H100-hours ≈ 313 H100-days**, i.e. ~10 days on 32×H100.
- At ~$2.5–4/H100-hr cloud pricing: **$19k–30k** compute for one run. Budget **3–5× that** for ablations, failed runs, data experiments, and post-training.

### 2.3 Budgeting heuristics for domain models

| Model size | Token budget (from-scratch) | Typical hardware | Realistic all-in cost |
|---|---|---|---|
| 0.5–1.5B SLM | 300B–2T (over-train) | 8–64 H100 | $30k–300k |
| 3–8B | 1–15T | 64–512 H100 | $200k–5M |
| 30–70B | 5–15T | 1k–8k H100 | $5M–80M |
| DAPT of open 7–8B | 20–200B domain tokens | 16–128 H100 | $15k–250k |

Fit domain data reality first: if you only have 30B unique domain tokens, from-scratch at >3B params is data-starved — mix with general corpora (see §3.5) or drop to DAPT.

---

## 3. Data Engineering

Data quality is the highest-leverage variable — FineWeb [Penedo et al., 2024], RefinedWeb [Penedo et al., 2023], Dolma [Soldaini et al., 2024], and the Phi series [Gunasekar et al., 2023; Abdin et al., 2024] all demonstrate that curation beats raw scale.

### 3.1 Sourcing

- **General web**: FineWeb / FineWeb-Edu (15T tokens, quality-classifier filtered), RefinedWeb, Dolma, The Pile [Gao et al., 2020], C4 [Raffel et al., 2020], RedPajama.
- **Code**: The Stack v2 [Lozhkov et al., 2024], StarCoder data — license-filtered, PII-scrubbed.
- **Domain (examples)**: SEC EDGAR filings, ECB/BaFin/ESMA publications, earnings-call transcripts (finance); PubMed/PMC, MIMIC (healthcare, heavy governance); EUR-Lex, national case law (legal); internal wikis, tickets, runbooks (enterprise).
- **Synthetic**: teacher-generated "textbook-quality" data (Phi approach), Self-Instruct [Wang et al., 2022], Evol-Instruct. Guard against model collapse from recursive synthetic training [Shumailov et al., 2024] — always anchor with real data and dedup against eval sets.

### 3.2 Cleaning pipeline (canonical order)

1. **Extraction**: trafilatura / resiliparse for HTML; domain parsers for PDF (financial filings need table-aware extraction).
2. **Language & encoding filtering**: fastText LID; fix mojibake.
3. **Quality filtering**: heuristics (Gopher rules [Rae et al., 2021] — doc length, symbol ratios, repetition), then model-based classifiers (FineWeb-Edu's educational-value classifier; perplexity filtering against a KenLM domain model).
4. **Deduplication**: exact (hash on normalized text) + near-dup via **MinHash-LSH** [Lee et al., 2021, "Deduplicating Training Data Makes Language Models Better"]. Dedup reduces memorization and improves loss-per-token.
5. **PII & compliance scrubbing**: regex + NER for emails, IBANs, national IDs; mandatory under GDPR minimization; log decisions for audit (EU AI Act GPAI data-summary obligations).
6. **Decontamination**: n-gram overlap (typically 13-grams) against every eval benchmark you will ever report. Contamination invalidates your entire eval story.
7. **Toxicity/safety filtering**: threshold, don't zero out — over-filtering harms robustness and refusal calibration.

Tooling: **datatrove** (HF, used for FineWeb), **Dolma toolkit** (AI2), **NeMo Curator** (NVIDIA, GPU-accelerated), Spark for petabyte scale.

### 3.3 Data mixing for domain models

- BloombergGPT used ~51% financial / 49% general — retaining general ability prevents catastrophic loss of reasoning/instruction-following.
- Practical starting mix for a domain model: **40–60% domain, 20–30% high-quality general web (FineWeb-Edu-like), 10–20% code (code improves reasoning), 5–10% math**.
- **DoReMi** [Xie et al., 2023] learns domain weights with a small proxy model; worth it above ~1T-token budgets.
- **Curriculum / staged training**: modern practice (Llama 3, OLMo 2 [OLMo Team, 2024]) uses a final "annealing" phase — last 5–15% of tokens on the highest-quality, most domain-dense data with LR decayed to ~0. This disproportionately shapes final behavior; put your best domain data here.

### 3.4 Domain token math

Rule of thumb: you need **≥10–50B unique domain tokens** for from-scratch domain pretraining to beat DAPT. Below that, DAPT with up-to-4-epoch repetition [Muennighoff et al., 2023] on a strong base wins.

---

## 4. Tokenizer Design

A domain tokenizer is one of the few *irreversible* decisions — you cannot cheaply change it after pretraining.

### 4.1 Algorithms

- **BPE** [Sennrich et al., 2016] — used by GPT/Llama lineages (byte-level BPE via tiktoken/HF tokenizers).
- **Unigram LM** [Kudo, 2018] — probabilistic; often better for morphologically rich or non-segmented languages.
- **SentencePiece** [Kudo & Richardson, 2018] — language-agnostic trainer for both, operates on raw text.

### 4.2 Domain decisions

- **Vocab size**: 32k (Llama 2) → 128k (Llama 3) → 150k+ (Qwen 2.5 [Qwen Team, 2024]). Larger vocab = better compression (fewer tokens/doc → cheaper inference, longer effective context) but bigger embedding tables — significant for SLMs (at 1B params, a 128k vocab can be >25% of parameters; consider **tied embeddings**, as in Gemma [Gemma Team, 2024] and MobileLLM [Liu et al., 2024]).
- **Fertility check**: measure tokens-per-word on your domain corpus vs. general text. If your domain fertility is >1.3× general, a custom tokenizer pays for itself.
- **Special tokens**: reserve generously up-front (chat roles, tool-call delimiters, FIM tokens for code [Bavarian et al., 2022], domain markers like `<filing>`, `<icd10>`). Adding later is painful.
- **Digits**: single-digit splitting (Llama-style) measurably helps arithmetic — important for quant/finance models.
- **Vocabulary extension for DAPT**: you can extend an existing tokenizer with domain merges and initialize new embeddings from subword averages — standard trick in biomedical and multilingual adaptation; retrain embeddings during continued pretraining.

---

## 5. Model Architecture

The 2024–2026 consensus decoder recipe ("Llama-style") is remarkably stable. Deviate only with ablation evidence.

### 5.1 The modern default stack

| Component | Choice | Reference |
|---|---|---|
| Backbone | Decoder-only transformer | Vaswani et al., 2017; Radford et al., 2018/2019 (GPT/GPT-2) |
| Positional encoding | **RoPE** (rotary) | Su et al., 2021 |
| Normalization | **RMSNorm**, pre-norm | Zhang & Sennrich, 2019 |
| Activation / FFN | **SwiGLU**, FFN dim ≈ 8/3·d | Shazeer, 2020 |
| Attention | **GQA** (grouped-query, e.g. 8 KV heads) | Ainslie et al., 2023 |
| Attention kernel | **FlashAttention-2/3** | Dao et al., 2022; Dao, 2023 |
| Bias terms | None (no biases in linear layers) | Llama practice |
| Context | 4–8k pretrain → extend via RoPE scaling (YaRN [Peng et al., 2023]) or long-context annealing | Llama 3 (128k) |
| Precision | bf16 compute, fp32 master weights & optimizer | — |

### 5.2 Variants worth knowing

- **MoE (Mixture of Experts)**: Switch Transformer [Fedus et al., 2021], Mixtral 8x7B [Jiang et al., 2024], DeepSeek-V3 (671B total / 37B active, MLA + fine-grained experts) [DeepSeek-AI, 2024]. MoE buys capacity at fixed inference FLOPs but complicates serving and fine-tuning — usually wrong for a first domain model.
- **MLA (Multi-head Latent Attention)** [DeepSeek-V2/V3]: compresses KV cache dramatically — attractive for long-context domain workloads (contracts, filings).
- **State-space / hybrid**: Mamba [Gu & Dao, 2023], Jamba [Lieber et al., 2024] — linear-time inference; hybrids (attention + SSM) are production-viable but tooling is thinner.
- **Depth vs. width for SLMs**: MobileLLM [Liu et al., 2024] shows **deep-and-thin** wins at <1B params; also use embedding sharing and layer sharing.

### 5.3 Sizing a config (example: 3B domain SLM)

- d_model 2560, 32 layers, 20 heads (GQA 4 KV heads), SwiGLU FFN ~6912, vocab 64k (tied), RoPE θ=500k, context 8192.
- Sanity-check params: ≈ 12·L·d² + 2·V·d (tied). Always verify with a parameter-count script before launch.

---

## 6. Pretraining

### 6.1 Distributed training stack

- **Parallelism**: Data parallel (with **ZeRO** sharding [Rajbhandari et al., 2020] / PyTorch **FSDP**), **tensor parallel** and **pipeline parallel** (Megatron-LM [Shoeybi et al., 2019; Narayanan et al., 2021]), sequence/context parallel for long context. Rule: TP within a node (NVLink), PP/DP across nodes.
- **Frameworks**: Megatron-LM / Megatron-Core, NVIDIA NeMo, GPT-NeoX [Andonian et al., EleutherAI], **torchtitan** (PyTorch-native), HF nanotron, **LitGPT**, and **nanoGPT / modded-nanoGPT** (Karpathy) for pedagogy and small-scale ablations. OLMo [Groeneveld et al., 2024] and Pythia [Biderman et al., 2023] provide fully open, reproducible training references — study their configs and logs.
- **Throughput target**: 35–45% MFU on H100 clusters is healthy for dense models; below 25% you have a bottleneck (dataloader, comms topology, or kernel issues).

### 6.2 Hyperparameters (battle-tested defaults)

- Optimizer: **AdamW**, β=(0.9, 0.95), eps 1e-8, weight decay 0.1, grad-clip 1.0.
- LR: peak ≈ 3e-4 (1–3B) down to ~1.5e-4 (30B+); **warmup 0.1–1%** of steps; **cosine decay to 10% of peak** — or **WSD (warmup-stable-decay)** schedule [MiniCPM, Hu et al., 2024] which enables flexible-length runs and clean annealing phases.
- Batch size: 2–8M tokens/step (ramp up early in training); sequence length 4k–8k with document packing (mask cross-document attention if possible).
- μP / muTransfer [Yang et al., 2022] lets you tune HPs on a small proxy and transfer to the target width — de-risks large runs.

### 6.3 Training dynamics & failure modes

- **Loss spikes**: mitigate with bf16 + fp32 master weights, grad clipping, z-loss on logits [PaLM, Chowdhery et al., 2022], embedding-norm regularization; on hard spikes, roll back to previous checkpoint and skip the offending data shard.
- **Checkpointing**: every 30–60 min of wall-clock; async saves; test restore *before* the run. Track everything in W&B/MLflow with data-provenance manifests (which shards, which mix, which tokenizer hash) — this is your EU AI Act technical-documentation backbone.
- **Evals during training**: perplexity on held-out domain + general sets every few B tokens; small benchmark suite (few-shot) every checkpoint; watch for domain PPL improving while general PPL degrades → mix imbalance.

---

## 7. SLM-Specific Strategies

Small Language Models (≈0.1B–7B) are the sweet spot for domain deployment: on-prem, edge, low latency, data residency by construction.

### 7.1 Three routes to a strong domain SLM

1. **From-scratch with extreme data quality** — the **Phi** thesis: "Textbooks Are All You Need" [Gunasekar et al., 2023]; Phi-3 [Abdin et al., 2024] and Phi-4 [Abdin et al., 2024b] show curated + synthetic data lets 3.8–14B models rival much larger ones. TinyLlama [Zhang et al., 2024] (1.1B on 3T tokens) and SmolLM2 [Allal et al., 2025] are open recipes worth replicating.
2. **Distillation from a larger teacher** — classic KD [Hinton et al., 2015]; sequence-level KD; **logit distillation during pretraining** (Gemma 2 [Gemma Team, 2024b] distilled from a larger teacher); MiniLLM [Gu et al., 2023] for reverse-KL generative distillation. For domains: generate teacher outputs on *your* domain prompts, filter with verifiers, train the SLM on the result (this is also how DeepSeek-R1 distilled reasoning into 1.5–70B models [DeepSeek-AI, 2025]).
3. **Prune + heal** — structured pruning of a big model then continued training: Sheared-LLaMA [Xia et al., 2023], Minitron / Llama-3.1-Minitron [Muralidharan et al., 2024] (prune width/depth, distill-heal with ~100B tokens — 10–40× cheaper than from scratch).

### 7.2 SLM architecture notes

- Tied input/output embeddings; deep-thin ratios (MobileLLM); GQA aggressively (KV cache dominates edge memory); consider 32k–64k vocab unless multilingual.
- Over-train massively: 1B-param SLMs happily absorb 2–5T tokens with continuing returns (Llama 3.2 1B/3B, Qwen2.5-0.5/1.5B practice).

---

## 8. Domain Adaptation Playbook

When from-scratch isn't justified (§1), this is the pipeline that wins.

### 8.1 Continued / Domain-Adaptive Pretraining (DAPT)

Canonical result: Gururangan et al., 2020 ("Don't Stop Pretraining") — DAPT + task-adaptive pretraining (TAPT) reliably improves domain tasks. Modern recipe:

1. Start from a strong open base (Llama 3.1 8B, Qwen2.5-7B, Mistral, Gemma 2 — check licenses against your product).
2. **Replay to prevent catastrophic forgetting**: mix 60–80% domain tokens with 20–40% general "replay" data resembling the original distribution [Ibrahim et al., 2024, "Simple and Scalable Strategies to Continually Pre-train"]. Re-warm LR to ~10–50% of original peak, decay again.
3. 20–200B tokens is the typical DAPT budget; anneal on the best domain data.
4. Then re-run post-training (§9) — DAPT damages instruction-following; you must restore it.

### 8.2 Named precedents to cite in design reviews

- **Finance**: BloombergGPT [Wu et al., 2023]; FinBERT [Araci, 2019]; FinGPT [Yang et al., 2023] (LoRA-based, open).
- **Biomedical/clinical**: BioGPT [Luo et al., 2022]; PubMedBERT [Gu et al., 2021]; Med-PaLM / Med-PaLM 2 [Singhal et al., 2022, 2023] (instruction-tuned + ensemble refinement, expert-level USMLE performance); MEDITRON-70B [Chen et al., 2023] (open DAPT of Llama-2 on medical corpora).
- **Code**: Codex [Chen et al., 2021]; Code Llama [Rozière et al., 2023] (DAPT of Llama 2 on 500B code tokens + infilling + long context); StarCoder 1/2 [Li et al., 2023; Lozhkov et al., 2024]; DeepSeek-Coder [Guo et al., 2024].
- **Science**: Galactica [Taylor et al., 2022] — also a cautionary tale about hallucination framing and launch comms.
- **Law**: SaulLM-7B [Colombo et al., 2024] (legal DAPT of Mistral).

Pattern across all: **DAPT on curated domain tokens + domain-specific instruction data + domain evals** — not exotic architectures.

---

## 9. Post-Training

### 9.1 Supervised Fine-Tuning (SFT)

- Instruction tuning: FLAN [Wei et al., 2021; Chung et al., 2022], InstructGPT SFT stage [Ouyang et al., 2022].
- **Quality ≫ quantity**: LIMA [Zhou et al., 2023] — 1k excellent examples can align a strong base. For domains: 5k–50k expert-authored or expert-verified examples (procedures, report drafting, tool use, refusal boundaries for regulated advice).
- Synthetic expansion: Self-Instruct [Wang et al., 2022], Evol-Instruct/WizardLM [Xu et al., 2023], Orca explanation-tuning [Mukherjee et al., 2023]; UltraChat/UltraFeedback [Cui et al., 2023]. Filter with execution checks, verifiers, or teacher grading.
- Chat template discipline: fix roles/special tokens now; mask loss on prompt tokens; pack conversations.

### 9.2 Preference optimization

- **RLHF with PPO**: Christiano et al., 2017 (preferences); Stiennon et al., 2020 (summarization); InstructGPT [Ouyang et al., 2022]. Powerful, operationally heavy (4 models in memory: policy, ref, RM, value).
- **DPO** [Rafailov et al., 2023]: directly optimizes the preference objective, no RM/PPO loop — the default for most teams. Variants: IPO, KTO [Ethayarajh et al., 2024] (works from binary good/bad labels — practical for domain SME feedback), ORPO, SimPO.
- **RLAIF / Constitutional AI** [Bai et al., 2022]: AI feedback against a written constitution — attractive in regulated domains because the "constitution" can encode policy (e.g., MiFID II suitability language, medical-advice boundaries) explicitly and auditable.
- Zephyr [Tunstall et al., 2023]: reference open recipe — distilled SFT + DPO on UltraFeedback.

### 9.3 Reasoning (RLVR)

- **DeepSeek-R1** [DeepSeek-AI, 2025]: large-scale RL with verifiable rewards (GRPO [Shao et al., 2024]) elicits chain-of-thought reasoning; distillation transfers it to SLMs. For domains with checkable answers (quant math, code, rules-based compliance), RLVR on your own verifiers is now a realistic in-house technique.
- Process supervision [Lightman et al., 2023, "Let's Verify Step by Step"] for step-level reward models.

### 9.4 Domain post-training checklist

- Tool-use/function-calling data for your real APIs (order systems, EHR queries, market-data feeds).
- Grounded-generation training: answers must cite retrieved passages → pairs naturally with RAG at inference.
- Refusal & escalation behavior encoded per your compliance policy; red-team prompts in the preference set.

---

## 10. Evaluation

### 10.1 Layers of evaluation

1. **Intrinsic**: held-out perplexity (domain + general), token-level calibration.
2. **General benchmarks** (guard against regression): MMLU [Hendrycks et al., 2020], MMLU-Pro, GSM8K [Cobbe et al., 2021], HumanEval [Chen et al., 2021], BBH [Suzgun et al., 2022], IFEval [Zhou et al., 2023b] (instruction following), GPQA [Rein et al., 2023].
3. **Domain benchmarks**: FinanceBench [Islam et al., 2023], FinQA/ConvFinQA (finance); MedQA/USMLE, PubMedQA, MultiMedQA suite [Singhal et al., 2022] (medical); LegalBench [Guha et al., 2023] (law); SWE-bench [Jimenez et al., 2023] (software).
4. **Custom evals — the real moat**: 200–1,000 golden tasks written with domain SMEs, versioned, with rubric scoring. This is the artifact regulators and stakeholders will actually trust.
5. **LLM-as-judge**: MT-Bench / Chatbot Arena methodology [Zheng et al., 2023]; mitigate position, verbosity, and self-preference biases; sample-audit with humans.

### 10.2 Hygiene

- Decontaminate training data against *every* reported benchmark (§3.2) and disclose methodology; contamination analysis à la GPT-4 tech report [OpenAI, 2023].
- Report variance across seeds/prompts; use standardized harnesses (**lm-evaluation-harness** [Gao et al., EleutherAI], HELM [Liang et al., 2022]).
- Safety evals: HarmBench, domain red-teaming (prompt-injection on tool-connected deployments — OWASP LLM Top 10).

---

## 11. Compression & Inference

### 11.1 Quantization

- **Post-training**: GPTQ [Frantar et al., 2022] (4-bit, second-order), **AWQ** [Lin et al., 2023] (activation-aware, robust default), GGUF/llama.cpp K-quants for CPU/edge, FP8 (native on H100/Blackwell, near-lossless), SmoothQuant [Xiao et al., 2022] for W8A8.
- **Quantized fine-tuning**: **QLoRA** [Dettmers et al., 2023] — NF4 base + LoRA adapters; fine-tune a 70B on a single 80GB GPU.
- Rule of thumb: 4-bit weight-only costs ~0.5–2 benchmark points on 7B+ models; SLMs (<3B) degrade more — prefer 5–8 bit or QAT there.

### 11.2 Serving

- **vLLM** with **PagedAttention** [Kwon et al., 2023] — continuous batching, prefix caching; **SGLang** (RadixAttention) for agentic/structured workloads; **TensorRT-LLM** for max NVIDIA throughput; llama.cpp/Ollama for edge & air-gapped on-prem (common BFSI requirement).
- **Speculative decoding** [Leviathan et al., 2022; Chen et al., 2023b]: 2–3× latency win with a small drafter — your domain SLM can draft for your domain LLM. Medusa [Cai et al., 2024], EAGLE for head-based variants.
- KV-cache economics dominate long-context serving: GQA/MLA at architecture time (§5) is what makes 128k-context contract analysis affordable.
- Everything above is training/architecture-side. For the deployment-side
  question — which GPU to provision, self-host-vs-API cost math, batching/
  KV-cache/quantization tuning at serve time, and GPU-level troubleshooting
  and observability — see
  [notes/21_hardware_gpu_inference_and_observability.md](./notes/21_hardware_gpu_inference_and_observability.md).

---

## 12. Safety, Governance & Compliance

Directly relevant for EU deployment (BaFin/DORA/MiFID II context):

- **EU AI Act (Reg. 2024/1689)**: GPAI model obligations applied from **Aug 2, 2025** — technical documentation, a public summary of training content, copyright policy (Art. 53); systemic-risk tier at ≥10²⁵ FLOPs training compute (Art. 51–55) — most domain SLMs fall far below, but documentation duties still apply if you place a GPAI model on the EU market. High-risk *system* obligations (Annex III — credit scoring, essential services) attach to the application layer from Aug 2026. The **GPAI Code of Practice** (2025) is the practical compliance template.
- Your training pipeline should emit compliance artifacts as a by-product: data-provenance manifests, dedup/PII logs, eval reports, model card [Mitchell et al., 2019] and datasheets [Gebru et al., 2018].
- **Memorization & privacy**: training-data extraction attacks are real [Carlini et al., 2021, 2023]; dedup (§3.2) is the primary mitigation; DP-SGD where warranted.
- Financial services: model risk management alignment (SR 11-7 style validation, ECB TRIM expectations) — independent validation of your eval suite, challenger models, monitoring & drift detection in production.
- Security: OWASP Top 10 for LLM Applications (prompt injection, insecure output handling, training-data poisoning) — poisoning matters if you ingest user/partner data into continued-pretraining loops.

---

## 13. Cost Models, Reference Stack & Roadmap

### 13.1 Reference stack (opinionated)

| Layer | Tools |
|---|---|
| Data | datatrove, Dolma toolkit, NeMo Curator, Spark; DVC/lakeFS for versioning |
| Tokenizer | HF tokenizers, SentencePiece |
| Pretraining | Megatron-Core / torchtitan / GPT-NeoX / LitGPT; nanoGPT for ablations |
| Post-training | HF TRL (SFT/DPO/GRPO), Axolotl, OpenRLHF, Unsloth (fast LoRA) |
| Eval | lm-evaluation-harness, HELM, custom golden-set harness, promptfoo |
| Serving | vLLM / SGLang / TensorRT-LLM; llama.cpp for edge |
| Observability | W&B or MLflow (training), Langfuse/OpenTelemetry (inference), drift monitors |

### 13.2 A pragmatic 12-month roadmap (domain SLM, team of 4–8)

1. **M1–2 — Strategy & data audit**: ADR on rung selection (§1); inventory unique domain tokens; legal review of sources; build eval golden set v0 with SMEs.
2. **M2–4 — Data pipeline**: extraction → filtering → dedup → decontamination; tokenizer study (fertility analysis); publish internal datasheet.
3. **M3–5 — Ablation season**: 100–400M-param proxy runs on mix/tokenizer/architecture variants (μP transfer); pick the config with eval evidence.
4. **M5–8 — Main run**: DAPT of an 7–8B base (default) *or* from-scratch 1–3B SLM (if §1 criteria met); annealing phase on best data; checkpoint evals throughout.
5. **M8–10 — Post-training**: SFT (SME-verified data) → DPO/KTO on domain preferences → optional RLVR if you have verifiers; safety/refusal tuning.
6. **M10–12 — Productionization**: quantization study, vLLM/edge deployment, RAG integration with citation grounding, monitoring, model card + AI-Act documentation pack, SR 11-7-style validation report.

Continuous: quarterly data-refresh + annealing "checkpoint uplift" runs rather than yearly full retrains.

### 13.3 Where teams actually fail

1. Skipping the ADR and training from scratch for prestige. 2. No decontamination → eval story collapses in diligence. 3. DAPT without replay → base capabilities destroyed. 4. No SME golden set → "benchmarks up, users unhappy." 5. Tokenizer chosen by default → permanent inference tax. 6. Underestimating post-training (it's ~40% of the effort). 7. No provenance logging → AI-Act documentation retrofit is 10× the cost.

---

## 14. Master Reference List

### Foundations & scaling
- Vaswani et al., 2017 — *Attention Is All You Need* — arxiv.org/abs/1706.03762
- Radford et al., 2019 — *GPT-2: Language Models are Unsupervised Multitask Learners* (OpenAI)
- Brown et al., 2020 — *GPT-3: Language Models are Few-Shot Learners* — arxiv.org/abs/2005.14165
- Kaplan et al., 2020 — *Scaling Laws for Neural Language Models* — arxiv.org/abs/2001.08361
- Hoffmann et al., 2022 — *Training Compute-Optimal LLMs (Chinchilla)* — arxiv.org/abs/2203.15556
- Muennighoff et al., 2023 — *Scaling Data-Constrained Language Models* — arxiv.org/abs/2305.16264
- Chowdhery et al., 2022 — *PaLM* — arxiv.org/abs/2204.02311
- Yang et al., 2022 — *Tensor Programs V: μTransfer* — arxiv.org/abs/2203.03466

### Open model families & reports
- Touvron et al., 2023 — *LLaMA* — arxiv.org/abs/2302.13971; *Llama 2* — arxiv.org/abs/2307.09288
- Grattafiori et al., 2024 — *The Llama 3 Herd of Models* — arxiv.org/abs/2407.21783
- Jiang et al., 2023 — *Mistral 7B* — arxiv.org/abs/2310.06825; *Mixtral of Experts* — arxiv.org/abs/2401.04088
- Qwen Team, 2024 — *Qwen2.5 Technical Report* — arxiv.org/abs/2412.15115
- Gemma Team, 2024 — *Gemma 2* — arxiv.org/abs/2408.00118
- DeepSeek-AI, 2024 — *DeepSeek-V3* — arxiv.org/abs/2412.19437
- DeepSeek-AI, 2025 — *DeepSeek-R1* — arxiv.org/abs/2501.12948
- Groeneveld et al., 2024 — *OLMo* — arxiv.org/abs/2402.00838 (OLMo 2: arxiv.org/abs/2501.00656)
- Biderman et al., 2023 — *Pythia* — arxiv.org/abs/2304.01373
- OpenAI, 2023 — *GPT-4 Technical Report* — arxiv.org/abs/2303.08774

### SLMs
- Gunasekar et al., 2023 — *Textbooks Are All You Need (phi-1)* — arxiv.org/abs/2306.11644
- Abdin et al., 2024 — *Phi-3* — arxiv.org/abs/2404.14219; *Phi-4* — arxiv.org/abs/2412.08905
- Zhang et al., 2024 — *TinyLlama* — arxiv.org/abs/2401.02385
- Allal et al., 2025 — *SmolLM2* — arxiv.org/abs/2502.02737
- Liu et al., 2024 — *MobileLLM* — arxiv.org/abs/2402.14905
- Hu et al., 2024 — *MiniCPM (WSD schedule)* — arxiv.org/abs/2404.06395
- Xia et al., 2023 — *Sheared LLaMA* — arxiv.org/abs/2310.06694
- Muralidharan et al., 2024 — *Compact LMs via Pruning & Distillation (Minitron)* — arxiv.org/abs/2407.14679
- Hinton et al., 2015 — *Distilling the Knowledge in a Neural Network* — arxiv.org/abs/1503.02531
- Gu et al., 2023 — *MiniLLM* — arxiv.org/abs/2306.08543

### Data
- Gao et al., 2020 — *The Pile* — arxiv.org/abs/2101.00027
- Raffel et al., 2020 — *T5 / C4* — arxiv.org/abs/1910.10683
- Penedo et al., 2023 — *RefinedWeb* — arxiv.org/abs/2306.01116
- Penedo et al., 2024 — *FineWeb* — arxiv.org/abs/2406.17557
- Soldaini et al., 2024 — *Dolma* — arxiv.org/abs/2402.00159
- Lozhkov et al., 2024 — *StarCoder 2 & The Stack v2* — arxiv.org/abs/2402.19173
- Lee et al., 2021 — *Deduplicating Training Data Makes LMs Better* — arxiv.org/abs/2107.06499
- Rae et al., 2021 — *Gopher (quality heuristics)* — arxiv.org/abs/2112.11446
- Xie et al., 2023 — *DoReMi* — arxiv.org/abs/2305.10429
- Shumailov et al., 2024 — *The Curse of Recursion (model collapse)* — arxiv.org/abs/2305.17493
- Gebru et al., 2018 — *Datasheets for Datasets* — arxiv.org/abs/1803.09010

### Tokenization
- Sennrich et al., 2016 — *BPE for NMT* — arxiv.org/abs/1508.07909
- Kudo, 2018 — *Subword Regularization (Unigram)* — arxiv.org/abs/1804.10959
- Kudo & Richardson, 2018 — *SentencePiece* — arxiv.org/abs/1808.06226
- Bavarian et al., 2022 — *FIM (fill-in-the-middle)* — arxiv.org/abs/2207.14255

### Architecture
- Su et al., 2021 — *RoFormer (RoPE)* — arxiv.org/abs/2104.09864
- Zhang & Sennrich, 2019 — *RMSNorm* — arxiv.org/abs/1910.07467
- Shazeer, 2020 — *GLU Variants (SwiGLU)* — arxiv.org/abs/2002.05202
- Ainslie et al., 2023 — *GQA* — arxiv.org/abs/2305.13245
- Dao et al., 2022 — *FlashAttention* — arxiv.org/abs/2205.14135; *FlashAttention-2* — arxiv.org/abs/2307.08691
- Peng et al., 2023 — *YaRN* — arxiv.org/abs/2309.00071
- Fedus et al., 2021 — *Switch Transformers* — arxiv.org/abs/2101.03961
- Gu & Dao, 2023 — *Mamba* — arxiv.org/abs/2312.00752
- Lieber et al., 2024 — *Jamba* — arxiv.org/abs/2403.19887

### Distributed training
- Shoeybi et al., 2019 — *Megatron-LM* — arxiv.org/abs/1909.08053
- Narayanan et al., 2021 — *Efficient Large-Scale Training (Megatron 3D)* — arxiv.org/abs/2104.04473
- Rajbhandari et al., 2020 — *ZeRO* — arxiv.org/abs/1910.02054

### Domain models
- Gururangan et al., 2020 — *Don't Stop Pretraining (DAPT/TAPT)* — arxiv.org/abs/2004.10964
- Ibrahim et al., 2024 — *Continual Pre-training Strategies* — arxiv.org/abs/2403.08763
- Wu et al., 2023 — *BloombergGPT* — arxiv.org/abs/2303.17564
- Araci, 2019 — *FinBERT* — arxiv.org/abs/1908.10063
- Yang et al., 2023 — *FinGPT* — arxiv.org/abs/2306.06031
- Luo et al., 2022 — *BioGPT* — arxiv.org/abs/2210.10341
- Singhal et al., 2022 — *Med-PaLM / MultiMedQA* — arxiv.org/abs/2212.13138; *Med-PaLM 2* — arxiv.org/abs/2305.09617
- Chen et al., 2023 — *MEDITRON-70B* — arxiv.org/abs/2311.16079
- Chen et al., 2021 — *Codex / HumanEval* — arxiv.org/abs/2107.03374
- Rozière et al., 2023 — *Code Llama* — arxiv.org/abs/2308.12950
- Li et al., 2023 — *StarCoder* — arxiv.org/abs/2305.06161
- Guo et al., 2024 — *DeepSeek-Coder* — arxiv.org/abs/2401.14196
- Taylor et al., 2022 — *Galactica* — arxiv.org/abs/2211.09085
- Colombo et al., 2024 — *SaulLM-7B* — arxiv.org/abs/2403.03883
- Lin et al., 2022 — *ESM-2 protein LM* — science.org/doi/10.1126/science.ade2574

### Post-training & alignment
- Wei et al., 2021 — *FLAN* — arxiv.org/abs/2109.01652; Chung et al., 2022 — *Scaling Instruction-Finetuned LMs* — arxiv.org/abs/2210.11416
- Ouyang et al., 2022 — *InstructGPT (RLHF)* — arxiv.org/abs/2203.02155
- Christiano et al., 2017 — *Deep RL from Human Preferences* — arxiv.org/abs/1706.03741
- Stiennon et al., 2020 — *Learning to Summarize from Human Feedback* — arxiv.org/abs/2009.01325
- Rafailov et al., 2023 — *DPO* — arxiv.org/abs/2305.18290
- Ethayarajh et al., 2024 — *KTO* — arxiv.org/abs/2402.01306
- Bai et al., 2022 — *Constitutional AI* — arxiv.org/abs/2212.08073
- Zhou et al., 2023 — *LIMA* — arxiv.org/abs/2305.11206
- Wang et al., 2022 — *Self-Instruct* — arxiv.org/abs/2212.10560
- Xu et al., 2023 — *WizardLM / Evol-Instruct* — arxiv.org/abs/2304.12244
- Mukherjee et al., 2023 — *Orca* — arxiv.org/abs/2306.02707
- Tunstall et al., 2023 — *Zephyr* — arxiv.org/abs/2310.16944
- Shao et al., 2024 — *DeepSeekMath (GRPO)* — arxiv.org/abs/2402.03300
- Lightman et al., 2023 — *Let's Verify Step by Step* — arxiv.org/abs/2305.20050

### PEFT & compression
- Hu et al., 2021 — *LoRA* — arxiv.org/abs/2106.09685
- Dettmers et al., 2023 — *QLoRA* — arxiv.org/abs/2305.14314
- Frantar et al., 2022 — *GPTQ* — arxiv.org/abs/2210.17323
- Lin et al., 2023 — *AWQ* — arxiv.org/abs/2306.00978
- Xiao et al., 2022 — *SmoothQuant* — arxiv.org/abs/2211.10438

### Inference
- Kwon et al., 2023 — *vLLM / PagedAttention* — arxiv.org/abs/2309.06180
- Leviathan et al., 2022 — *Speculative Decoding* — arxiv.org/abs/2211.17192
- Chen et al., 2023b — *Speculative Sampling* — arxiv.org/abs/2302.01318
- Cai et al., 2024 — *Medusa* — arxiv.org/abs/2401.10774

### Evaluation
- Hendrycks et al., 2020 — *MMLU* — arxiv.org/abs/2009.03300
- Cobbe et al., 2021 — *GSM8K* — arxiv.org/abs/2110.14168
- Suzgun et al., 2022 — *BIG-Bench Hard* — arxiv.org/abs/2210.09261
- Rein et al., 2023 — *GPQA* — arxiv.org/abs/2311.12022
- Zhou et al., 2023b — *IFEval* — arxiv.org/abs/2311.07911
- Islam et al., 2023 — *FinanceBench* — arxiv.org/abs/2311.11944
- Guha et al., 2023 — *LegalBench* — arxiv.org/abs/2308.11462
- Jimenez et al., 2023 — *SWE-bench* — arxiv.org/abs/2310.06770
- Zheng et al., 2023 — *MT-Bench / LLM-as-Judge* — arxiv.org/abs/2306.05685
- Liang et al., 2022 — *HELM* — arxiv.org/abs/2211.09110

### Safety, privacy & governance
- Carlini et al., 2021 — *Extracting Training Data from LMs* — arxiv.org/abs/2012.07805
- Carlini et al., 2023 — *Quantifying Memorization* — arxiv.org/abs/2202.07646
- Mitchell et al., 2019 — *Model Cards* — arxiv.org/abs/1810.03993
- EU AI Act — Regulation (EU) 2024/1689 — eur-lex.europa.eu (32024R1689); GPAI Code of Practice — digital-strategy.ec.europa.eu
- OWASP Top 10 for LLM Applications — owasp.org/www-project-top-10-for-large-language-model-applications

### Learning resources
- Karpathy — *nanoGPT* & *Let's build GPT* — github.com/karpathy/nanoGPT
- EleutherAI — *lm-evaluation-harness*, *GPT-NeoX* — github.com/EleutherAI
- HF — *FineWeb blog* (data recipes), *smol-course*, *nanotron*; AI2 — *OLMo* open logs/configs
- Raschka, 2024 — *Build a Large Language Model (From Scratch)* (Manning)

---

*End of guide. Verify arXiv IDs when citing formally; all references are primary sources current to early 2026.*

# The Instrumented Service Layer

### A build spec for the one architectural decision the rest of the stack keeps pointing to

*Part of [The FDE Playbook](./README.md). Feeds [The Governance Playbook](./governance-playbook.md)'s governance hooks, the [EU AI Act guide](./eu-ai-act.md)'s Article 12/14/15/50 obligations, and the [eval harness](./eval-harness.md).*

> Three other docs in this stack call this "the single highest-leverage architectural choice you make" and stop there. This is where it actually gets built. The idea in one sentence: **every model call in your product flows through one path**, and that path is where you get observability, cost control, evals, guardrails, and compliance — as a side effect of good engineering, not as separate projects bolted on later.

---

## Why one layer, not many

Without it, every feature that calls a model reinvents logging, retries, and guardrails slightly differently — and you can't answer "what did we actually send the model last Tuesday" without grepping five codebases. With it, that question is one query. The layer is the load-bearing wall; everything else is a room you can renovate without touching it.

**The rule:** if a line of code constructs a prompt or calls `chat.completions` (or equivalent) outside this layer, that's a bug, not a shortcut.

---

## The shape

```
  client request
        │
        ▼
  ┌─────────────────────────────────────────────────────┐
  │                   GATEWAY                            │
  │  auth · rate limit · tenant isolation                │
  └───────────────────────┬─────────────────────────────┘
                           ▼
  ┌─────────────────────────────────────────────────────┐
  │              INPUT GUARDRAILS                        │
  │  PII redaction · prompt-injection screen · policy     │
  └───────────────────────┬─────────────────────────────┘
                           ▼
  ┌─────────────────────────────────────────────────────┐
  │           MODEL ROUTER + REGISTRY                    │
  │  model/prompt version · provider · fallback chain     │
  └───────────────────────┬─────────────────────────────┘
                           ▼
                    [ model call ]
                           │
                           ▼
  ┌─────────────────────────────────────────────────────┐
  │              OUTPUT GUARDRAILS                       │
  │  validation · policy check · confidence threshold      │
  └───────────────────────┬─────────────────────────────┘
                           ▼
  ┌─────────────────────────────────────────────────────┐
  │        LOGGING + OBSERVABILITY (async, immutable)     │
  │  input/output · versions · cost · latency · scores    │
  └───────────────────────┬─────────────────────────────┘
                           ▼
                    response to client
                           │
                           └──► EVAL SAMPLING (async, off critical path)
```

Everything below the gateway is invisible to the caller — a feature team calls one internal API and inherits the whole stack.

---

## Core components, what each one does, and what it satisfies

| Component | What it does | What it buys you elsewhere in this stack |
|---|---|---|
| **Gateway / unified call path** | Single entry point for every model call; auth, rate limiting, tenant isolation | The substrate everything else attaches to |
| **Model router + registry** | Resolves logical name → concrete model/prompt version, handles fallback chains | Change management, technical documentation ([EU AI Act](./eu-ai-act.md) Art 11) |
| **Input guardrails** | PII redaction, prompt-injection screening, policy checks before the model sees anything | Data governance, robustness |
| **Output guardrails** | Schema/format validation, policy checks, confidence thresholds before the caller sees anything | Robustness, safety (Art 15) |
| **Immutable audit log** | Every input, output, model+prompt version, timestamp, score, override — written async, never mutated | Traceability (Art 12), incident forensics, the [discovery toolkit](./discovery-toolkit.md)'s "what happened" answer |
| **Human-in-the-loop hooks** | Surface confidence/explanation, override control, anti-automation-bias nudges | Human oversight (Art 14) |
| **Eval sampling hook** | A percentage (or all) of traffic gets scored against the [eval harness](./eval-harness.md), off the critical path | Continuous quality signal without adding latency |
| **Cost + latency instrumentation** | Per-request token count, cost, latency, tagged by feature/tenant | Unit economics, the thing that makes or breaks a use case |
| **Data-governance plane** | Residency routing, retention policy, consent state | GDPR/DPDP-class regimes |

Build the **gateway + logging + eval hook** first. They're the three that are both good engineering on day one and the ones every later requirement attaches to.

---

## The request lifecycle, concretely

1. **Request arrives** at the gateway with a tenant ID and a logical model name (`"support-classifier"`, not `"gpt-x-version-y"`).
2. **Auth + rate limit** resolve, tenant isolation applied.
3. **Input guardrails** run: redact PII, screen for injection patterns, reject if policy violated — reject *before* spending a model call.
4. **Router** resolves the logical name to a concrete model + prompt version via the registry, and picks a fallback if the primary is degraded.
5. **Model call** happens. This is the one part that's "just" an API call — everything around it is the actual engineering.
6. **Output guardrails** run: validate shape, check policy, check confidence; low-confidence responses route to human review instead of the caller.
7. **Response returns** to the caller. Latency budget for this whole path should be a number you know, not a guess.
8. **Async logging** writes the full record — this must not block the response.
9. **Async eval sampling** scores a slice of traffic against the golden set's rubric, feeding the dashboard, not the request.

The word "async" appears three times on purpose: nothing downstream of the response should add latency the user feels.

---

## Minimal interface shape

Language-agnostic, but concretely, the contract a feature team calls looks like this:

```
interface ModelCall {
  logicalName: string          // "support-classifier", not a raw model id
  tenantId: string
  input: Record<string, any>
  context?: { userId?: string; sessionId?: string }
}

interface ModelResponse {
  output: Record<string, any>
  modelVersion: string
  promptVersion: string
  confidence?: number
  guardrailFlags: string[]     // empty if clean
  requestId: string            // the key into the audit log
}
```

A feature team never sees a raw provider SDK. That constraint is what keeps the layer from eroding — the moment someone can bypass it "just this once," the audit log has a hole in it.

---

## Build sequence

1. **Gateway with a single logical-name → model mapping.** Even one model behind one name is worth doing on day one.
2. **Immutable async logging**, before you need it for compliance — retrofitting logs onto six months of undocumented traffic is the expensive version of this.
3. **Input/output guardrails**, starting with the guardrails your riskiest use case needs, not a generic library.
4. **Eval sampling hook** — even a stub that logs to a queue is enough to start; the [eval harness](./eval-harness.md) consumes this.
5. **Model registry + versioning** once you have more than one prompt version in flight — usually within the first month.
6. **Cost/latency dashboards** as soon as a second feature team starts calling the layer, because that's when "whose cost is this" becomes a real question.

---

## Anti-patterns

- **Bypassing the gateway "just for this one internal tool."** The internal tool is the one that leaks a prompt-injection into production, because nobody thought to guardrail the trusted path.
- **Synchronous logging that blocks the response.** Logging failures should never become user-facing latency or errors.
- **A registry with no rollback.** If you can promote a prompt version, you must be able to demote it in one action, not a redeploy.
- **Guardrails as an afterthought library dropped in pre-launch.** Guardrails tuned under deadline pressure are guardrails tuned to pass the demo, not stop the incident.
- **Building all nine components before anyone calls the layer.** Ship gateway + logging + one guardrail, get real traffic, then harden.

---

## One-page quick reference

**The rule:** every model call flows through one path — no exceptions, no "just this once."

**Build first:** gateway → immutable async logging → eval sampling hook. These three are both good engineering and the load-bearing compliance pieces.

**The lifecycle:** auth → input guardrails → route → model call → output guardrails → respond → (async) log + eval sample.

**The interface a feature team sees:** a logical name and a typed response — never a raw provider SDK.

**The payoff:** compliance, observability, cost control, and eval coverage become properties of the architecture, not separate projects you have to remember to do.

> The whole thing in a sentence: **build the layer once, and every obligation downstream — logging, oversight, evals, cost, compliance — becomes configuration instead of a rebuild.**

---

*Back to [The FDE Playbook](./README.md) · [The Governance Playbook](./governance-playbook.md) · [Eval Harness Guide](./eval-harness.md)*

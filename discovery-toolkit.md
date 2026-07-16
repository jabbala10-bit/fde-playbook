# The Discovery Toolkit

### Fillable templates for the discovery and scoping stages

*Part of [The FDE Playbook](./README.md). Turns the discovery-stage prose in that doc and the [Governance Playbook](./governance-playbook.md)'s question set into artifacts you actually fill out with a customer in the room.*

> The other docs in this stack *describe* the stakeholder map, the use-case scoring rubric, and the governance question set. This is where you copy-paste and fill them in during an actual discovery session. Nothing here is new thinking — it's the same frameworks, made usable.

---

## 1. Use-case scoring rubric

Score every candidate use case you surface in discovery. Fill one row per use case; rank by total score before picking the wedge.

| Use case | Value (1–5) | Feasibility (1–5) | Visibility (1–5) | Total | Notes |
|---|---|---|---|---|---|
| _e.g. Automate tier-1 support triage_ | | | | | |
| | | | | | |
| | | | | | |

**Scoring guide:**

- **Value (1–5):** 1 = nice-to-have, 5 = measurably moves a metric the economic buyer already cares about.
- **Feasibility (1–5):** 1 = needs data/access/integration you don't have yet, 5 = you could prototype it this week with data you already have.
- **Visibility (1–5):** 1 = only one person will notice it shipped, 5 = the whole org will see it and it becomes the reference story for expansion.

**The wedge is the highest-total row you can actually de-risk fastest** — not necessarily the highest value alone. A 5/5/5 that needs six months of data-access negotiation loses to a 4/4/4 you can prove in a week.

---

## 2. Stakeholder map

| Name | Role | Type | What they need from you | Risk if ignored |
|---|---|---|---|---|
| | | Champion | | |
| | | Economic buyer | | |
| | | Blocker (security/legal/skeptic) | | |
| | | End user | | |

**Type definitions** (from the [FDE Playbook](./README.md)'s customer-facing craft):

- **Champion** — wants you to win, will advocate internally when you're not in the room.
- **Economic buyer** — controls budget, cares about ROI and risk, usually not in the weekly syncs.
- **Blocker** — security, legal, or a skeptical end user; their objection can stop the deal if not addressed early.
- **End user** — whose actual adoption is the real test; the demo means nothing if they don't use it.

Fill this in before you pick the wedge — the highest-scored use case on the rubric above is worthless if its champion has no influence and its blocker hasn't been identified yet.

---

## 3. Governance discovery checklist

Run this alongside the use-case scoring, not after — a governance red flag can eliminate a use case from the rubric entirely. Full context on each question is in [The Governance Playbook](./governance-playbook.md); this is the fillable version.

**Jurisdiction & reach**
- [ ] Countries the users are in:
- [ ] Where data is stored/processed:
- [ ] Cross-border transfer involved? Data-residency requirement?

**Use case & risk tier**
- [ ] What decision does the system make or influence, and about whom?
- [ ] High-stakes domain (hiring, credit, healthcare, biometrics, education, law enforcement, critical infra)? Y/N —
- [ ] Could this read as manipulation, social scoring, or emotion/biometric inference? Y/N —
- [ ] Human in the loop, or fully automated?

**Data**
- [ ] Personal data involved? Special-category data?
- [ ] Children's/minors' data involved?
- [ ] Lawful basis for training + runtime data:
- [ ] Data lineage — source of training/context data, rights confirmed?

**Roles & responsibility**
- [ ] Are we provider or deployer here?
- [ ] Who signs off on risk acceptance on the customer side?

**Model & capability**
- [ ] Own model / hosted API / fine-tune?
- [ ] Acceptable-use policy of the model provider — can this use case violate it?
- [ ] Blast radius if wrong, jailbroken, or misused:

**Deployment & operations**
- [ ] Logging/monitoring/human-override needed:
- [ ] Incident path when it fails in production:
- [ ] Existing framework the customer runs (ISO 42001 / NIST / none):

**Outcome of this checklist:** ☐ Clear to proceed  ☐ Proceed with flagged mitigations  ☐ Escalate to counsel before building

---

## 4. Definition of done

Fill this out at the end of scoping, before any code is written. This is what "it works" means, agreed in writing before the demo — not decided retroactively when the customer asks if it's done.

| Field | Your answer |
|---|---|
| Success metric (the number that must move) | |
| Target value | |
| Measurement method (which eval, which dashboard — see the [eval harness](./eval-driven-development.md)) | |
| Who signs off that it's met | |
| What's explicitly out of scope | |
| Known risks / governance flags carried forward | |

---

## 5. Running the discovery session

- **Ask more than you tell.** The problem the customer states first is rarely the highest-value one — the sharpest questions come from listening, not pitching.
- **Fill the stakeholder map live**, even roughly — asking "who else should be thinking about this" in the room surfaces blockers you'd otherwise meet for the first time in week six.
- **Run the governance checklist in the same session**, not as a follow-up email — a red flag found in week one is a redesign; found in month three, it's a write-off.
- **Leave with the use-case table scored**, even if scoring is provisional — an unscored list of ideas is not an artifact, it's notes.

---

## One-page quick reference

**Fill in this order:** stakeholder map (who's in the room and who should be) → use-case scoring (what's worth doing) → governance checklist (what's actually allowed) → definition of done (what "finished" means, in writing).

**The wedge:** highest total score you can de-risk fastest — not just the highest value.

**The governance checklist can eliminate a use case outright** — run it *during* scoring, not after you've already picked the wedge.

> The whole thing in a sentence: **discovery produces artifacts, not impressions — leave the room with a scored table, a stakeholder map, a governance answer, and a written definition of done.**

---

*Back to [The FDE Playbook](./README.md) · [The Governance Playbook](./governance-playbook.md) · [Eval Harness Guide](./eval-driven-development.md)*

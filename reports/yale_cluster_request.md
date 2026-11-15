# Yale HPC Access — How To Actually Get It (Bouchet, under Prof. Kelly)

*Thesis: News Shocks and Prediction-Market Price Formation · advisor/PI: Prof. Bryan Kelly*
*Revised 2026-09-05 after checking the YCRC process directly. Supersedes the earlier justification-memo draft, which named the wrong cluster (McCleary) and misframed the process.*

> **TL;DR:** There is no "proposal" to write. The student submits a short YCRC account-request form
> naming Kelly as PI; YCRC auto-emails Kelly; Kelly clicks/replies to confirm; the account exists in
> 1–2 business days. The right cluster is **Bouchet**, not McCleary.

---

## 1. Which cluster
- **Bouchet** — Yale's primary shared-use HPC cluster, the successor to **Grace** (FAS, being
  decommissioned in 2026) and **McCleary** (life-sciences/YCGA). Bouchet is general-purpose and
  serves all disciplines, so it's the correct fit for a School of Management / finance project.
- **Not McCleary** (life-sciences/genomics eligibility) and **not Grace** (FAS-only, retiring 2026;
  new accounts only for groups with dedicated nodes).
- Hardware on Bouchet includes RTX 5000 Ada (32 GB), H100 (80 GB), H200 (141 GB), B200 GPUs — far
  more than this project needs (a single GPU suffices).

## 2. The exact process
1. **Student submits** the YCRC account-request form: <https://research.computing.yale.edu/account-request>
   (redirects to a Google Form). Name **Bryan Kelly** as the PI/sponsor.
2. **YCRC auto-emails the PI (Kelly)** a confirmation request.
3. **Kelly replies/approves** that email — this is the only action required of him.
4. **Account is created in 1–2 business days.** On Bouchet your *primary* group is your NetID; the
   Kelly PI group is attached as a *secondary* group (use `--account=<kelly_group>` in Slurm).
5. **Log in** via SSH or the Open OnDemand portal: <https://ood-bouchet.ycrc.yale.edu>.

> Practical note from the YCRC docs: *"check with your PI as soon as you submit"* — the request only
> advances once Kelly answers the confirmation email, so give him a heads-up (the email below does that).

## 3. What to confirm with Kelly (the only real dependencies)
- **He has a YCRC PI group.** Faculty are granted a PI group account on request; as a computational
  finance PI he very likely already has one. If not, he (as faculty) requests it once from YCRC —
  quick, and it's his action, not the student's.
- **He's OK being named as sponsor** and will approve the auto-confirmation email.

## 4. What to put in the form's "research description" (short, factual)
> Senior finance thesis under Prof. Bryan Kelly on news-shock price formation in Polymarket
> prediction markets. Compute needs: embedding passes (sentence-transformers on one GPU), 1-minute
> log-odds bar resampling (multi-core CPU), and later small model training. Bursty usage, a few
> GPU-hours/week, ~200 GB storage. No PHI/HIPAA data.

## 5. Resource reality (so we know a standard allocation is enough)
- **One GPU** (any Bouchet GPU) for the BGE/E5 embedding passes — the ~11 h local MPS pass drops to
  well under an hour.
- **A CPU node, 32–64 GB RAM** for trade→bar resampling.
- **~200 GB** project/scratch storage. A standard Bouchet allocation covers all of this; no special
  hardware or dedicated-node request is needed.

## 6. Where this sits in the plan
Access is a **1–2 day** turnaround once Kelly confirms, so submitting the form now removes it from
the critical path. It does **not** by itself unblock the core deliverable — that still needs the
trade-source decision (`reports/trade_source_decision.md`). Until the account lands, the GPU stages
run on Colab (`reports/colab_offload_plan.md`).

---

**Sources:** [YCRC account request](https://research.computing.yale.edu/support/hpc/account-request) ·
[YCRC accounts & PI groups](https://docs.ycrc.yale.edu/clusters-at-yale/access/accounts/) ·
[Bouchet cluster](https://docs.ycrc.yale.edu/clusters/bouchet/) ·
[Grace (decommissioning 2026)](https://docs.ycrc.yale.edu/clusters/grace/) ·
[McCleary (life-sciences)](https://docs.ycrc.yale.edu/clusters/mccleary/)

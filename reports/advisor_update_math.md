# Advisor Update — The New Math (Two Method Threads)

*For: Prof. Bryan Kelly · Thesis: News Shocks and Prediction-Market Price Formation · Sept 2026*

Both threads are designed to be methodological contributions (per the DUS requirement), not off-the-shelf applications. Notation is grounded in what the pipeline already computes: prices enter in **log-odds** units, and the scalar reaction target is
$$y^{(\Delta)}_{gj,\tau} \;=\; \operatorname{logit} p_{gj}(\tau+\Delta) - \operatorname{logit} p_{gj}(\tau),$$
computed on prices clipped off $\{0,1\}$.

---

## Thread 1 — Matching as measurable embedding-space structure

**Objects.** Article $a$ has analysis embedding $e_a\in\mathbb R^{d}$ ($d=768$, E5-large). A contract group $g=(c,m)$ (company $c$, expiry month $m$) has a description embedding $e_g$, structured side-information $x_g$ (ticker identity, family, expiry, static liquidity), and liquidity $\ell_g$.

**Model — a learned metric, not cosine.** Cosine similarity assumes the identity metric and cannot be a contribution. Instead learn a bilinear compatibility
$$s(a,g) \;=\; f(e_a;\phi)^\top\, M_\theta\, h(e_g,x_g;\psi), \qquad M_\theta = U V^\top\ (\text{low rank}),$$
$$\Pr(M_{ag}=1\mid a,g)=\sigma\!\big(s(a,g)+\gamma^\top x_g^{\text{struct}}\big),$$
where $h$ **fuses** the contract text with structured metadata (so the same article scores differently against "NVDA above \$180" vs "NVDA CEO resigns" even when the two contract texts embed similarly). Hard structural features (ticker match, publication inside the contract's active window) act as a pre-filter and a soft bias.

**Training signal.** Weak supervision: (S1) deterministic ticker+time hard matches as weighted positives; (S2) different-company / out-of-window pairs as hard negatives; trained with a margin-ranking loss
$$\mathcal L=\sum_a\sum_{g^+}\sum_{g^-}\max\!\big(0,\; s(a,g^-)-s(a,g^+)+\alpha\big).$$

**The novelty — liquidity as an external validation moment, not a feature.** A *genuine* match should be followed by an abnormal market response. Define the abnormal log-odds move $AR^{(\Delta)}_{ag}=y^{(\Delta)}_{gj^\*,\tau_a}-\mu^{(\Delta)}_{f(g)}$ (and analogously abnormal volume $AV$). The validation is the testable moment condition
$$\mathbb E\big[\,|AR^{(\Delta)}_{ag}|\;\big|\;\hat M_{ag}=1\big]\;\gg\;\mathbb E\big[\,|AR^{(\Delta)}_{ag}|\;\big|\;\hat M_{ag}=0\big],$$
evaluated **out-of-sample**, with $AR,AV$ never entering $s(\cdot)$ or the loss. This reframes the event-study logic (information events reveal themselves through abnormal reactions) as an identification check for embedding-space matching.

**Honest flags.** Label sparsity can leave $M_\theta$ weakly identified vs. the cosine null; the ticker pre-filter may already be strong, so the paper must show the learned metric adds economically significant lift; the moment condition is necessary, not sufficient (co-incident news is a confound → needs a competing-article test or instrument).

---

## Thread 2 — Log-odds reaction over the parent/child strike ladder

This is the stronger thread and sits directly in the IPCA lineage.

**The ladder is a market-implied survival function.** For company $c$, expiry $m$, strikes $k_1<\dots<k_J$, child $j$ is the binary "underlying $\ge k_j$ at expiry," so
$$p_{gj}(t)=\Pr^{\mathcal M}(S_{T_m}\ge k_j\mid\mathcal I_t)=\bar F_t(k_j),$$
monotone decreasing in $k_j$ by no-arbitrage; in log-odds $\ell_{gj}(t)=\operatorname{logit}p_{gj}(t)$ inherits $\ell_{g1}\ge\dots\ge\ell_{gJ}$.

**Latent one-factor structure across strikes.**
$$\ell_{gj}(t)=\alpha_{gj}+\beta_{gj}\,\theta_c(t)+u_{gj}(t),\qquad \beta_{gj}=\beta\!\big(k_j/k_{\mathrm{ref},g},\,T_m-t\big).$$
$\theta_c(t)$ is a **latent company state** (the analogue of the IPCA latent factor); $\beta_{gj}$ is the **strike sensitivity** — exactly "how the strikes respond relative to one another," parameterized smoothly in moneyness and maturity (the analogue of characteristic-based loadings).

**A news shock becomes a vector response.** A shock at $\tau$ is an innovation $\varepsilon_{c,\tau}=\theta_c(\tau^+)-\theta_c(\tau^-)$. The scalar target generalizes to the whole ladder:
$$\mathbf y^{(\Delta)}_{g,\tau}=\boldsymbol\beta_g\,\Delta\theta^{(\Delta)}_c+\Delta\mathbf u^{(\Delta)}_g.$$
One shared shock, broadcast through strike-specific betas. Flat $\beta$ = parallel shift; increasing $\beta$ = the shock stretches one tail (re-shapes the implied distribution).

**Reduced-form summaries (computable in EDA, before any estimation).** From the observed ladder alone: implied-median shift $\mu^{(\Delta)}$ (location), inter-quartile-strike change $\sigma^{(\Delta)}$ (dispersion), and the Wasserstein-1 movement $W_1(F_\tau,F_{\tau+\Delta})$ (full shift). These are the first deliverables — they need no structural fit, matching the "look at the data first" directive.

**Three extensions beyond standard IPCA:**
1. **No-arbitrage shape constraint** — the latent ladder is estimated under monotonicity via pool-adjacent-violators isotonic regression, so measurement noise cannot inject arbitrage violations into the reaction target.
2. **Measurement-error / state-space layer** — Polymarket trades are sparse and irregular; observed LOCF log-odds $\tilde\ell=\ell+\eta$ are stale measurements. With $J$ strikes measuring one factor, $\theta_c(t)$ is filtered from the cross-section (noise averages down), with recency/volume weights $w_{gj}(t)$.
3. **Event-time shock identification** — once $\hat\theta_c(t)$ is filtered, $\hat\varepsilon_{c,\tau_a}=\hat\theta_c(\tau_a+\Delta)-\hat\theta_c(\tau_a^-)$ is the market's factored response to the article.

**The payoff regression (links the two threads).** Regress the factored shock on the purged text embedding and the match score:
$$\hat\varepsilon_{c,\tau_a}\;=\;\lambda_0+\lambda_1^\top \varepsilon_a+\lambda_2\, s(a,g)+\text{controls}+\nu,$$
where $\varepsilon_a$ is the purging residual (article embedding minus the part predictable from market characteristics, fit out-of-sample). This "does news text predict the factored log-odds response?" regression is the thesis's core empirical object.

**Substrate extension (from live-data validation).** The same ladder math applies to any monotone numeric-threshold ladder — **valuation** ladders (Databricks \$200B/\$250B/…) and **revenue** ladders (NVIDIA data-center \$80B/…/\$100B), not just share-price strikes. This is how **private** companies (no stock price) enter Thread 2, and in recent months those ladders dominate volume. It argues for defining the ladder family by *(company, metric, period)* rather than share-price only.

**Honest flags.** Few groups/strikes per company-month → thin factor identification; a single factor captures location only (dispersion/shape need a second factor); LOCF staleness dominates thin strikes; event-time leakage (news may reach the market before the article timestamp — the "timestamp inverse problem," parked).

---

### Open questions for discussion
1. Normalization of $\theta_c$ that keeps $\boldsymbol\beta_g$ comparable across companies/months with different strike spacing.
2. Minimum positive-pair count to identify $M_\theta$ above the cosine null.
3. Per-company vs. pooled factor estimation (borrow strength across thin companies vs. avoid cross-firm misspecification).
4. Whether to define the ladder family by *(company, metric, period)* — folding valuation/revenue ladders into the strike-ladder model.

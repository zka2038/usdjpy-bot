# Splicing high-frequency FX data across sources, and handling incomplete data in a pre-declared analysis

Scope: Q5 (validating a new HF source before splicing) and Q8 (what to do when pre-declared data cannot be fully obtained). Labels used throughout: **[field-standard]** = codified in a widely used guideline, textbook or reference implementation; **[common/contested]** = widely practised or proposed but disputed or not codified; **[inference]** = my reasoning, not found stated in a source.

Retrieval caveat: several primary PDFs (Barndorff-Nielsen et al. 2009; Danielsson & Payne 2002; Willroth & Atherton 2024) could not be text-extracted in this session. Where a claim about them rests on an abstract, a search excerpt, or a secondary source (e.g. the R `highfrequency` documentation), that is stated. No dukascopy.com URL was fetched.

## Q5. Standard procedures for validating a new high-frequency source before splicing it into an existing series

### Takeaway
No source I found sets an absolute cross-source agreement tolerance (such as "0.3 pips") for splicing tick or bar data. The field-standard cleaning rules (Barndorff-Nielsen, Hansen, Lunde & Shephard 2009; Brownlees & Gallo 2006; the Olsen/Dacorogna adaptive filter) all scale their thresholds to the data: multiples of the day's median spread, or of MADs around a rolling median. The thresholds are set by heuristic and defended by how few observations they remove and by robustness checks, not derived from theory. Cross-source FX validation (Danielsson & Payne 2002) compares statistical properties and lead-lag structure, not only price levels. It found that indicative feeds lag firm venues by minutes and that spread behaviour differs persistently. So a fixed pip threshold is defensible only if it is tied to a stated scale (the spread at the execution hour, or the effect size), and the timestamp check should test fine lags as well as whole-hour lags.

### Cited Findings

**Cleaning rules: what is field-standard and how thresholds are justified**
- [field-standard] Barndorff-Nielsen, Hansen, Lunde & Shephard, "Realized kernels in practice: trades and quotes", *Econometrics Journal* 12(3), C1–C32 (2009), is the standard cleaning reference for trade/quote data. Its focus includes "data cleaning across different types of financial databases" — [EconPapers record](https://econpapers.repec.org/RePEc:ect:emjrnl:v:12:y:2009:i:3:p:c1-c32); [Shephard publications page](https://shephard.scholars.harvard.edu/publications/realised-kernels-practice-trades-and-quotes)
- [field-standard] The quote rules are implemented in R `highfrequency::quotesCleanup` as a fixed sequence: noZeroQuotes → exchangeHoursOnly → select a single exchange → rmNegativeSpread → rmLargeSpread → mergeQuotesSameTimestamp → rmOutliersQuotes (v1.0.2), citing BNHLS 2009 — [quotesCleanup docs](https://search.r-project.org/CRAN/refmans/highfrequency/html/quotesCleanup.html); [rdocumentation v1.0.2](https://www.rdocumentation.org/packages/highfrequency/versions/1.0.2/topics/quotesCleanup)
- [field-standard] Large-spread rule: delete entries whose spread is more than 50× the median spread on that day (default `maxi = 50`). The function is valid only on one day of data at a time, so the scale is the day's own median — [rmLargeSpread docs](https://rdocumentation.org/packages/highfrequency/versions/0.6.5/topics/rmLargeSpread)
- [field-standard] Outlier rule: delete entries where "the mid-quote deviated by more than 'maxi' median absolute deviations from a rolling centered median (excluding the observation under consideration)", with `maxi` defaulting to 10. The package's default "advanced" variant compares against the closest of the centred, previous-window and next-window medians, so that genuine jumps are not removed. The page attributes the standard rule to "Barndorff-Nielsen et al. (2010)" but its reference list cites the 2009 paper, an internal inconsistency — [rmOutliersQuotes docs](https://rdrr.io/cran/highfrequency/man/rmOutliersQuotes.html)
- A paper applying the BNHLS rules describes the rolling median as 50 observations (25 before, 25 after), excluding the observation itself, with a 10-MAD cutoff. Applied to its own data, the rules replaced 154 entries (≈0.05% of the sample) and the 50×-median step removed none. Reporting the share removed is how such thresholds are defended in practice — [arXiv 1605.05382](https://arxiv.org/pdf/1605.05382)
- [field-standard] Brownlees & Gallo, "Financial econometric analysis at ultra-high frequency: Data handling concerns", *Computational Statistics & Data Analysis* 51(4), 2232–2245 (2006). They propose an outlier filter that removes records "not consistent with plausible market activity". The filter uses a trimmed mean and SD in a local window (parameters k = neighbourhood, δ = trimming, γ = granularity). Their key result: coefficient differences are larger between dirty and clean series than among series cleaned with different algorithms — [IDEAS/RePEc](https://ideas.repec.org/p/fir/econom/wp2006_03.html); [working paper PDF](https://labdisia.disia.unifi.it/area01/pubblicazioni_DS/wp/2006/wp2006_03.pdf); filter parameters as described in [arXiv 2602.19732 (VOLARE)](https://arxiv.org/pdf/2602.19732)
- [field-standard, FX-specific] Gençay, Dacorogna, Müller, Pictet & Olsen, *An Introduction to High-Frequency Finance* (Academic Press, 2001), has a chapter on adaptive data cleaning focused on FX quotes, for which Reuters carried >275,000 spot prices a day — [Elsevier book page](https://shop.elsevier.com/books/an-introduction-to-high-frequency-finance/gencay/978-0-12-279671-5)
- The Olsen filter design (patent text) targets bid/ask FX quotes. It must be **strict immediately after a data gap**, since "no trader would take this test quote seriously when the market is quiet". It keeps copied quotes that sit at a correct level. Its time scales build on Dacorogna et al. (1993) intraday seasonality, which handles daylight-saving shifts — [US patent 7742959](https://patents.justia.com/patent/7742959)
- [field-standard, finance research protocol] Arnott, Harvey & Markowitz, "A Backtesting Protocol in the Era of Machine Learning", *Journal of Financial Data Science* 1(1), 64–74 (2019), Category #3 "Sample Choice and Data":
  - (a) define the test sample ex ante: "The sample should never change after the research begins";
  - (b) ensure data quality, with integrity tools "applied as a first step";
  - (c) document data-transformation choices, "ideally decided in advance", with results robust to minor changes;
  - (d) do not arbitrarily exclude outliers;
  - (e) select the winsorization level before modelling.
  - Its checklist asks "Were they selected in advance? And are the results robust to minor changes in these transformations?"
  - Sources: [SSRN 3275654](https://papers.ssrn.com/abstract=3275654); text read from the [SSRN PDF mirror](https://www.smallake.kr/wp-content/uploads/2023/04/SSRN-id3275654.pdf)

**Cross-source agreement and venue differences in FX**
- [field-standard precedent] Danielsson & Payne, "Real trading patterns and prices in spot foreign exchange markets", *Journal of International Money and Finance* (2002). The paper compares one week of Reuters EFX indicative quotes with firm D2000-2 broker quotes:
  - their statistical properties are "very similar … at a 5 minute sampling frequency";
  - indicative returns lag firm returns by up to ~3 minutes (2–3 min on average);
  - spread behaviour differs even at lower frequencies.
  - The method is to compare return statistics and lead-lag structure across sampling frequencies, not level differences alone.
  - Sources: [LSE Research Online](https://researchonline.lse.ac.uk/id/eprint/119126); [FMG DP320](https://www.fmg.ac.uk/sites/default/files/2021-01/dp320.pdf); [author PDF](https://www.riskresearch.org/files/DanielssonPayne2002.pdf). Figures are from abstracts and search excerpts; I could not extract the full PDF text.
- Chaboud, Chernenko & Wright, "Trading Activity and Exchange Rates in High-Frequency EBS Data", Fed IFDP 903 (2007):
  - EUR/USD and USD/JPY interdealer trading happens mainly on EBS, which is the reference price;
  - indicative-quote frequency is "only loosely related to actual trading volume, particularly at high frequency";
  - they drop Friday 17:00 – Sunday 17:00 NY time, holidays and very light days;
  - they anchor announcement times to the minute using the first Dow Jones newswire story, with FOMC releases varying from 14:11 to 14:20.
  - This is an example of known-event timestamp anchoring and of its limits.
  - Source: [Fed IFDP 903](https://www.federalreserve.gov/pubs/ifdp/2007/903/ifdp903.htm)
- Ito (NBER) contrasts EBS deal data with Reuters FXFX indicative quotes, noting they "differ … in at least two important respects". EBS cut the USD/JPY tick size tenfold (10⁻² → 10⁻³) in March 2011, a structural break for any sample spanning that date. These come from search excerpts only — [NBER w12413](https://www.nber.org/papers/w12413.pdf); [arXiv 1307.5440](https://ar5iv.arxiv.org/html/1307.5440)

**Timestamp / lead-lag alignment**
- [field-standard] Hoffmann, Rosenbaum & Yoshida, "Estimation of the lead-lag parameter from non-synchronous data", *Bernoulli* 19(2), 426–461 (2013). The lead-lag θ is estimated by maximising a shifted Hayashi–Yoshida covariation contrast over candidate shifts. The estimator converges at rate Δₙ⁻¹, faster than the usual Δₙ^(-1/2), so lags are well identified at fine resolution. A no-arbitrage alignment corresponds to θ = 0 — [arXiv 1303.4871](https://arxiv.org/pdf/1303.4871); [Project Euclid](https://projecteuclid.org/euclid.bj/1363192034); implementation in [yuima `llag`](https://search.r-project.org/CRAN/refmans/yuima/html/llag.html)
- Hayashi–Yoshida is the standard cross-covariance estimator for asynchronous ticks (search excerpt) — [arXiv 1111.7103](https://www.arxiv.org/pdf/1111.7103)

### Inferences
- [inference] **A fixed 0.3-pip threshold is defensible only if it is anchored to a stated scale.**
  - The field's thresholds are relative: 50× the median spread, or 10 MADs.
  - A natural anchor here is the bid-ask spread at the execution hour. The repo's CLAUDE.md records 0.36 pips at 08:00 JST, so 0.3 pips is about 0.8 of a spread.
  - A second anchor is the effect size. Spec 004's prefix effect is ~2.07 pips, so a source disagreement of 0.3 pips per fill (~0.6 pips per round trip if the errors do not cancel) is ~15–30% of the effect.
  - The spec should state which anchor justifies 0.3, and report the full distribution (median, mean, 90th/99th percentile, share above one spread), not just the median.
  - Because the threshold was declared before any comparison, it is not a post-hoc choice, which is the property Arnott et al. require.
- [inference] **A level-difference test at ±60 minutes cannot detect the lags the FX literature cares about.**
  - Bid levels are close to a random walk. At a ±60 min shift the mean absolute difference grows with ~1-hour USDJPY volatility (on the order of 10 pips), so it will almost always detect a one-hour DST-type error. That is useful, and it is the error already found in HistData.
  - It cannot see 1–3 minute misalignments, the scale Danielsson & Payne found between feeds.
  - It cannot see an off-by-one-bar convention: is the bar labelled T the open or the close of the minute? The repo's `quote_at` fills on the bar at ts−1min.
  - Two fixes: add offsets of −2, −1, +1, +2 minutes as a reported (not gating) diagnostic, or use the cross-correlation of 1-minute returns across shifts (the Hoffmann–Rosenbaum–Yoshida logic). Both are cheap.
  - Adding them to the gate after declaration would be a deviation. Adding them as reported-only diagnostics is not.
- [inference] **Compare returns as well as levels.** Danielsson & Payne's precedent compares return statistics, because two feeds can agree in level, differing by a constant spread offset, while differing in dynamics. For a fill used as an entry or exit price, level agreement is what matters for P&L. Return correlation at the execution bars is a cheap complement that separates a constant venue offset from noise.
- [inference] **Same venue, different extraction (2007–2014 third-party export vs. fresh ticks).** Large disagreements here more likely indicate processing differences (bar construction from ticks, bid vs. mid, time zone of export) than venue differences. A threshold is justified for this leg. For the 2023 HistData leg (different venue), reporting without a threshold matches how Danielsson & Payne treat cross-venue comparisons: they describe the differences and do not gate on them.
- [inference] **Corrected vs. uncorrected reference series.** I found no source stating that checking against both versions of a reference is standard. Reporting both is still good practice under Arnott et al.'s "document choices in data transformations", and it gives a free diagnostic:
  - the corrected series should agree at offset 0;
  - the uncorrected series should show the 60-minute discrepancy only in the weeks where EU and US DST dates differ;
  - that pattern independently confirms the correction.
  - Circularity risk: if the HistData DST correction was itself derived by comparing to Dukascopy, the 2023 comparison is not independent evidence of either series' correctness. The spec should say how the correction was derived.
- [inference] Brownlees & Gallo's result (dirty vs. clean matters more than which cleaning algorithm) supports doing a declared cleaning pass on the new tree before step 0, rather than tuning the filter. The Olsen-filter point (be strict right after gaps) applies directly to fills taken right after a vendor gap.

### Gaps
- Could not read the BNHLS 2009 full text. The thresholds above come from the `highfrequency` implementation and a citing paper, and the "P/T/Q" rule labels were not verified.
- No source found for Falkenberry/TickData guidance, or for Lyons' or Evans' views on feed comparability (not retrieved).
- No academic study found comparing Dukascopy (or any retail/ECN aggregator such as HistData) against EBS/Reuters for USDJPY. Venue tolerances for retail feeds are undocumented in the literature I found.
- No source found that states a numeric cross-source tolerance for splicing in pips or bp.

### Implication for this study
Step 0 matches field practice in its two main features: it is declared before the comparison, and it checks timestamps with an offset test. But the field gates on relative scales, and does lead-lag at fine resolution.

Three recommendations (all as reported-only additions, so the declared gate is not revised):
1. **Report the threshold against its scale.** Give the 0.3-pip median alongside the execution-hour spread and the effect size, plus the 90th/99th percentiles and the share of execution bars whose difference exceeds one spread.
2. **Add ±1/±2-minute offsets, or a 1-minute return cross-correlation over shifts.** This catches bar-labelling and sub-hour lags, which the ±60 test is blind to.
3. **Run the 2023 HistData comparison against both the corrected and uncorrected series**, and state whether the DST correction was derived independently of Dukascopy.

Changing the gate itself after the declaration would be a deviation and must be logged as one (see Q8).

## Q8. What is standard when pre-declared data cannot be fully obtained, and how to treat vendor-driven missingness

### Takeaway
Across economics (AEA/J-PAL, Banerjee et al. 2020), psychology (Lakens 2024; Willroth & Atherton 2024) and epidemiology (STROBE), the standard is to neither abandon nor silently proceed. You run what is achievable and document every deviation: what changed, why, and when relative to seeing data or results. You report the planned analysis next to any changed one, and report the amount, pattern and assumed mechanism of missingness, with complete-case and sensitivity comparisons.

Waiting for data is legitimate if the wait is not conditioned on interim results. The finance protocol literature (Arnott et al. 2019; Harvey 2017) adds that the sample must be fixed ex ante, so any change to the sample is a deviation to be disclosed. Vendor gaps are best treated as possibly MAR given time-of-day and date, and must be checked for differential missingness between treatment and control.

### Cited Findings

**Pre-registration deviation standards**
- [field-standard, psychology/meta-science] Lakens, "When and How to Deviate From a Preregistration", *Collabra: Psychology* 10(1), 117094 (2024), DOI 10.1525/collabra.117094:
  - "A principled approach to the use of preregistration should not treat all deviations as problematic";
  - deviations can increase or decrease a test's severity;
  - it gives worked cases for five situations: **unforeseen events, errors in the preregistration, missing information, violations of untested assumptions, falsification of auxiliary hypotheses**;
  - each deviation is judged by its consequences for severity and validity.
  - Source: [TU/e record](https://research.tue.nl/en/publications/when-and-how-to-deviate-from-a-preregistration/). I read the abstract only.
- [field-standard, reporting template] Willroth & Atherton, "Best Laid Plans: A Guide to Reporting Preregistration Deviations", *Advances in Methods and Practices in Psychological Science* (2024), DOI 10.1177/25152459231213802:
  - most deviations "go unreported or are reported in unsystematic ways";
  - it proposes a standard Preregistration Deviations Table recording each deviation's **type, reason, and timing**, plus unregistered steps;
  - surveyed journal editors on average said they would probably support requiring it;
  - "preregistration can still be a valuable tool, even in the presence of deviations, as long as those deviations are well documented".
  - Sources: [APS journal page](https://www.psychologicalscience.org/journals/ampps/25152459231213802/); [APS Observer summary](https://www.psychologicalscience.org/observer/methods-preregistration-deviations); supplementary template on [OSF](https://osf.io/et6km).
- [common/contested] Rubin, "Preregistration Does Not Improve the Transparent Evaluation of Severity in Popper's Philosophy of Science or When Deviations are Allowed", *Synthese* (2025). It argues that once deviations are allowed, preregistration adds less to severity evaluation than claimed. It is a critique of the Lakens framework — [arXiv 2408.12347](https://arxiv.org/pdf/2408.12347v13); [Springer](https://link.springer.com/article/10.1007/s11229-025-05191-4)
- [field-standard, economics RCTs] J-PAL guidance:
  - "If you find you need to modify your PAP, or you overlooked something, document why you made the edit";
  - "register new PAP versions only at a couple of designated milestones";
  - file the plan "at the latest before data analysis begins";
  - write a companion document that "populates the PAP to the extent possible and discusses any deviations from it";
  - "Where you are not sure of something, note it and indicate why".
  - Source: [J-PAL, Pre-analysis plans](https://www.povertyactionlab.org/resource/pre-analysis-plans)
- [field-standard, economics] Banerjee, Duflo, Finkelstein, Katz, Olken & Sautmann, "In Praise of Moderation" (NBER w26993, 2020), propose the "populated PAP": a brief document that fills in the plan as far as possible and records which pre-analysis intentions "were or were not achievable in practice". They warn that strict ex-post adherence norms can be detrimental — [MIT PDF](https://economics.mit.edu/sites/default/files/publications/InPraise.pdf); [NBER](https://www.nber.org/papers/w26993.ris)
- Olken, "Promises and Perils of Pre-Analysis Plans", *JEP* 29(3), 61–80 (2015). It frames the benefit as limiting specification search (the thought experiment of 100 candidate outcomes with no true effect) and discusses costs and limits. I did not retrieve its deviation guidance — [IDEAS](https://ideas.repec.org/a/aea/jecper/v29y2015i3p61-80.html)
- Christensen & Miguel, "Transparency, Reproducibility, and the Credibility of Economics Research", *JEL* 56(3), 920–80 (2018). A survey covering registration, PAPs and disclosure standards; I did not retrieve its specific deviation text — [EconPapers](https://econpapers.repec.org/RePEc:aea:jeclit:v:56:y:2018:i:3:p:920-80); [NBER w22989](https://www.nber.org/papers/w22989.pdf)
- Ofosu & Posner, "Pre-Analysis Plans: An Early Stocktaking", *Perspectives on Politics* 21(1), 174–190 (2023). They audit 195 AEA/EGAP PAPs (2011–2016) and the adherence of 93 that led to papers, finding "significant variation" in how well PAPs achieved their goals. I did not retrieve the deviation rate — [LSE](https://researchonline.lse.ac.uk/id/eprint/112747); [eScholarship PDF](https://escholarship.org/content/qt7pd498q0/qt7pd498q0.pdf?t=rhhz5i)

**Finance-specific**
- Arnott, Harvey & Markowitz (2019): "Define the test sample ex ante… The sample should never change after the research begins". Their example of illegitimate sample choice is a model that "works" from 1970 but not 1960. Under this rule a forced change to the sample from data unavailability is permitted only if it is disclosed and not chosen on results — [SSRN 3275654](https://papers.ssrn.com/abstract=3275654); text from [PDF mirror](https://www.smallake.kr/wp-content/uploads/2023/04/SSRN-id3275654.pdf)
- Harvey, "Presidential Address: The Scientific Outlook in Financial Economics", *Journal of Finance* 72(4), 1399–1440 (2017). The incentive toward positive results drives data mining and p-hacking. He recommends reporting a minimum Bayes factor beside p-values, and notes that even t > 3 can give many false positives when true effects are rare — [Duke Scholars](https://scholars.duke.edu/publication/1274012); [author PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P131_The_scientific_outlook.pdf)

**Missing-data reporting and mechanisms**
- [field-standard] STROBE item 12c, "Explain how missing data were addressed". The Explanation & Elaboration says to:
  - report the number missing for each variable at each analysis stage, with reasons where possible;
  - note that complete-case analysis is biased when the missing cases differ and is always less efficient;
  - classify missingness as **MCAR / MAR / MNAR**, recognising that valid inference under MNAR needs explicit assumptions about the mechanism;
  - for MAR, use likelihood, weighting or multiple imputation, **compare results with complete-case analysis**, and discuss differences.
  - Sources: [EQUATOR STROBE 12c](https://resources.equator-network.org/guidelines/strobe/items/statistical-methods-missing-data.html); [STROBE checklist](https://resources.equator-network.org/reporting-guidelines/strobe/strobe-checklist.html); [Vandenbroucke et al. E&E](https://boris.unibe.ch/55060/1/Vandenbroucke%20IntJSurg%202014.pdf)
- A methodological summary of STROBE-type guidance lists what to report: the method, the missingness assumptions, the imputation model and software, and the number of imputations — [PMC table](https://pmc.ncbi.nlm.nih.gov/articles/PMC7260743/table/Tab1)

### Inferences
- [inference] **Wait, run incomplete, or abandon?** The deviation literature makes this a disclosure question, not a prohibition. Waiting is clean only if the stopping point does not depend on interim results.
  - A gate of "run only when every stage has 0 requests left" is a stopping rule independent of results. That is good, but it has no deadline.
  - Standard practice (J-PAL's "designated milestones"; Lakens' "unforeseen events") would be to declare now, before any results, a fallback: e.g. if a stage cannot complete by date X, or a range proves unavailable from the source, run on what exists with a deviation-table entry, plus the planned complete-case comparison.
  - Abandonment is warranted only if the missing data make the declared test uninformative. That is a power/MDE question, consistent with the repo's rules.
- [inference] **The fill turns missing data into a measurement-error problem.** Filling gaps from a second source is single deterministic imputation from an auxiliary variable, so step 0 is in effect validation of the imputation model. Following STROBE's logic, the primary result should be reported three ways:
  1. complete-case (original-source trades only);
  2. filled;
  3. the difference between them, with the count of filled trades per arm (treatment vs control), per year and per source.
- [inference] **Mechanism assessment for vendor gaps.** Gaps driven by vendor outages or collection windows are plausibly MAR given observables such as date, hour and source. For example, HistData's Feb–Jul 2023 08:00–24:00 UTC holes depend on calendar time, not on the unobserved price. The MNAR risks are specific:
  - feeds tend to drop during fast markets (interventions, data releases), so missingness can correlate with large moves;
  - if gaps fall unevenly on treatment (Gotobi/month-end) vs control days, the B-vs-C contrast is biased even if gaps are MAR overall.
  - Diagnostics: tabulate missingness by arm × hour × year; compare realised volatility (from the filling source) on missing vs non-missing bars; test whether the missingness indicator predicts the outcome among filled trades.
  - If filled and complete-case estimates diverge materially, report a bound (worst-case or delta-adjusted) rather than choosing one.
- [inference] Any change to the step-0 gate, the threshold, or the fill rule made after seeing the comparison is a deviation. Per Willroth & Atherton it belongs in a table with type, reason and timing relative to data access, and per Lakens/J-PAL the pre-declared version should be reported alongside.

### Gaps
- Little & Rubin's *Statistical Analysis with Missing Data* was not consulted directly; the MCAR/MAR/MNAR definitions above come from STROBE's E&E.
- I did not retrieve the AEA RCT Registry's own amendment/deviation rules, CONSORT 2010/2025 missing-data items, or the OSF "Transparent Changes" template.
- No finance-specific standard found for reporting missing tick data in a pre-declared backtest. López de Prado's backtesting protocol was not retrieved; Arnott et al. 2019 is the closest found.
- The full texts of Lakens 2024 and Willroth & Atherton 2024 could not be extracted (abstracts and summaries only), so the template's exact column layout is unverified.

### Implication for this study
The pre-declared fill-then-gate design is consistent with field standards, provided three things:

1. **Declare a deadline and fallback now**, before any output exists. If a stage cannot finish, the study runs on available data with a logged deviation, rather than waiting open-endedly or changing scope later.
2. **Report complete-case alongside filled results**, with filled-trade counts by arm, year and source, and a missingness-by-arm table. Differential gaps between treatment and control days are the real threat to spec 004's contrast. The 2023 HistData hole lands on the prefix entry leg only, which is exactly where an asymmetric fill could move the result.
3. **Keep a deviation table** (type, reason, timing relative to data access) for anything that departs from the declared step 0, including the already-found HistData DST correction. Record whether that correction was made before or after looking at the outcomes it affects.

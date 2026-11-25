# Reconstructing historical transaction costs from mixed price sources (FX and anomaly backtests)

Scope: Q2 (replacing assumed spreads with measured ones; missing-quote handling), Q3 (uniform vs best-available cost per column), Q6 (how to key era cost scaling; USDJPY spread history anchors).
Labels used below: **[STANDARD]** = practice used by several primary sources without dispute; **[COMMON/CONTESTED]** = used, but with documented problems or disagreement; **[INFERENCE]** = my reasoning, not a sourced claim.
Note on sources: several PDFs were read in full-text extraction (Chen & Velikov FEDS WP; Novy-Marx & Velikov 2015 working-paper version of the RFS paper; Karnaukh-Ranaldo-Söderlind 2013 working paper; Menkhoff et al. JFE 2012; Ivanova-Neely-Weller appendix; Mahmoodzadeh & Gençay; Hasbrouck & Levich 2019). BIS 2009 and Frazzini-Israel-Moskowitz items are from search abstracts/summaries only, flagged where used. No dukascopy.com URL was fetched.

## Q2. When measured spreads arrive for minutes previously priced with an assumed spread, what replaces what? And what to do when no measured quote exists at that minute?

### Takeaway
The standard in the cost-measurement literature is a hierarchy: use the directly measured quote/spread for an observation whenever it exists, fall back to a proxy only where it does not, and never drop observations because their cost data are missing (doing so conditions trade selection on information that was unavailable at trade time). Gaps are filled by imputation from a model validated on the overlap where both measured and proxy costs exist, and the share imputed plus the validation are reported. Matching a trade to the "prevailing" (last prior) quote is the microstructure norm; I found no published, field-wide staleness tolerance for minute-bar FX.

### Cited Findings
- **Measured beats proxy, observation by observation [STANDARD].** Chen & Velikov: "We use high-frequency HF data to compute spreads whenever it is available" (Daily TAQ, Monthly TAQ, ISSM), and they "compute effective spreads pre-1983 (and whenever HF data is missing) using low frequency (LF) proxies based on daily CRSP data." — [Chen & Velikov, FEDS WP 2020-039, §2.2](https://www.federalreserve.gov/econres/feds/files/2020039pap.pdf); published as [JFQA 58(3) 2023, 968–1004](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/zeroing-in-on-the-expected-returns-of-anomalies/945133D5A3ECEEAF466AEE91551FD225)
- **The proxy is framed as a backcast of the unobserved measured cost and is validated against it on the overlap.** Chen & Velikov treat LF proxies "as a forecast (or backcast) of the unobserved high frequency effective spread" and average four of them (Hasbrouck 2009 Gibbs, Corwin-Schultz 2012 high-low, Abdi-Ranaldo 2017 close-high-low, Fong-Holden-Tobek's Kyle-Obizhaeva volume-over-volatility). The LF average correlates 90% with TAQ and 94% with ISSM spreads, beating the best single proxy (84% and 90%). — [Chen & Velikov, §2.2 and Table 1](https://www.federalreserve.gov/econres/feds/files/2020039pap.pdf)
- **Correlation is not level agreement: proxies carry a time-varying bias.** Chen & Velikov find LF spreads are "biased upward by 25-50 basis points" after 2003, so the costs Novy-Marx & Velikov (2016) took from LF estimates "overestimate expected costs going forward." — [Chen & Velikov, §2.2, Fig. 2](https://www.federalreserve.gov/econres/feds/files/2020039pap.pdf)
- **Dropping observations without cost data is explicitly rejected.** Novy-Marx & Velikov: "We are interested in the cost of trading anomalies, and cannot know at the time of portfolio formation if the trading cost estimate for any given stock will be missing when we want to unwind the position. We thus cannot limit our trading to stocks for which the direct estimates of trading costs are available." — [Novy-Marx & Velikov, working paper Aug 2015, §2](https://mysimon.rochester.edu/novy-marx/research/ToAatTC.pdf); published [RFS 29(1) 2016, 104–147](https://econpapers.repec.org/RePEc:oup:rfinst:v:29:y:2016:i:1:p:104-147.)
- **Imputation method and how it is documented.** Novy-Marx & Velikov replace each missing Gibbs estimate with the cost of the nearest-neighbour stock in (size rank, idiosyncratic-volatility rank) space. They chose non-parametric matching because Fama-MacBeth fits showed nonlinearity, and they flag "the danger of extrapolating transaction costs estimated on large, relatively liquid stocks to small stocks using a linear model." They report that imputation adds 29% of observations but under 4% of market cap. They validate by re-imputing observations that do have direct estimates: momentum and PEAD strategy costs differ by "less than one basis point per month," with "no obvious biases in either direction." — [Novy-Marx & Velikov, §2, Fig. 2](https://mysimon.rochester.edu/novy-marx/research/ToAatTC.pdf)
- **A different gap rule for a different cost component.** Where price-impact estimates are missing, Novy-Marx & Velikov use "the contemporaneous cross-sectional average price elasticity … scaled by firms' market capitalizations," and report that these cover under 3.8% of market cap. — [Novy-Marx & Velikov, fn. 11](https://mysimon.rochester.edu/novy-marx/research/ToAatTC.pdf)
- **Background on the proxy's accuracy.** Hasbrouck (2009, JF) reports that his Gibbs effective-spread estimates have a 96.5% correlation with TAQ-measured spreads (as cited in Novy-Marx & Velikov). — [Novy-Marx & Velikov, §2](https://mysimon.rochester.edu/novy-marx/research/ToAatTC.pdf)
- **Matching trades to quotes: the prevailing-quote rule with an explicit timing convention [STANDARD in equity microstructure].** Effective spread is 2|log(P_k) − log(M_k)|, where M_k is the midpoint of the "matched" best bid and offer. Chen & Velikov follow Holden & Jacobsen's (2014, JF) interpolation-matching code: a 2-second quote delay before 1999, 1 ms for 1999–2002, then 1 ms / 1 µs / 1 ns delays as Daily TAQ timestamps get finer. The delay is chosen per data era to match that era's timestamp precision. — [Chen & Velikov, Appendix A.2](https://www.federalreserve.gov/econres/feds/files/2020039pap.pdf)
- **Proxy calibration to the measured series.** The VoV proxy's 8.0 coefficient "was chosen by FHT to fit the average monthly TAQ effective spread." That is, a proxy's level is set by fitting it to measured spreads where both exist. — [Chen & Velikov, Appendix A.3](https://www.federalreserve.gov/econres/feds/files/2020039pap.pdf)
- **FX analogue.** Karnaukh, Ranaldo & Söderlind suggest that "one can estimate FX trading costs using the estimated coefficients by fitting low-frequency FX liquidity to high-frequency effective cost" (EBS), and they use the fitted series to backcast to 1991. — [Karnaukh, Ranaldo & Söderlind WP 2013, §1](https://www.ecb.europa.eu/events/pdf/conferences/131216/Third_FX_workshop_RANALDO_UnderstandingFXLiquidity_KRS_20Sep2013_FULL.pdf); published [RFS 28(11) 2015](https://papers.ssrn.com/abstract=2329738)

### Inferences
- [INFERENCE] **"Replace the spread" vs "bid-anchored difference" vs "re-price entirely".** The literature's model is to replace the proxy cost with the cost measured from the new source's own quotes: trade price against that source's own prevailing midpoint. Applied here, that means **re-pricing both legs from the measured source's bid and ask** rather than adding (ask_B − bid_B) to bid_A. The hybrid "bid_A + spread_B" mixes two venues' midpoints. Any bid-level offset between HistData/third-party Dukascopy bid and the measured source then shows up as a fake cost or fake alpha, and it lands on the entry or exit leg depending on which leg was re-priced. The clean decomposition is:
  1. Δ(net P&L) = Δ(gross mid-to-mid P&L, a data-source effect) + Δ(spread cost, the cost effect).
  2. Report both terms. Only the second is the "measured cost" correction.
  3. If the source-B mid differs materially from source A at the same minute, that is a data-integrity finding in its own right.
- [INFERENCE] **Measured-minute-missing cases.** The standard sequence is:
  1. Use the prevailing quote (last tick at or before the execution timestamp, respecting `quote_at`'s ts−1min convention), within a tolerance set once and declared before results.
  2. Where no quote falls within the tolerance, impute from a model calibrated on the overlap: time-of-day × regime/era × a liquidity proxy, analogous to Novy-Marx & Velikov's characteristic matching.
  3. Flag every imputed trade.

  Dropping these trades is defensible only as a separately labelled "measured-coverage" subsample, never as the headline. Novy-Marx & Velikov's look-ahead argument applies directly, and in this repo missingness is not random: HistData's 2023 08:00–24:00 UTC holes hit the 23:00 UTC prefix entry specifically.
- [INFERENCE] **Documentation pattern drawn from these papers.** Report:
  - the fraction of trades (and of the P&L) priced by each method;
  - a validation of the imputation on trades where the measured value exists ("impute it as if missing, compare to the measured value", as Novy-Marx & Velikov's Fig. 2 does), giving bias and dispersion;
  - the level bias of the proxy against measured values by era, not just the correlation (as Chen & Velikov's Fig. 2 does).

### Gaps
- I found no published field standard for a quote-staleness tolerance in minute-bar FX backtests (e.g. "carry forward at most N seconds/minutes"). The Holden–Jacobsen delays concern timestamp alignment, not staleness. A tolerance would have to be declared ex ante and sensitivity-tested.
- I did not retrieve Holden & Jacobsen (2014) itself, which discusses withdrawn and stale quotes in DTAQ; claims about it here come only via Chen & Velikov's appendix.
- I found no academic paper that explicitly compares "bid-anchored spread substitution" with "full re-pricing" from a second source. That recommendation is inference.

## Q3. One uniform cost assumption per column, or best-available cost per trade? What do papers do with partial cost coverage?

### Takeaway
Published anomaly and FX papers use **best-available-per-observation for the headline net return**: measured where available, a calibrated proxy or imputation elsewhere, or era-specific fixed costs before data exist. They then add **uniform, deliberately conservative or zero-cost columns as bounds** (gross vs. full quoted spread). Splicing sources is accepted but known to introduce level breaks at the seam. Careful papers therefore calibrate the proxy to the measured series on the overlap and report proxy-vs-measured bias, rather than assuming the two are interchangeable.

### Cited Findings
- **Chen & Velikov (JFQA 2023): best-available hybrid.** HF effective spreads (ISSM 1983–92, Monthly TAQ, Daily TAQ from Oct 2003) where available, and the four-proxy LF average elsewhere (pre-1983 and gaps). Their data notes list ISSM holes: NASDAQ missing Apr–May 1987, Apr and Jul 1988, Nov–Dec 1989, plus 46 NASDAQ and 146 NYSE/AMEX trading days with no data in 1987–1991. These holes are also filled by LF proxies. — [Chen & Velikov, §2.2, fn. 8](https://www.federalreserve.gov/econres/feds/files/2020039pap.pdf)
- **Chen & Velikov switched sources because of the splicing problem.** They say the earlier LF-only approach (Novy-Marx & Velikov) "overestimate[s] expected costs" after 2003 by 25–50 bp, which is why HF data is "important … to examine trading costs in recent years." — [Chen & Velikov, §2.2](https://www.federalreserve.gov/econres/feds/files/2020039pap.pdf)
- **Novy-Marx & Velikov (RFS 2016): one estimator (Gibbs) everywhere, with matched imputation for missing observations.** This is a uniform method with best-available fill, validated on the overlap. — [Novy-Marx & Velikov, §2](https://mysimon.rochester.edu/novy-marx/research/ToAatTC.pdf)
- **Menkhoff, Sarno, Schmeling & Schrimpf (JFE 2012, FX momentum): one uniform conservative assumption plus gross.** They use Barclays/Reuters bid and ask (via Datastream) for both spot and forward legs, quote by quote at month-end. They impose "the full quoted bid–ask spread," which "is known to be too large relative to actual effective spreads (Lyons, 2001)." Net results are therefore described as a "lower bound on profitability," and they "frequently provide results with and without transaction costs." Applying the full spread cuts the best strategy from ~10% to ~4% p.a. — [Menkhoff et al. JFE 106 (2012) 660–684, §2 and §5.1](https://faculty.washington.edu/ss1110/IF/Sarno%20Currency%20Momentum%20JFE%20%281%29.pdf)
- **Neely & Weller (2013, FX technical rules): era-fixed costs before data, scaled measured costs after.**
  - Before Bloomberg spread data begin (Dec 1995), one-way costs for advanced currencies (Japan included) are 5 bp in the 1970s, 4 bp in the 1980s and 3 bp in the 1990s. These are consistent with Frenkel-Levich and McCormick triangular-arbitrage estimates.
  - From Dec 1995 they use one-third of the quoted one-month forward spread. Correspondence with traders led them to conclude "quoted spreads were roughly three times actual spreads."
  - Every currency has a 1 bp floor at all times. Cross rates take the maximum of the two USD legs.

  — [Ivanova, Neely & Weller, FRB St. Louis WP 2014-033, Online Appendix A](https://fraser.stlouisfed.org/files/docs/publications/frbsl_wp/2014-033_appendix.pdf)
- **Conflicting scale factors for quoted-to-effective FX spreads [COMMON/CONTESTED].** Menkhoff et al. apply the full quoted spread (a conservative bound). Neely & Weller divide by three, based on trader conversations. This is a judgement-based scalar in both cases, and it differs by 3×. — [Menkhoff et al.](https://faculty.washington.edu/ss1110/IF/Sarno%20Currency%20Momentum%20JFE%20%281%29.pdf); [Ivanova, Neely & Weller appendix](https://fraser.stlouisfed.org/files/docs/publications/frbsl_wp/2014-033_appendix.pdf)
- **Different FX spread sources are not interchangeable, even in correlation.** Daily 21:00 GMT snaps of EBS bid-ask have "weak correlations (0.04–0.28)" with Thomson Reuters daily bid-ask (Jan 2007–May 2012). Reuters bid-ask volatility for EUR/USD, EUR/CHF and USD/JPY "is more than twice as large as that from EBS." Reuters daily quotes are indicative, while EBS holds "the best transactable bid and ask prices." — [Karnaukh, Ranaldo & Söderlind WP 2013, fn. 13](https://www.ecb.europa.eu/events/pdf/conferences/131216/Third_FX_workshop_RANALDO_UnderstandingFXLiquidity_KRS_20Sep2013_FULL.pdf)
- **Which FX proxies track measured cost.** Against EBS effective cost (2007–2012), the best low-frequency measures are:
  - volatility (avg corr 0.81)
  - Corwin-Schultz (0.71)
  - Gibbs (0.70)

  The Roll measure (0.30), BPW (0.10) and EffTick (0.06) perform poorly, and daily indicative bid-ask "work[s] less well." CS, Gibbs and volatility stay above 0.76 in all three sub-periods, including Lehman. — [Karnaukh, Ranaldo & Söderlind WP 2013, §5.2](https://www.ecb.europa.eu/events/pdf/conferences/131216/Third_FX_workshop_RANALDO_UnderstandingFXLiquidity_KRS_20Sep2013_FULL.pdf)
- **Live execution data shows modelled costs can be an order of magnitude off.** Frazzini, Israel & Moskowitz use $1.7 trillion of AQR live executions across 21 developed equity markets over 19 years. They find actual costs far below prior-study estimates and fit a concave market-impact model from the live data. — [Frazzini, Israel & Moskowitz, SSRN 3229719 (2018) abstract](https://papers.ssrn.com/abstract=3229719); [AQR working paper page](https://www.aqr.com/Insights/Research/Working-Paper/Trading-Costs). (From the abstract and summaries only; model details not verified.)

### Inferences
- [INFERENCE] The literature does not require each column to apply one method uniformly. A study using best-available costs must, however, show that the method switch does not drive the result. The two papers that splice (Chen & Velikov; Neely & Weller) both address this:
  - Chen & Velikov report the proxy's bias against measured spreads by era.
  - Neely & Weller anchor pre-data assumptions to independent estimates (triangular arbitrage).

  Neither presents a hybrid number without a statement of how the seam behaves.
- [INFERENCE] **A column design that matches field practice and fits this repo's rules:**
  1. **Assumed-cost (uniform synthetic) column.** Synthetic profile × era multiplier on every trade. It is comparable across eras and reproduces the existing spec numbers.
  2. **Measured-only column.** Measured bid/ask on the trades that have it, explicitly labelled as conditional on coverage. Report n, and test whether covered and uncovered trades differ in gross (mid) return. This is a missing-at-random check; if they differ, this column is biased.
  3. **Best-available hybrid as the headline.** Measured where available, imputed (validated) elsewhere, with a per-trade source flag and the share of trades and P&L from each source.
  4. **PESSIMISTIC bound,** as the repo already requires.

  This mirrors Menkhoff et al.'s "gross + conservative-bound" reporting and Chen & Velikov's hybrid.
- [INFERENCE] **The headline should not be a uniform measured column with gaps silently dropped.** In this repo the gaps are non-random in time-of-day and era (the 2023 HistData holes sit on the prefix entry leg). Under Novy-Marx & Velikov's argument, dropping them conditions on post-trade information.
- [INFERENCE] **Seam risk is concrete here.** Dukascopy bid/ask (an ECN/bank aggregator) and Eightcap MT5 (a retail raw-spread account) are different venues, much as Reuters-indicative and EBS-firm quotes are. A hybrid that uses Dukascopy for 2007–2024 and Eightcap from mid-2024 changes venue at the seam. Run an overlap comparison over the period when both exist (mid-2024 onward) before splicing.

### Gaps
- I did not retrieve Hasbrouck (2009), Corwin & Schultz (2012) or Abdi & Ranaldo (2017) directly. Their roles above come via Chen & Velikov and Karnaukh et al.
- I did not verify Gilmore & Hayashi (2011) or Lyons (2001) primary text on how far quoted FX spreads overstate effective spreads. Lyons is cited only through Menkhoff et al.
- I found no Neely & Weller passage on time-varying intraday FX costs beyond the appendix summarised above.
- Practitioner texts (López de Prado AFML, Kissell, Harris) were not retrieved. I cannot cite them on mixed-source cost splicing.

## Q6. Key era cost scaling by calendar date, by data source/venue, or by a measured liquidity proxy? USDJPY spread-history anchors

### Takeaway
Practice runs from calendar-step costs (Neely & Weller's per-decade bp levels, used only where no data exist), to source-keyed costs (measured where a source exists), to measured liquidity proxies calibrated to measured spreads (Chen & Velikov; Karnaukh et al.). The proxy approach is the most defensible: FX spreads did not decline monotonically and spike in stress (Lehman: 3–4×), which a calendar multiplier cannot capture. The evidence for USDJPY gives these anchors:
- EBS USDJPY had a hard 1-pip tick floor on the inside spread until March 2011.
- EBS average quoted spread was ~1.5 bp (≈1.4 pips at 2007–12 levels), with effective cost ~0.4 bp per side, over 2007–2012.
- Spreads kept narrowing into 2016 while larger-order price impact rose after 2013.

### Cited Findings
- **Calendar keying where nothing is measured [STANDARD as a fallback].** Neely & Weller set decade-specific costs (5/4/3 bp one-way for 1970s/80s/90s) before Dec 1995, then switch to a source (Bloomberg forward spreads ÷ 3) with a 1 bp floor. — [Ivanova, Neely & Weller appendix](https://fraser.stlouisfed.org/files/docs/publications/frbsl_wp/2014-033_appendix.pdf)
- **Proxy keying calibrated to measured spreads [STANDARD in anomaly cost work].** In Chen & Velikov, costs vary per stock-month through the LF proxies. The VoV proxy's 8.0 scale was fit to TAQ averages. Their combined measure reproduces the 1970s NASDAQ entry, the late-1980s rise and the 2000s collapse with electronic trading and decimalisation. — [Chen & Velikov, §2.2, Fig. 3, App. A.3](https://www.federalreserve.gov/econres/feds/files/2020039pap.pdf)
- **In FX, a volatility proxy tracks measured cost best.** Volatility has the highest average correlation with EBS effective cost (0.81). Karnaukh et al. build a systematic FX liquidity measure (first principal component of CS, Gibbs and volatility) with 0.93 correlation to EBS effective cost over Jan 2007–May 2012, and backcast it to 1991. — [Karnaukh, Ranaldo & Söderlind WP 2013, §1, §5.2](https://www.ecb.europa.eu/events/pdf/conferences/131216/Third_FX_workshop_RANALDO_UnderstandingFXLiquidity_KRS_20Sep2013_FULL.pdf)
- **Stress spikes are large and short.** The estimated GBP/USD effective spread rose about 3× from ~0.5 bp in Aug 1992 (Black Wednesday). AUD/USD rose 4×, from 0.9 to 4.1 bp, by end-Oct 2008 after Lehman. — [Karnaukh, Ranaldo & Söderlind WP 2013, §1](https://www.ecb.europa.eu/events/pdf/conferences/131216/Third_FX_workshop_RANALDO_UnderstandingFXLiquidity_KRS_20Sep2013_FULL.pdf)
- **USDJPY EBS levels, Jan 2007–May 2012 (1-minute EBS data, Fri 22:00–Sun 22:00 GMT excluded).** USD/JPY monthly mean effective cost 0.401 bp (sd 0.091) and mean proportional quoted bid-ask 1.501 bp (sd 0.364). EUR/USD for comparison: 0.292 and 1.057. EC is |P − mid|/mid per trade, so it is a per-side measure. "Average effective costs are smaller than average bid-ask spreads, reflecting within-quote trading." — [Karnaukh, Ranaldo & Söderlind WP 2013, Table 1, Eqs. 1–2, §5.1](https://www.ecb.europa.eu/events/pdf/conferences/131216/Third_FX_workshop_RANALDO_UnderstandingFXLiquidity_KRS_20Sep2013_FULL.pdf). Same data lineage: [Mancini, Ranaldo & Wrampelmeyer, JF 68(5) 2013](https://econpapers.repec.org/RePEc:bla:jfinan:v:68:y:2013:i:5:p:1805-1841)
- **EBS tick-size history (a hard structural break, keyed by date and venue).**
  - EBS moved majors from pip to decimal-pip pricing in 2010–11. EUR/USD changed in March 2011, and the paper's Table 1 lists USD/JPY "p → dp" among the 2010–2011 changes.
  - EBS partly reversed to half-pip in September 2012.
  - EUR/USD mean EBS inside spread was 1.5 pips (0.00015) under pip pricing, 1.3 under decimal pip and 1.0 under half pip. Under pip pricing the spread was at the 1-pip floor more than 50% of the time.

  — [Mahmoodzadeh & Gençay, "Human vs. High Frequency Traders in the Interbank FX Market: Role of Tick Size," preprint submitted to J. Banking & Finance, 2016, Tables 1–2, §8.1](https://www.fmg.ac.uk/sites/default/files/images/Tick%20Size.pdf)
- **Conflict on USD/JPY half-pip.** LeapRate reports that EBS half-pip pricing applied to USDJPY (with EURUSD, AUDUSD, GBPUSD, USDCHF, USDCAD) from Monday 17 September. Mahmoodzadeh & Gençay's Table 1 shows a dp→hp change for USD/CHF, EUR/USD and others but no hp entry for USD/JPY. Treat USD/JPY's 2012 tick as unconfirmed. — [LeapRate](https://www.leaprate.com/news/icap-ebs-goes-to-half-pip-pricing); [Mahmoodzadeh & Gençay](https://www.fmg.ac.uk/sites/default/files/images/Tick%20Size.pdf)
- **2010–2016: spreads down, price impact non-monotone.** Using CLS settlement data, price-impact coefficients "generally decline from April 2010 to April 2013 and rise from April 2013 to April 2016." Olsen bid-ask spreads "generally decline" over both periods, "suggesting an ongoing improvement in liquidity for smaller orders." Settlement prices for yen pairs sat on the 0.01 grid in 2010; by 2016 the price grid had "become finer by a factor of ten." — [Hasbrouck & Levich, "FX Liquidity and Market Metrics: New Results Using CLS Bank Settlement Data," NYU WP, Sept 2019](https://pages.stern.nyu.edu/jhasbrou/Research/Hasbrouck-Levich%20v25.pdf)
- **Venue fragmentation changes what a "spread" means.** Single-bank platforms rose from 16% (2013) to 25% (2016) of global FX turnover, and EBS+Reuters' share fell from ~16% to 13%. Hasbrouck & Levich cite Moore-Schrimpf-Sushko (BIS QR 2016) for these figures. — [Hasbrouck & Levich 2019](https://pages.stern.nyu.edu/jhasbrou/Research/Hasbrouck-Levich%20v25.pdf)
- **Long-run trend.** The BIS reports that interbank FX efficiency "improved significantly as electronic broking spread" and that bid-ask spreads fell from 1996 (Graph 1 includes JPY/USD). The decline levelled off by the mid-2000s and spreads rose sharply after Lehman (Sept 2008). — [BIS Quarterly Review, March 2009, "Execution methods in foreign exchange markets"](https://www.bis.org/publ/qtrpdf/r_qt0903h.pdf) (content via search summary; full text not extracted)

### Inferences
- [INFERENCE] **Implied USDJPY pip anchors** (my arithmetic, using approximate 2007–12 USDJPY levels of ~80–118, mean ≈95):
  - EBS quoted spread of 1.50 bp ≈ **1.4 pips** (range ~1.2–1.8 across the price range).
  - EBS per-side effective cost of 0.40 bp ≈ **0.38 pips**, i.e. ~0.76 pips round trip against mid.
  - These are all-hours averages (Fri/Sun excluded) on the interbank venue, at a 1-pip tick floor before 2011.
  - The repo's pre-2015 ×5 on ~0.3 pips gives 1.5 pips. That is close to the all-hours EBS *quoted* average, but roughly 2× the EBS *effective* round-trip cost.
  - Which is right depends on venue. A retail or ECN fill in 2007–2014 was plausibly at or above EBS quoted, not EBS effective, but I found no sourced retail USDJPY spread series for 2007–2014 (see Gaps).
- [INFERENCE] **Calendar step functions are the weakest keying.** The ×5 → ×2.5 → ×1 step at 2015 and mid-2024 does not coincide with any documented structural break. The documented breaks are:
  - the EBS decimalisation of 2010–11;
  - the 2012 half-pip partial reversal (unconfirmed for USDJPY);
  - the 2008 Lehman spike and 2010–2013 improvement;
  - the 2013–2016 deterioration in price impact alongside continued spread narrowing;
  - the venue shift to internalisation.

  A step at 2015 is a data-source boundary (third-party Dukascopy → HistData), not a liquidity boundary. Keying cost on it confounds venue/source with era.
- [INFERENCE] **Recommended keying, consistent with field practice:**
  1. **Key on source/venue first**, because measured spreads from a given source define that source's cost.
  2. **Within a source, scale by a measured liquidity proxy** calibrated on the overlap. Candidates are realised volatility from the bid series (Karnaukh et al.'s best FX proxy) or Corwin-Schultz on hourly high/low, keyed by JST hour (and NY-DST flag for JST 6–8, per the repo's trap 7). This captures Lehman/2011-quake/intervention-day widening that a calendar multiplier misses.
  3. **Use calendar keying only as a fallback** for periods with no overlap data, anchored on the EBS breaks and the 2007–12 EBS levels above.

  Once the pending Dukascopy tick download provides genuine 2007–2014 bid/ask and 2015–2024 sample days, the era multipliers can be **estimated** (measured spread ÷ synthetic profile, by JST hour and year) instead of set by judgement. Judgement multipliers should then become a stress column, not the base case.
- [INFERENCE] **Report level bias, not just correlation.** For the overlap validation, report the proxy-vs-measured *level bias* by year, as Chen & Velikov do in their Fig. 2. A proxy with 0.9 correlation can still be off by a factor that dominates a 1.5–2.1 pip effect.

### Gaps
- I found no primary, citable time series of **retail/ECN USDJPY spreads 2005–2024** (e.g. broker-published average spreads by year). Retail anchors for the ×5 and ×2.5 multipliers are therefore unsourced here.
- I found no published EBS USDJPY inside-spread series by year for 2003–2024. Karnaukh et al. give only the 2007–2012 average. The BIS 2009 Graph 1 JPY/USD series was not extracted, so no pre-2007 or post-2012 USDJPY pip levels are cited.
- Whether EBS USD/JPY moved to half-pip in Sept 2012 is unresolved (sources conflict, above).
- I did not obtain Chaboud et al. (2014, JF) or King-Osler-Rime (2012) spread figures. They may hold 2003–2010 EBS USDJPY spread levels.
- No time-of-day (Tokyo-morning) USDJPY spread figures from the literature were found. The EBS averages above are all-hours and may overstate the 08:00–11:00 JST spread (high-liquidity hours) or understate rollover-adjacent hours.

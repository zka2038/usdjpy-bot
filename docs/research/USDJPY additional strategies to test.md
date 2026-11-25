# Weekend gaps top the next USDJPY test queue

Of the roughly forty further USDJPY ideas reviewed here, only one has evidence that is specific to the yen, out of sample and net of costs: the **weekend-gap reversal**. After the largest 5% of downward Monday-open gaps, USDJPY retraced about **0.32% by the Monday New York close and 0.63% over three days**, and the contrarian rule earned significant alpha on major pairs after costs in a 2007–2014 out-of-sample test. A 0.32% move is about 50 pips, more than 40 times the ~1.1-pip round trip your repo's cost model charges. Your complete 2015–2024 HistData bars also give a clean post-publication test. Three other ideas make the queue mainly because they are cheap to test on data you already hold and their moves dwarf costs, not because the evidence is strong. They are fading large 1-minute moves that have no scheduled news, trading continuation after the first five minutes of US 08:30 ET releases, and fading the reaction to the BoJ statement into Governor Ueda's 15:30 JST press conference. A good deal of well-known event folklore fails for the yen in particular. The FOMC-day dollar premium is **−1.59bp with t = −0.16 for JPY**. Pre-FOMC dollar drift has no significant yen loading. Pressure around Treasury auctions halved after 2015 and works out to a few pips. Japanese holidays, Golden Week and March are coin flips for direction. The cross-asset, options and positioning signals (VIX regimes, volatility targeting, CFTC extremes, Japanese retail positioning, risk reversals) work best as overlays that cut drawdowns on a trend/carry position, and the options and retail-positioning versions need data the repo lacks. Before any of this, build three tools: a US release and auction calendar, which is the most valuable missing dataset; a 30-minute seasonality baseline to act as the control for every window test; and a volatility forecast for sizing. Also extend the bars past 5 June 2026, since they currently miss the July 2026 intervention.

## A 1.1-pip cost bar and a June 2026 data edge set what you can test

### The cost model sets a pip hurdle that most intraday effects cannot clear

Every strategy below is judged against the cost model in your repo (`src/usdjpy/costs.py`). It applies IBKR's 0.20bp commission with a $2 minimum per side, fills at bid/ask, and adds 0.1 pip of slippage per side (0.3 pip under `PESSIMISTIC`). At USDJPY ≈ 159 a pip on $100k is worth about $6.29, so **commission is about 0.32 pip per side**. Adding slippage and a 0.25–0.30-pip spread gives a **round trip of about 1.1 pips in liquid hours, or about 1.5 pips under PESSIMISTIC**. The Eightcap raw-spread data in the repo puts the median spread at 0.23–0.30 pips through most session hours, 0.33–0.36 around 08:00–09:00 JST, and **about 5 pips at 06:00–07:00 JST**, the 17:00 New York rollover (`docs/DATA.md`). Below $100k notional the $2 minimum dominates: at $25k it alone costs about 2.5 pips per round trip.

Most published intraday effects for the yen are 1–2bp, or 1.5–3 pips, so this bar removes much of the intraday literature before any test is run. Your spec 001 result shows what passing looks like. Gotobi-versus-control was significant at p ≈ 0.01, and the post-fix short netted +1.6 pips per trade with synthetic spreads. Moving to PESSIMISTIC slippage adds 0.4 pip per round trip, which leaves about +1.2 pips. That is thin, but positive.

Overnight holds add financing. IBKR charges interest only on settled balances. A position closed before the 17:00 ET value-date roll creates none; one held through it is rolled with a tom-next swap and pays or earns benchmark ± spread, with TONAR as the JPY benchmark ([IBKR KB 2815](https://ibkb.interactivebrokers.com/de/node/2815); [IBKR KB 2949](https://ibkb.interactivebrokers.com/de/node/2949)). For the multi-day strategies below, this means long USDJPY earns a little carry and short USDJPY pays it. At an assumed 4% net differential (pull the live rates from IBKR), that is roughly 1.5–2 pips a night: immaterial against a 50-pip gap reversal, decisive against a 3-pip edge.

### The repo covers most event tests, but its bars stop before the July 2026 intervention

Three features of the repo shape the whole queue.

First, the **bars end on 5 June 2026**. The Eightcap real bid/ask series runs from 2024-06-19 to 2026-06-05. It therefore covers the 30 April 2026 intervention but not the record ¥15.4tn joint operation of 30 July–3 August 2026, or anything from September to November.

Second, the **pre-2015 history is patchy**. Dukascopy 2011–2018 is only 40–65% complete and 2020 is missing. HistData is complete only for January 2015 to April 2025.

Third, the **holdout starts on 1 January 2025**. That leaves about 17 months of held-out bars. This is ample for daily strategies, but nearly useless for rare-event strategies such as weekend gaps, which would see only a handful of signals.

The table below sorts the data the queue needs into what is loaded, what `scripts/fetch_official.py` can pull for free, and what has to be sourced.

| Data | Status | Coverage / note | Needed by |
|---|---|---|---|
| 1-min bid bars (Dukascopy, HistData) | **In repo** | 2007–2014 gappy; 2015-01→2025-04 complete; synthetic ask from Eightcap hourly profile | Everything |
| 1-min real bid/ask + ticks (Eightcap) | **In repo** | 2024-06-19→2026-06-05; ~45M ticks | Spread validation, limit-fill tests, round numbers, shock fades |
| FOMC calendar (with SEP flag, unscheduled) | **In repo** | 2007→2027 | FOMC window tests, blackout filters |
| BoJ MPM calendar | **In repo** | 2010→2027; 2007–09 missing; no statement timestamps | BoJ tests |
| MOF intervention days | **In repo** | 1991→2026-08-03 (transcribed; diff against official file) | Post-intervention rules, exclusions |
| JP holidays, gotobi, UK month-ends | **In code** | `usdjpy.calendars` | Holiday filters |
| CFTC TFF + legacy JPY | **In repo** | 2010-01→2026-11-17, with `available_from` | COT rules |
| FRED: DGS10/20/30, VIX, Nikkei, DEXJPUS | **In repo** | to 2026-06; CBOE VIX to 2026-09 | Factor models, VIX filters |
| MOF JGB 1y–40y; BoJ call rate | **In repo** | to 2026-05 | Rate-differential and hedged-yield signals |
| DGS2, DGS3MO, DFF, SOFR, SP500, broad dollar, OECD JP rates, MOF weekly flows | **Scriptable** (`fetch_official.py`, not yet run) | Free | Equity-shock rule, residual model, rate filters |
| Bars after 2026-06-05 | **Scriptable** (`download.py`, Dukascopy ticks) | Free, large | Holdout, July 2026 intervention, current regime |
| US release calendar with times (NFP, CPI, etc.) | **Missing** | BLS/BEA schedules, free; consensus has no reliable free source | US release rule; news exclusion for shock fades |
| Treasury auction calendar and results | **Missing** | TreasuryDirect, free; when-issued yields are paid | Auction rules |
| Rate-check dates (e.g. 2026-01-23) | **Missing** | Add by hand | Exclusions |
| Fed funds futures / OIS history | **Missing** | CME ZQ (paid or IBKR); DFF is a crude proxy | Signalled pre-FOMC rule |
| FX options (25Δ RR, implied vol, expiries) | **Missing** | Bloomberg/Refinitiv paid; CME JPY options IV via IBKR; DTCC public data | All options rules |
| Japanese retail positioning | **Missing** | TFX Click 365, FFAJ; broker pages need scraping | Retail liquidation rule |
| Intraday ZN/ES/NKD futures | **Missing** | Databento/DataMine paid; IBKR history limited | Lead-lag diagnostics |
| AUD/NZD/EUR crosses | **Missing** | Dukascopy free | Cross controls, FOMC high-yielder variant |
| BIS REER, G10 3m rates | **Missing** | Free, monthly | Value cap, dollar factor |
| Live IBKR quotes | **Missing** | Log via API | Recalibrating `slippage_pips` |

### Running many tests requires a stricter bar for exploratory ideas

The queue below implies about eight strategies with up to three variants each, plus about ten cheap diagnostics: roughly 35 tests. At p < 0.05, around two would pass by chance. A Bonferroni bar of 0.05/35 means **t ≈ 3.2**. A workable compromise is to treat hypotheses whose rules and parameters come straight from published work (weekend gaps, Osler's round numbers, the auction cycle) as confirmatory at t ≥ 2. Ideas whose thresholds you are choosing yourself (shock fades, the BoJ reversal, COT turns) count as exploratory and need t ≥ 3, plus the same sign in both halves of 2015–2024. Keep a ledger of every variant run, including the failures.

## Event calendars: weekend gaps survive, central-bank days mostly don't

### Weekend gaps are the one event effect with out-of-sample support

Dao et al. study 16 USD pairs using daily Bloomberg data from 2002 to May 2014. They define the weekend return as log(Monday open / Friday close) and the signal as the top or bottom 5% of that return. Fifteen of the 16 pairs show significant reversal ([NTU IRep](https://irep.ntu.ac.uk/id/eprint/35555/1/13113_Dao.pdf)). The yen result is asymmetric.

**Downward gaps** average −0.444% and then retrace:

| Horizon after a downward gap | Retracement |
|---|---|
| By the European open | +0.148% |
| By the US open | +0.183% |
| By the US close | +0.322% |
| After three days | **+0.634%** (significant at 1%) |

**Upward gaps** average +0.537%. They reverse by −0.299% by the first US close (significant at 5%), but the reversal is gone by three days and has turned into continuation by one week.

The authors estimated thresholds on 2002–2006 and ran the contrarian strategy out of sample from January 2007 to May 2014. After a 0.08% round-trip cost and interest differentials, **alpha on the majors was about 0.05–0.06% a week**, with maximum drawdowns of 2.3–24.1% across pairs ([NTU IRep](https://irep.ntu.ac.uk/id/eprint/35555/1/13113_Dao.pdf)).

Three caveats determine how to test this.

First, the paper labels the pair "JPY/USD". The asymmetry could flip depending on the quote convention, so test both directions as one pre-declared hypothesis rather than trusting the stated asymmetry.

Second, daily Bloomberg "Monday opens" are indicative prints from the thinnest point of the week. The real-world haircut is how much of the gap has already closed by the time spreads normalise. The Eightcap profile shows spreads still around 5 pips in the rollover hour (06:00–07:00 JST) and back near 0.33 pip by 08:00 JST.

Third, the sample is small. With 5% tails, 2015–2024 contains roughly 26 signals per side. As an illustration only, assume the per-trade standard deviation is 0.6–0.8% and the true reversal is 0.32%. Then t = 2 needs about 15–25 trades and t = 3 about 30–55. So a decade of complete data can confirm a full-sized effect, but cannot detect one that has halved.

Large event gaps carry their own risk. After the October 2014 BoJ easing surprise, a gap near 112.50 took about 1.5 years to fill as USDJPY ran to 125.87 ([Moneypost](https://www.moneypost.jp/225396/3/)). Gaps follow weekend politics too: the 27 October 2024 lower-house election produced a yen-weak gap the next morning ([OANDA Japan](https://www.oanda.jp/lab-education/market_news/2024_10_28_usdjpy/)). Retail claims that "73% of gaps fill within 24 hours" have no visible method behind them ([FXNX](https://fxnx.com/en/blog/forex-weekend-gap-size-500-sunday-opens-their-fill-rates)). Japanese data on holiday Mondays also show that 10-sen-plus gaps split 19 down and 20 up ([ZAi FX](https://zai.diamond.jp/articles/-/313145)). Gap direction is therefore unpredictable. The bet is only on partial reversal of the largest gaps.

### FOMC and auction effects are dollar stories that skip the yen

The well-known FOMC results largely do not apply to USDJPY. Mueller, Tahbaz-Salehi and Vedolin find that a short-USD portfolio earns **12.45bp on FOMC days versus 0.34bp otherwise** (t = 2.43), with about 75% of it accruing before 14:15 ET. **For the yen the FOMC-day return is −1.59bp versus −0.58bp otherwise (t = −0.16)**, because the premium sits in high-yielding currencies ([FMG DP 54](https://www.fmg.ac.uk/sites/default/files/publications/dp-54.pdf); [LSE](https://researchonline.lse.ac.uk/id/eprint/77256)). Lucca and Moench find no pre-FOMC drift in currencies at all ([NY Fed SR512](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr512.html)). Karnaukh's futures-signalled strategy works for the dollar: go long or short USD from 14:00 ET two days before a meeting to 14:00 ET on the day, according to whether fed funds futures price a hike or a cut. It earned 25bp per trade with a Sharpe of 0.93 before costs over 1994–2015, but **JPY is the only G10 currency with an insignificant loading** (0.30, t = 0.94) ([Karnaukh](https://acfr.aut.ac.nz/__data/assets/pdf_file/0019/190315/DollarAheadFOMC_NinaKarnaukh.pdf)). A 2025 study adds that post-announcement FX returns cancel about 65% of the pre-FOMC drift ([RAPS 2025](https://econpapers.repec.org/RePEc:oup:rasset:v:15:y:2025:i:3-4:p:247-287.)).

The plausible reason is that two channels offset each other. Hawkish news lifts USDJPY through the rate differential, and dovish relief rallies lift it through risk-on demand. Because the repo already holds the FOMC calendar, a pre/post window split costs an afternoon to run. It belongs in the diagnostics battery with an expected null result, not in the trading queue.

Treasury auctions are a better-documented mechanism with too small a payoff. The NY Fed finds yields rise **0.36–0.63bp over the 180 minutes before the 13:00 ET bid deadline**, then fall back 0.32–0.75bp afterwards. The effect was strongest in 2007–2014 and is less than half that size since 2015 ([NY Fed SR1188](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr1188.pdf)). Krohn finds that a one-standard-deviation rise in auction demand weakens the USD by about 2bp against the G9, yen included ([Bank of Canada SWP 2025-29](https://www.bankofcanada.ca/2025/11/staff-working-paper-2025-29/)). Translated through USDJPY's sensitivity to US yields, the expected move is low single-digit pips, about the size of the cost bar. The test is still worth running, because there are around 24 ten- and thirty-year auctions a year: a clean null result would arrive quickly. It needs the free TreasuryDirect calendar, which the repo does not yet hold.

### BoJ days and US releases offer big moves but only anecdotal or mixed evidence

BoJ decision days are where yen surprises cluster. Under Kuroda, the rate of large FX surprises on policy-meeting days was **13.3% against a 4.4% Tokyo baseline**, and six of the 30 largest yen surprises since 1984 fell on BoJ days ([Keio-IES DP2025-015](https://ies.keio.ac.jp/upload/DP2025-015_EN.pdf)).

The tradeable claim is a practitioner one. The reaction to the midday statement often reverses during the 15:30 JST press conference. June 2024 is the standard example: the yen weakened to 158.25 on the statement, then Ueda's "considerable" taper comments pushed USDJPY back into the 156s ([MUFG FX Daily](https://www.bk.mufg.jp/report/dmr2024/FXDaily20240614.pdf)). On 23 January 2026, USDJPY first rose above 159 after the press conference and then fell below 157.4 amid rate-check rumours ([Jiji via Adnkronos](https://english.adnkronos.com/2026/01/23/dollar-briefly-dives-below-157-4-yen-in-tokyo-2/)). That day shows the contamination problem. Of six 2026 decision days, the three down days all had ranges of 2 yen or more and were tied to official action: the 23 January rate check and the 31 July intervention ([Monex](https://media.monex.co.jp/articles/-/30412)).

Pre-meeting yen strength appeared in about five meetings in 2023 ([MNI](https://marketnews.com/yen-has-tended-to-strengthen-in-the-lead-up-to-prior-boj-meeting-outcomes)). That is too few to test. Leaks sometimes arrive more than 12 hours before the decision ([Japan Times](https://www.japantimes.co.jp/commentary/2023/11/02/japan/boj-media-leaks)), so a "leak continuation" rule would need timestamped headlines.

The statement-to-press-conference reversal is worth testing because the repo has the BoJ calendar from 2010 and the 1-minute bars to detect the statement minute. It also sits at a time no other strategy uses. Expect only about 40–60 qualifying events, and require that the result survives excluding intervention and rate-check days.

US 08:30 ET releases split the evidence.

The case against continuation is direct and USDJPY-specific. EBS data for USDJPY and EURUSD show that the effect of a data surprise on the conditional mean is absorbed quickly ([Fed IFDP 823](https://www.federalreserve.gov/pubs/IFDP/2004/823/ifdp823.htm)).

The case for continuation is indirect. Evans and Lyons find that news-induced customer order flow stays significant for days with persistent price effects: "currency markets are not responding to news instantaneously" ([NBER w11041](https://www.nber.org/papers/w11041.pdf)). Several US releases also show drift in the direction of the coming surprise from about 30 minutes before, mostly in equity futures ([ECB WP 1901](https://ecb.europa.eu/pub/pdf/scpwps/ecbwp1901.lv.pdf)).

A rule that skips the first jump and enters after five minutes, once spreads have normalised, avoids the latency race that rules out news scalping. NFP and CPI alone give about 24 events a year, so the test has power. It needs a release calendar, but not consensus data: the first five-minute move serves as the market-implied surprise.

### Intervention aftermaths, holidays and fiscal year-ends are risk rules, not trades

Post-intervention behaviour is consistent but rests on a handful of episodes. FOREX.com's count shows the intervention day itself averaging −1.2% with a 3.1% range. Over the following six days there is no directional bias and ranges contract. Three of the four 2022–2024 interventions marked significant turning points, though the sample is admitted to be small and these figures come from search snippets ([FOREX.com](https://www.forex.com/en-au/news-and-analysis/japanese-yen-intervention-volatility-fades-but-turning-points-emerge/)).

The 2026 episodes show the reversal fading. The joint July operation pushed USDJPY from near 164 to 155.23. The rebound stalled at the 38.2% retracement (158.58), and the pair was back near 159 by 11 August ([IG](https://www.ig.com/uk/news-and-trade-ideas/yen-intervention--what-history-tells-us-about-last-week-s-dramat-260716)) and above 160 by September ([IG](https://www.ig.com/uk/news-and-trade-ideas/yen-intervention--what-history-tells-us-when-usd-jpy-returns-to--260903)). This was with the rate differential "largely unchanged" ([LSEG](https://www.lseg.com/en/insights/data-analytics/why-rate-differentials-remain-dominant-despite-japans-intervention)).

Only about eight yen-buying intervention days fall inside your bar data. That is too few for a directional strategy, but enough to justify a risk rule: no new directional entries from T+1 to T+6, and size intraday trades to the T+0 range.

Holidays fail as direction signals. Across 178 Japanese holiday trading days from 2007 to March 2019, the yen rose in **52.8%** of Tokyo sessions, a non-significant difference. Over Golden Week from 1999 to 2018, USDJPY fell 11 times and rose 9 ([ZAi FX](https://zai.diamond.jp/articles/-/313145)).

What survives is the tail risk:

- Golden Week ranges average **2.15 yen** ([ZAi FX](https://zai.diamond.jp/articles/-/313145)).
- There were yen-surge panics in four straight Golden Weeks, 2008–2011 ([Monex](https://media.monex.co.jp/articles/-/16689?mmuid=532720210430)).
- The 3 January 2019 flash crash produced a 3.04-yen range ([ZAi FX](https://zai.diamond.jp/articles/-/313145)).

March repatriation fails a long-run count: the yen strengthened in only **19 of 42 Marches** from 1973 to 2014 ([Mizuho](https://www.mizuhobank.co.jp/forex/pdf/market_analysis/econ150311.pdf)). The claim that end-March marks turning points rests on 5 of 6 years in 2000–2005 ([Monex](https://media.monex.co.jp/articles/-/21641?mmuid=579320230329)). With about 19 observations per calendar effect in the repo, these belong in the diagnostics battery to check folklore, not in the trading queue.

## Intraday statistics: round numbers and shocks are real but thin

### Round numbers are statistically real for USDJPY and roughly cost-sized

Osler's order-book work is the strongest microstructure basis for any intraday USDJPY rule. Take-profit orders cluster at round numbers, and stop-losses cluster just beyond them ([J. Finance 2003](https://ideas.repec.org/a/bla/jfinan/v58y2003i5p1791-1819.html)).

Using minute-by-minute USDJPY quotes in New York hours from 1996 to 1998, she finds two effects, both against bootstrapped arbitrary levels ([NY Fed SR150](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.pdf)):

- **Reversal.** Rates reverse at 00/50 levels **60.1% of the time versus 57.3%** at arbitrary levels. The effect lasts under 30 minutes and is stronger in the New York afternoon.
- **Continuation.** After a round number is crossed, the rate moves **1.3bp further** than after a reversal.

The paper contains one inconsistency: the two-hour significance appears as both 0.017 and 0.145.

A 2.8-point edge in hit rate and a roughly 2-pip continuation edge sit right at the 1.1-pip cost bar. The data also predate algorithmic liquidity provision. Use the result as a modifier: never park a take-profit just beyond a figure, and never park a stop just beyond one either. Test the fade and breakout rules against placebo levels to see whether the effect survives in 2015–2024.

This needs a path-dependent simulator, since the entry is triggered by a touch rather than a clock time. It also needs limit-fill assumptions validated on the Eightcap ticks. Option barriers add a colourful anecdote but no test. A 1bn reverse knock-out at 155.50 broke at about 03:33 UTC (12:33 JST) on 26 April 2024 and spot ran to 158.33. Even the authors say the brake-then-accelerate effect is inferred, not measured ([MathFinance](https://mathfinance.com/wp-content/uploads/2025/01/2025-01-Barriers-brake-the-spot.pdf)).

### Time-of-day effects are baselines, and intraday momentum has gone

The "currencies weaken in their own trading hours" effect is present in USDJPY: the yen weakened by about 1.7% a year in Tokyo hours over 1997–2007. But **the strategy lost money after EBS costs for the yen** (−0.05 in the USD session, −0.13 in the JPY session). Only EURUSD profited ([Breedon & Ranaldo WP694](https://www.qmul.ac.uk/sef/media/econ/research/workingpapers/2012/items/wp694.pdf)). A 2010–2015 replication confirms the pattern ([Zhang, FRL 2018](https://econpapers.repec.org/RePEc:eee:finlet:v:27:y:2018:i:c:p:99-104)).

Krohn, Mueller and Whelan find that the yen is the exception in an overnight/intraday split. **USDJPY falls overnight (yen +1.73% a year, 17:00–08:30 ET) and rises in New York hours (yen −2.01%)** ([Krohn et al. 2018](https://acfr.aut.ac.nz/__data/assets/pdf_file/0007/190753/Krohn_Mueller_Whelan_Jun2018_FXPremiaAroundTheClock.pdf)). Switching between those two windows grosses about 2.2 pips a day and costs about two round trips, so it nets close to zero.

The two papers' session signs can be reconciled. The yen weakens into the 09:55 JST fix (the gotobi flow) and strengthens after it and through Europe. Settling that needs an hour-by-hour map, not session averages. That **30-minute seasonality map, split by gotobi versus non-gotobi days and by year**, is the single most useful diagnostic in this report. It is the control every window test should be measured against, and the repo already enforces a control-day comparison.

Intraday momentum has decayed out of currencies. In CME currency futures, the coefficient of the last half-hour on the rest of the day fell from 1.31 (t = 6.48) in 1974–1999 to **0.33 (t = 1.45, insignificant) in 2000–2020**, and the timing strategy earned 0.85% a year before costs ([Baltussen et al.](https://academicweb.nd.edu/~zda/intramom.pdf)). The mechanism also needs a hard session close, which 24-hour spot lacks ([Elaut et al.](https://ideas.repec.org/a/eee/finmar/v37y2018icp35-51.html)). One regression by year settles it.

### Volatility is forecastable, so shocks and sizing are where 1-minute data pays

FX volatility is autocorrelated, follows an intraday periodic pattern, and jumps around announcements and interventions ([St. Louis Fed WP 2012-008](https://files.stlouisfed.org/files/htdocs/wp/2012/2012-008.pdf)). That makes a HAR-RV forecast, built from 5-minute realised variance at daily, weekly and monthly lags, the most reliable product of your 1-minute bars. Use it for sizing and for switching strategies on and off, not for direction.

The same periodicity matters for any shock rule. Without normalising each 1-minute return by its minute-of-week volatility, "large moves" just pick out 08:30 ET and 09:55 JST.

The case for fading no-news shocks is borrowed from equities. In equity ETFs, 57% of intraday jumps have no associated news, and **those are followed by significant reversals for at least 60 minutes** ([Xiao, Yin & Zhao](https://law-journals-books.vlex.com/vid/jumps-news-and-subsequent-855590156)). The only FX trading evidence is a three-month 2013 jump-cluster study ([Bayes WP 08-2014](https://www.bayes.citystgeorges.ac.uk/__data/assets/pdf_file/0009/246546/08-2014.pdf)), and FX jump detection is "extremely sensitive" to sampling frequency and test choice ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9563180)).

The yen-specific danger is that the largest "no-news" moves in 2022–2026 were interventions, rate checks and BoJ leaks, and those continue rather than revert. The exclusion list therefore matters more than the entry threshold. Spread and tick-rate surges in the Eightcap ticks are best used as an entry filter, for example skipping entries for 5 minutes when the spread z-score exceeds 3. No source tests them as direction signals, and two years of ticks allow only one train/test split.

## Cross-asset, options and positioning work as overlays, not triggers

### Spot now leads futures, so minute-scale lead-lag is closed to retail

In 1996, CME yen futures led spot by up to nine minutes. By 2006 the relationship had reversed: spot carried 89% of price discovery against floor futures, and Globex led by only three minutes with low correlations ([NY Fed SR262](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr262.pdf)).

The yen's link to equities and bonds is contemporaneous and non-linear. The yen rises when US stocks fall, US bonds rally and FX volatility jumps, "from a few hours to several days" ([Ranaldo & Söderlind](https://econpapers.repec.org/RePEc:oup:revfin:v:14:y:2010:i:3:p:385-407)). It is also unstable: one late-2025 reading had the 10-day Nikkei correlation at 0.08 while the 20-day reading was 0.81 ([Forex.com](https://www.forex.com/en-us/news-and-analysis/usd-jpy-nikkei-outlook-japanese-yen-weakens-amid-risk-on-tone/)).

With API latency of hundreds of milliseconds and paid intraday futures data, a lead-lag trade is not worth building. A daily residual "catch-up" model is cheap to run once `fetch_official.py` has pulled DGS2 and SP500. It regresses USDJPY on changes in US yields, JGB yields, VIX and equities, then fades 5-day residual extremes. But no paper supports it, and a JIE study finds that once small-sample bias is corrected, no variable beats the random walk for the dollar out of sample ([JIE 2023](https://www.sciencedirect.com/science/article/abs/pii/S0022199623000016)).

### Risk-off and volatility rules cut tails, but their Sharpe gains fail out of sample

The yen's haven behaviour depends on the regime.

- **2022:** ING said the USDJPY–equity correlation had fallen from about 0.35 to zero ([Fortune](https://fortune.com/2022/09/02/japanese-yen-price-falls-to-24-year-low-against-dollar-is-it-safe-haven-asset)).
- **Early November 2026:** the yen got no haven bid when Japanese stocks fell almost 6% in a US tech rout ([ExchangeRates.org.uk](https://www.exchangerates.org.uk/news/47709/2026-11-08-us-dollar-to-yen-forecast-us-tech-stock-crash-tests-the-yen-s-haven-role.html)).
- **20 November 2026:** the yen did get a haven bid in Friday's sell-off, which reversed with Monday's Nvidia-led rally ([TMGM](https://www.tmgm.com/en/analysis/market-news/article/japanese-yen-weakens-as-nvidia-led-stock-rally-boosts-risk-appetite-202611231815)).

An equity-shock safe-haven short is therefore testable but needs splitting by regime, and conditioning on whether Japan was the epicentre.

Volatility management raised Sharpe ratios in sample, including for FX carry ([Moreira & Muir](https://www.ssrn.com/abstract=2773438)). In real-time tests the gains "generally do not survive"; in one example the equity-market Sharpe improvement shrinks to 0.488 versus 0.471 ([Cederburg et al., via arXiv 2603.03213](https://arxiv.org/pdf/2603.03213)). The robust benefit is tail control. Judge VIX-regime filters and volatility targeting on the trend/carry position by the change in maximum drawdown and skew, not by return.

### Options signals predict crashes weakly and need data you lack

Risk reversals drive the skew of risk-neutral returns "but explain little of the skewness of future spot returns" ([Risk.net citing Jurek](https://www.risk.net/cutting-edge/7959625/harvesting-the-fx-skew-premium)). Brunnermeier, Nagel and Pedersen found that the relationship with future skewness has a surprising negative sign once rate differentials are controlled for ([NBER chapter](https://www.nber.org/system/files/chapters/c7286/c7286.pdf)).

The strongest options-based predictor is cross-sectional. Della Corte, Ramadorai and Sarno's volatility-risk-premium sort earned **4.03% a year with a Sharpe of 0.48** in developed currencies over 1996–2011 ([AEA version](https://aeaweb.org/conference/2014/retrieve.php?pdfid=554)). It has never been shown as a single-pair timing rule.

Expiry pinning has equity support but no FX evidence. Golez and Jackwerth find pinning in S&P futures but "cannot find evidence of pinning in related markets" ([Golez & Jackwerth](https://d-nb.info/1112655492/34)).

All three need option data you do not hold. The cheapest route is implied volatility on CME JPY options from IBKR history, used as a crash filter. Defer the rest.

### Positioning samples are tiny, and retail loss-cuts are the most interesting mechanism

The CFTC TFF series in the repo separates Leveraged Funds from Asset Managers ([CFTC](https://www.cftc.gov/sites/default/files/idc/groups/public/@commitmentsoftraders/documents/file/tfmexplanatorynotes.pdf)). There is still no out-of-sample test of a JPY TFF rule. An "extreme plus turn" rule would fire fewer than 15 times since 2010, so report it trade by trade rather than as a statistic.

Japanese retail positioning has a better mechanism. The BoJ describes margin traders in two ways. They are normally contrarians who dampen moves. They are also structural yen sellers whose **forced loss-cut liquidations accelerated yen rallies** in March 2011, August 2015 and January 2016 ([BoJ Review 2016-E-5](https://www.boj.or.jp/en/research/wps_rev/rev_2016/data/rev16e05.pdf)). So the signal is not a general "fade retail". It is that an extreme retail yen short combined with a break lower in USDJPY provides fuel for a liquidation cascade.

The 2026 data are volatile. Retail flipped to about ¥500bn net long yen in June, the most since late 2020 ([Bloomberg](https://www.bloomberg.com/news/articles/2026-06-22/japan-s-retail-fx-traders-bet-their-government-can-prop-up-yen)). Reposted Bloomberg figures then put retail at a record-high ¥3.61trn net short by September ([KuCoin](https://www.kucoin.com/news/flash/japanese-retail-investors-hold-23-5b-yen-short-position-amid-currency-rally)), possibly on a different aggregation. Building a consistent TFX Click 365 series is a data project before it is a test.

### The dollar factor, the basis, value and ML add little to a single pair

The dollar carry factor earns Sharpe ratios above 0.5 for the dollar basket ([Lustig, Roussanov & Verdelhan](https://www.nber.org/papers/W16427)). For USDJPY it largely duplicates the US–Japan rate filter.

The yen cross-currency basis is the most extreme among the majors ([BIS QR 2016](https://www.bis.org/publications/qr-201609/covered-interest-parity-lost-understanding-cross-currency-basis)), but its relationship to yen spot moves is insignificant: R² of 0.012 ([Fed IFDP 1283](https://www.federalreserve.gov/econres/ifdp/files/ifdp1283.pdf)).

In a 16-year out-of-sample portfolio test, the real exchange rate added nothing, while carry, momentum and reversal did ([Barroso & Santa-Clara](https://ore.exeter.ac.uk/repository/handle/10871/14068)). So the record-low yen REER belongs only as a cap on position size.

The 2026 ML working papers disagree on whether ML beats the random walk at all ([SSRN 6351765](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6351765); [SSRN 6741546](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6741546)). If you try ML, do it last, walk-forward, against carry and trend benchmarks.

## A prioritised test queue with exact rules

The ranking weighs five factors: whether someone is forced to trade (the mechanism), how yen-specific and out-of-sample the evidence is, how large the move is relative to the 1.1-pip bar, how many events 2015–2024 supplies, and whether the repo already holds the data. Times are given for US winter (EST) first and US summer (EDT) second. JST is always UTC+9.

### Tier 0: build the baselines and calendars first

| Step | What to build | Data status |
|---|---|---|
| 0a | **30-minute seasonality map.** Mean and t-stat by JST bucket, by year, gotobi versus non-gotobi. Key buckets: 09:00–09:55, 09:55–11:30, 11:30–12:30 lunch, 12:30–15:00, 15:00–16:00 JST (00:00–07:00 UTC). Also the US morning, 08:30–12:00 ET (13:30–17:00 / 12:30–16:00 UTC). Add the overnight/NY split (17:00–08:30 ET versus 08:30–17:00 ET), day-of-week, and spread by minute-of-week from Eightcap. | In repo |
| 0b | **Volatility model.** HAR-RV on 5-min realised variance, a minute-of-week volatility profile, and a vol-target sizing function. | In repo |
| 0c | **Event calendar.** BLS/BEA release times (NFP, CPI), TreasuryDirect auctions, BoJ 2007–09, rate-check dates by hand; run `fetch_official.py` (DGS2, SP500, DFF) and `download.py` (bars after 2026-06-05). | Missing / scriptable |
| 0d | **Cheap-null battery**, run through `window_trades` against control days. FOMC pre-window T−1 16:00 ET → T 13:55 ET and post-window 14:00–16:00 ET (statement at 04:00 / 03:00 JST). BoJ decision day close-to-close. JP holiday Tokyo session 09:00–15:00 JST (00:00–06:00 UTC). Golden Week, Obon and year-end trend continuation. Fiscal year-end 20-day fade from the last March Tokyo close at 15:00 JST (06:00 UTC). Intraday-momentum regressions. Expected result: nulls. Log each one in the multiple-testing ledger. | In repo |

### Tier 1: strategies to test, in order

| Rank | Strategy | Exact rule | Evidence and expected size | Events, 2015–24 | Data |
|---|---|---|---|---|---|
| **1** | **Weekend-gap reversal** | Fri ref = last mid ≤ 16:55 ET Fri (Sat 06:55 / 05:55 JST; 21:55 / 20:55 UTC). Gap g = ln(first mid after Sun 17:00 ET reopen, Mon 07:00 / 06:00 JST ÷ Fri ref). Signal: g in the top or bottom 5% of the trailing 260 weekends (expanding window). Downward gap → long, upward → short. **Entry Mon 08:00 JST (Sun 23:00 UTC).** Three pre-declared exits: Mon 16:00 JST (07:00 UTC); Mon 16:50 ET (Tue 06:50 / 05:50 JST); Thu 16:50 ET. Report the sides separately and log the gap share already retraced at 08:00 JST. | OOS 2007–14: down-gap retrace +0.32% by US close, +0.63% at 3 days; up-gap −0.30% at day 1 only ([Dao et al.](https://irep.ntu.ac.uk/id/eprint/35555/1/13113_Dao.pdf)). About 40× cost. | ≈26 per side | In repo; check Sunday-open bar coverage |
| **2** | **No-news 1-min shock fade** | Shock: \|r₁ₘ\| > 5 × trailing 60-day median \|r₁ₘ\| for that minute-of-week. Exclude ±5 min around 08:30, 10:00 and 14:00 ET on every weekday until 0c exists; 08:25–08:55 JST (23:25–23:55 UTC); 09:50–10:00 JST (00:50–01:00 UTC); BoJ days 11:00–16:00 JST (02:00–07:00 UTC); FOMC days after 14:00 ET; MOF intervention days and T+1; rate-check days; 16:55–17:10 ET; Mondays before 09:00 JST. Enter against the shock at the next bar close. Exits at 15, 30 or 60 min. Twin test: shocks *inside* news windows should continue. | Equity no-news jumps revert ≥60 min ([Xiao et al.](https://law-journals-books.vlex.com/vid/jumps-news-and-subsequent-855590156)); FX evidence weak. | Hundreds | In repo; validate fills on Eightcap ticks |
| **3** | **US release post-jump continuation** | NFP and CPI only. r₅ = mid 08:29→08:35 ET (22:29–22:35 / 21:29–21:35 JST; 13:29–13:35 / 12:29–12:35 UTC). If \|r₅\| > 2 × median of that release's last 12 \|r₅\|, enter with r₅ at 08:35 ET. Exits: 10:00 ET (00:00 / 23:00 JST); 16:00 ET (06:00 / 05:00 JST next day); next Tokyo close 15:00 JST (06:00 UTC). Diagnostic: does the 08:00→08:29 ET drift predict the sign of r₅? | Flow persistence for days ([Evans & Lyons](https://www.nber.org/papers/w11041.pdf)) against a fast conditional mean in EBS USDJPY ([IFDP 823](https://www.federalreserve.gov/pubs/IFDP/2004/823/ifdp823.htm)). | ≈240 before filter | Needs release calendar (0c) |
| **4** | **BoJ statement → press-conference reversal** | Decision days from `boj_mpm.csv`. Statement minute = first bar 11:00–14:00 JST (02:00–05:00 UTC) with \|r\| > 5 × that minute's 20-day median. R₁ = mid from 1 min before the statement to 15:25 JST (06:25 UTC). If \|R₁\| > 0.3%, fade at 15:25 JST. Exit 17:00 JST (08:00 UTC) or 23:59 JST (14:59 UTC). Run the continuation twin. Exclude intervention and rate-check days. | Anecdotes 2024–26 ([MUFG](https://www.bk.mufg.jp/report/dmr2024/FXDaily20240614.pdf)); BoJ-day surprise rate 13.3% vs 4.4% ([Kamada](https://ies.keio.ac.jp/upload/DP2025-015_EN.pdf)). | ≈40–60 qualifying | In repo |
| **5** | **Round-number fade and breakout vs placebo** | Levels XXX.00 and XXX.50, tested separately; placebo offsets bootstrapped. Fade: first approach within 1.5 pips → limit at L∓1 pip, stop L±5, target 5 pips, 30-min time stop. Breakout: stop-entry at L±2, stop 3 pips the other side of L, exit at 60 or 120 min. Hours 09:00–02:00 JST (00:00–17:00 UTC). Subset: NY afternoon 12:00–16:00 ET (02:00–06:00 / 01:00–05:00 JST). Skip ±15 min around scheduled data. The statistic is round minus placebo. | Reversal 60.1% vs 57.3%; continuation +1.3bp ([Osler SR150](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.pdf)). About 1–2× cost. | Thousands | In repo; needs a touch-based simulator |
| **6** | **Treasury auction cycle** | 10y and 30y auction days, plus refunding-week 3/10/30y. Long 10:00→12:58 ET (00:00–02:58 / 23:00–01:58 JST; 15:00–17:58 / 14:00–16:58 UTC). Short 13:01→16:00 ET (03:01–06:00 / 02:01–05:00 JST). Control: non-auction days at the same times. | Yields +0.4–0.6bp before, reversing after; halved since 2015 ([SR1188](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr1188.pdf)). Expect a few pips. | ≈240 | Needs TreasuryDirect calendar |
| **7** | **Equity-shock haven short** | Trigger: S&P 500 day < −2% and VIX close > 1.25 × its 20-day mean. Short at 16:50 ET (06:50 / 05:50 JST; 21:50 / 20:50 UTC). Hold 1 and 3 days. Split by Nikkei same-day < −4% and by regime (2007–12, 2013–21, 2022–26). | Haven co-movement ([Ranaldo & Söderlind](https://econpapers.repec.org/RePEc:oup:revfin:v:14:y:2010:i:3:p:385-407)); unstable since 2022. | ≈30–60 (2007–26) | SP500 via `fetch_official.py`; VIX in repo |
| **8** | **COT extreme + turn** | LF_net/OI at or below the 5th percentile on an expanding 156-week window within the last 4 weeks, and a weekly change ≥ +1.5% of OI. Short USDJPY at Mon 08:00 JST (Sun 23:00 UTC) after the Friday 15:30 ET release. Hold 4 weeks with a stop at 2 × ATR(20). Mirror for yen-long extremes. Report each trade; no tuning. | Anecdotal 2024 and 2026 episodes; no OOS test. | <15 since 2010 | In repo |

Run a separate data-acquisition track alongside. Build a TFX Click 365 retail-positioning series for a **retail liquidation rule**: short USDJPY when retail net-long share is at or above its 1-year 90th percentile and USDJPY closes below its 10-day low; hold 5 days. Pull IBKR implied volatility on CME JPY options for a **risk-reversal or implied-vol crash filter**. Neither is testable today.

### Overlays for the trend/carry position, judged by drawdown

| Overlay | Rule | Data |
|---|---|---|
| VIX regime | Full long only when VIX < 20 and below its 50-day MA. Half size at 20–30. Flat at ≥ 30 or after a 4-point daily rise. Re-enter after 5 days below the 20-day MA. | In repo |
| Vol targeting | w = min(2, 8% / σ̂), with σ̂ from HAR-RV or EWMA (λ = 0.94). Rebalance weekly. Judge against Cederburg's OOS caveat. | In repo |
| Holiday and Golden Week | When spot is above 158, half size from the last pre-holiday Tokyo close at 15:00 JST (06:00 UTC) to the first post-holiday 09:00 JST (00:00 UTC). Widen intraday stops on JP holidays. | In code |
| Post-intervention | No new directional entries T+1 to T+6. Intraday sizing to the T+0 range. Size longs above the last intervention level for a 5% gap. | In repo (through 2026-08-03) |
| Event blackouts and spread filter | No new intraday entries in the BoJ window, the 08:30 ET releases, 14:00 ET FOMC, or 16:55–17:10 ET. Skip entries for 5 min when the spread z-score exceeds 3 (live and Eightcap only). | Partly missing (0c) |

### Ideas deprioritised until the evidence or the data changes

Several ideas stay off the queue until something changes:

- **Minute-scale lead-lag** with UST, ES or Nikkei futures. Spot is now dominant, and the futures data is paid.
- **Expiry pinning and barrier trading.** There is no FX evidence and no expiry or barrier database.
- **Single-pair volatility-risk-premium timing.** The evidence is cross-sectional only.
- **Dollar-factor and basis-stress signals.** These are redundant or insignificant for the yen.
- **REER timing.** Value showed no out-of-sample contribution.
- **Intraday momentum, the overnight/NY switch and vol-filtered opening-range breakouts.** These have decayed, are cost-bound, or belong to a breakout family that has already failed.
- **Karnaukh's signalled pre-FOMC trade.** The JPY loading is insignificant, and ZQ data would be needed.
- **Pre-BoJ drift.** It rests on about five meetings.
- **Tankan and Tokyo CPI drift, JGB auction and rinban windows, February redemption flows, JGB coupon dates and dividend season.** No evidence was found for any of them.
- **Leak continuation and keyword-triggered intervention fades.** They need headline data, and the samples are tiny.
- **Asset-manager versus leveraged-fund divergence.** No source supports it.
- **Intraday ML.**

Two kinds of finding would change this. A new yen-specific out-of-sample paper would justify a test. So would a clear pattern in the Tier 0 seasonality map in one of these windows.

### Fit the harness to each rule and spend the holdout once

The existing `window_trades` harness already fits ranks 1, 3, 6 and 7 and the whole Tier 0 battery. Precompute a conditional date list for each side, such as down-gap Mondays or upward-r₅ NFP days, and call it with a fixed side and fixed clock times. Ranks 2, 4 and 5 are path-dependent (touches, detected statement minutes, stops). They need a small bar-loop simulator, or an early move to the NautilusTrader layer, with limit fills validated on the Eightcap ticks. A limit counts as filled only if the bid or ask trades through it by at least one tick.

Adapt the spec template's "effect present in 2022+" kill criterion for rare events. For weekend gaps, 2022–2024 holds only about 8 signals per side. Instead, require the same sign in 2015–2019 and 2020–2024, and treat the 2025–2026 holdout plus forward paper trading as the confirmation. Where two strategies fire at once, net the positions. On a Monday that is also a gotobi day, for example, the weekend-gap long and the gotobi pre-fix long overlap, so cap combined exposure rather than stacking two full positions.

## Conclusion

The common thread is that yen effects worth testing come from someone who has to trade at a known time and cannot wait. Examples are importers at 09:55 JST, dealers rebuilding after a weekend gap, and Japanese margin accounts hitting loss-cuts. Effects that rely on information arriving on a schedule mostly fail for the yen: the FOMC, auctions, Japanese data and fiscal year-end. The yen's dual role as a funding and a haven currency cancels the directional response to scheduled news, which is why dollar-wide results that hold for EUR or AUD keep coming back insignificant for JPY. That points the next stage of the bot towards liquidity-driven reversals and risk overlays, and away from forecasting macro direction.

The practical consequence is that infrastructure now matters more than ideas. A release and auction calendar, a seasonality baseline, a volatility model and bars that run through the July 2026 intervention will turn eight queued hypotheses into answers within weeks. Without them, any positive result risks being a time-of-day drift or a single intervention. The weekend-gap test is the one to run first. A decade of post-publication data exists for it, the move is 40 times the cost, and a positive result would give the bot a second edge that does not overlap in time with spec 001.

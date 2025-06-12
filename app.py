# # app.py
# import streamlit as st
# import pandas as pd
# import plotly.express as px
# from pathlib import Path
# import requests
# from bs4 import BeautifulSoup
# import zipfile
# import io
# import statsmodels.api as sm
# from fetch_monthly_returns import fetch_monthly_returns
# import re
# # ─── Streamlit page config MUST come first ────────────────────────────────────
# st.set_page_config(
#     page_title="🚀 Starship Finance Simulator",
#     layout="wide",
# )


# FF5_REGIONS = {
#     "us": "Fama/French North American 5 Factors",
#     "de": "Fama/French European 5 Factors",
#     "au": "Fama/French Asia Pacific ex Japan 5 Factors",
#     "nz": "Fama/French Asia Pacific ex Japan 5 Factors",
# }

# @st.cache_data(show_spinner=False)


# def fetch_ff5_urls() -> dict[str, str]:
#     URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"
#     resp = requests.get(URL)
#     resp.raise_for_status()
#     soup = BeautifulSoup(resp.text, "html.parser")

#     # 1) Find the Developed Markets header
#     header = soup.find(lambda tag: tag.name in ("h3","b")
#                                and "Developed Markets Factors and Returns" in tag.get_text())
#     if not header:
#         raise RuntimeError("Could not find Developed Markets header")

#     urls: dict[str,str] = {}
#     # 2) Process every <a> until we hit “Emerging Markets”
#     for link in header.find_all_next("a", href=re.compile(r"CSV\.zip$")):
#         block_text = link.parent.get_text(" ", strip=True)
#         # stop when we reach Emerging Markets section
#         if "Emerging Markets Factors and Returns" in block_text:
#             break
#         # only 5-factor files, skip daily
#         if "5 Factors" not in block_text or "Daily" in block_text:
#             continue

#         # chop off “TXT CSV Details” etc
#         region = re.sub(r"\s+TXT.*$", "", block_text)
#         href = link["href"]
#         if href.startswith("/"):
#             href = "https://mba.tuck.dartmouth.edu" + href
#         urls[region] = href

#     return urls

# # ── DEBUG: show exactly what region names we scraped
# st.sidebar.write("🔍 Scraped FF5 regions (raw):", list(fetch_ff5_urls().keys()))


# def compute_ff5_betas(stock_exc: pd.Series, ff5: pd.DataFrame) -> pd.Series:
#     """
#     Runs a 5‐factor regression:
#       stock_exc ~ const + (Mkt-RF) + SMB + HML + RMW + CMA
#     Returns the fitted betas (constant + 5 factor loadings).
#     """
#     # 1) align dates & drop missing
#     df = pd.concat([stock_exc, ff5[['Mkt-RF','SMB','HML','RMW','CMA']]], axis=1).dropna()

#     # 2) set up y and X
#     y = df[stock_exc.name]
#     X = sm.add_constant(df[['Mkt-RF','SMB','HML','RMW','CMA']])

#     # 3) fit OLS
#     model = sm.OLS(y, X).fit()

#     return model.params  # contains ['const','Mkt-RF','SMB','HML','RMW','CMA']


# def compute_capm_beta(stock_exc: pd.Series, ff5: pd.DataFrame) -> float:
#     """
#     Runs a CAPM regression:
#       stock_exc ~ const + (Mkt-RF)
#     Returns the market beta (slope on Mkt-RF).
#     """
#     df = pd.concat([stock_exc, ff5[['Mkt-RF']]], axis=1).dropna()
#     y = df[stock_exc.name]
#     X = sm.add_constant(df['Mkt-RF'])
#     model = sm.OLS(y, X).fit()
#     return float(model.params['Mkt-RF'])



# # ─── 1) Existing loader/grabber ────────────────────────────────────────────
# YEAR_ROW = 10
# COLS     = list(range(1,16))

# def load_sheet(xlsx: Path, sheet: str):
#     try:
#         df = pd.read_excel(xlsx, sheet_name=sheet, header=None, engine="openpyxl")
#     except:
#         return None, None
#     if df.shape[0] <= YEAR_ROW or df.shape[1] <= max(COLS):
#         return None, None
#     years = df.iloc[YEAR_ROW, COLS].astype(int).tolist()
#     return df, years

# def grab_series(xlsx: Path, sheet: str, regex: str):
#     df, years = load_sheet(xlsx, sheet)
#     if df is None:
#         return None
#     col0 = df.iloc[:,0].astype(str).str.lower()
#     mask = col0.str.contains(regex, regex=True, na=False)
#     if not mask.any():
#         return None
#     row = df.loc[mask, :].iloc[0]
#     return pd.to_numeric(row.iloc[COLS], errors="coerce").tolist()

# # ─── 2) Build dataset ───────────────────────────────────────────────────────────
# @st.cache_data
# def build_dataset():
#     # debug: show how each Country maps to an FF5 region key
# #     st.write(
# #     "Region mapping:",
# #     df["Country"]
# #       .str.lower()
# #       .map(FF5_REGIONS)
# #       .dropna()
# #       .unique()
# # )
#     base = Path(__file__).parent
#     rows = []

#     for xlsx in base.rglob("*.xlsx"):
#         ticker = xlsx.stem

#         # ── 1.1) Determine country ───────────────────────────────────────────────
#             # ── 1.1) Determine country from parent folder ─────────────────────────
#         country = xlsx.parent.name.lower()

#         # ── 1.2) Get years ─────────────────────────────────────────────────────────
#         _, years = load_sheet(xlsx, "Income Statement")
#         if years is None:
#             continue

#         # ── 1.3) Pretax & cash taxes paid ─────────────────────────────────────────
#         pretax  = grab_series(xlsx, "Income Statement", r"income (?:before|pre)[ -]tax")
#         taxcash = grab_series(xlsx, "Cash Flow",        r"income taxes.*paid")

#         # ── 1.4) Effective tax‐rate per year ─────────────────────────────────────
#         if pretax and taxcash:
#             tax_rate_series = [
#                 (t / p) if p not in (0, None) else 0.0
#                 for p, t in zip(pretax, taxcash)
#             ]
#         else:
#             tax_rate_series = [0.0] * len(years)

#         # ── 1.5) Grab core series ─────────────────────────────────────────────────
#         ebitda   = grab_series(xlsx, "Income Statement",  r"earnings before.*ebitda")
#         capex    = grab_series(xlsx, "Cash Flow",          r"capital expenditure|capex")
#         debt     = grab_series(xlsx, "Balance Sheet",      r"total debt|debt\b")
#         cash     = grab_series(xlsx, "Balance Sheet",      r"cash and cash equivalents|cash$")
#         ev       = grab_series(xlsx, "Financial Summary",  r"^enterprise value\s*$")
#         taxes_cf = grab_series(xlsx, "Cash Flow",          r"income taxes\s*-\s*paid")

#         # ── 1.6) Skip if any core series is missing ───────────────────────────────
#         if None in (ebitda, capex, debt, cash, ev, taxes_cf):
#             continue

#         # ── 1.7) Compute ΔNWC ─────────────────────────────────────────────────────
#         curr_assets = grab_series(xlsx, "Balance Sheet", r"total current assets")
#         curr_liab   = grab_series(xlsx, "Balance Sheet", r"total current liabilities")
#         if curr_assets and curr_liab:
#             nwc = [a - l for a, l in zip(curr_assets, curr_liab)]
#             change_in_nwc = [0] + [nwc[i] - nwc[i-1] for i in range(1, len(nwc))]
#         else:
#             change_in_nwc = [0] * len(years)

#         # ── 1.8) Interest expense ─────────────────────────────────────────────────
#         ie_is = grab_series(xlsx, "Income Statement", r"interest expense|finance costs")
#         ie_cf = grab_series(xlsx, "Cash Flow",        r"interest\s*paid")
#         interest_expense = ie_is if ie_is is not None else (ie_cf or [0] * len(years))

#         # ── 1.9) Assemble one row per year ───────────────────────────────────────
#         for i, (y,e,c,d,ca,v,t,nwc0,ie) in enumerate(zip(
#             years, ebitda, capex, debt, cash, ev, taxes_cf,
#             change_in_nwc, interest_expense
#         )):
#             rows.append({
#                 "Ticker":          ticker,
#                 "Country":         country,
#                 "Year":            y,
#                 "EBITDA":          e,
#                 "CapEx":           c,
#                 "Debt":            d,
#                 "Cash":            ca,
#                 "EV":              v,
#                 "CashTaxesPaid":   t,
#                 "ChangeNWC":       nwc0,
#                 "InterestExpense": ie,
#                 "tax_rate":        tax_rate_series[i],
#             })

#     # ────────────────────────────────────────────────────────────────────────────
#     # 2) Build DataFrame & post-process
#     # ────────────────────────────────────────────────────────────────────────────
#     df = pd.DataFrame(rows)
#     if df.empty:
#         return df

#     df["ΔDebt"] = df.groupby("Ticker")["Debt"].diff().fillna(0)
#     df["ΔCash"] = df.groupby("Ticker")["Cash"].diff().fillna(0)

#     df["FCFF"] = (
#         df["EBITDA"]
#       - df["CashTaxesPaid"]
#       - df["ChangeNWC"]
#       - df["CapEx"]
#     )
#     df["FCFE"] = (
#         df["FCFF"]
#       - df["InterestExpense"] * (1 - df["tax_rate"])
#       + df["ΔDebt"]
#       - df["ΔCash"]
#     )
#     df["FCF"]  = (
#         df["EBITDA"]
#       - df["CashTaxesPaid"]
#       - df["ChangeNWC"]
#       - df["CapEx"]
#     )
#     df["EV/EBITDA"] = df["EV"] / df["EBITDA"].replace(0, pd.NA)

#     return df



# # ─── 2) Page setup & CSS ───────────────────────────────────────────────────────

# st.markdown("""
# <style>
#   /* 1) Import a sci-fi font */
#   @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700&display=swap');

#   /* 2) Background & base text */
#   body {
#     background: radial-gradient(circle at center, #000011, #000);
#     color: #39ff14;
#     font-family: 'Orbitron', monospace;
#   }

#   /* 3) Make your metric cards wider and neon-glow */
#   .stMetric {
#   flex: 0 0 130px !important;
#   min-width: 130px !important;
#   max-width: 130px !important;

#   /* make every card the same height */
#   min-height: 113px !important;

#   /* your existing styles */
#   background: rgba(0, 0, 30, 0.8) !important;
#   border: 2px solid #0ff !important;
#   border-radius: 12px !important;
#   padding: 8px !important;
#   box-shadow: 0 0 8px #0ff, 0 0 16px #39ff14 !important;

#   /* center value+delta vertically */
#   display: flex !important;
#   flex-direction: column !important;
#   justify-content: center !important;
# }


#   /* Neon glow on the numbers */
#   .stMetric .value {
#     font-size: 1.6rem !important;
#     text-shadow: 0 0 4px #39ff14 !important;
#   }
#   .stMetric .delta {
#     font-size: 1.1rem !important;
#     text-shadow: 0 0 4px #0ff !important;
#   }

#   /* 4) Force each metric-row into a no-wrap, scrollable flex strip */
#   /* ─── Force each metric card to the same size ───────────────────────────────── */
# .stMetric {
#   flex: 0 0 220px !important;     /* exact width for every card */
#   min-width: 220px !important;
#   max-width: 220px !important;
#   margin: 0 !important;           /* reset any default margins */
# }

# /* ─── Evenly distribute the cards in each row ───────────────────────────────── */
# section[data-testid="metric-container"] > div {
#   display: flex !important;
#   flex-wrap: nowrap !important;
#   justify-content: space-evenly !important;
#   align-items: stretch !important;
#   gap: 16px !important;           /* space between cards */
#   overflow-x: auto !important;    /* keep horizontal scroll if viewport too narrow */
#   padding-bottom: 12px;           /* breathing room below */
#   margin-bottom: 24px;            /* space under each row heading */
# }


#   /* 5) Tweak slider labels */
#   .stSlider > div > div > label {
#     color: #0ff !important;
#   }
# </style>
            


# """, unsafe_allow_html=True)
# st.sidebar.write("🔍 Scraped FF5 regions:", list(fetch_ff5_urls().keys()))



# df = build_dataset()
# # debug: list all available FF-5 region keys that were fetched
# st.write("Available FF-5 regions:", list(fetch_ff5_urls().keys()))

# if df.empty:
#     st.error("❌ No data found. Check your folders/sheets.")
#     st.stop()
# if df.empty:
#     st.error("❌ No data found. Check your folders/sheets.")
#     st.stop()

# # ─── 3) Sidebar: selectors & sliders ────────────────────────────────────────────
# tickers     = sorted(df["Ticker"].unique())
# sel_tickers = st.sidebar.multiselect("🔍 Companies", options=tickers, default=[])
# if not sel_tickers:
#     st.sidebar.info("Please select at least one company to continue.")
#     st.stop()

# years_avail  = df[df.Ticker.isin(sel_tickers)]["Year"].dropna().unique()
# years_sorted = sorted(int(y) for y in years_avail)
# if not years_sorted:
#     st.sidebar.error("No years available for the selected companies.")
#     st.stop()

# sel_year = st.sidebar.slider(
#     "📅 Year",
#     min_value=years_sorted[0],
#     max_value=years_sorted[-1],
#     value=years_sorted[-1]
# )

# st.sidebar.markdown("### 🎛 Simulations")
# ebt_adj  = st.sidebar.slider("EBITDA Δ%", -50, 50, 0)
# cpx_adj  = st.sidebar.slider("CapEx Δ%",  -50, 50, 0)
# debt_adj = st.sidebar.slider("Debt Δ%",   -50, 50, 0)
# cash_adj = st.sidebar.slider("Cash Δ%",   -50, 50, 0)
# nwc_adj  = st.sidebar.slider("NWC Δ%",    -50, 50, 0)

# # ── 3.5) Equity model choice ─────────────────────────────────────────────────
# st.sidebar.markdown("### 🔬 Equity Model")
# equity_model = st.sidebar.radio(
#     "Select Cost-of-Equity model",
#     options=["CAPM", "FF5", "Both"],
#     index=0
# )


#     # ── 3.6) Auto‐map FF5 region based on selected stock’s country ───────────────
# country = df.loc[df.Ticker == sel_tickers[0], "Country"].iat[0].lower()
# region_key = FF5_REGIONS.get(country)
# # ── DEBUG ───────────────────────────────────────────────────────────────
# urls = fetch_ff5_urls()

# st.sidebar.write("🔍 Mapped region_key:", region_key)
# if region_key is None:
#     st.sidebar.error(f"No FF5 region mapped for country '{country}'")
#     st.stop()
# @st.cache_data(show_spinner=False)
# def load_ff5_factors(region_key: str) -> pd.DataFrame:
#     """
#     Downloads and parses the FF5 CSV for the given region.
#     """
#     urls = fetch_ff5_urls()
#     if region_key not in urls:
#         raise ValueError(f"No FF5 URL found for region '{region_key}'")
#     csv_url = urls[region_key]

#     resp = requests.get(csv_url)
#     resp.raise_for_status()

#     df = pd.read_csv(
#         io.StringIO(resp.text),
#         skiprows=3,           # drop the three header lines
#         index_col=0,
#         parse_dates=True
#     )
#     df.columns = df.columns.str.strip()
#     return df


# # ── 3.7) Download & load that region’s FF5 factors ──────────────────────────
# # ── 3.7) Download & load that region’s FF5 factors ──────────────────────────
# urls = fetch_ff5_urls()
# st.sidebar.write("🔍 Scraped FF5 URLs:", list(urls.items()))
# ff5  = load_ff5_factors(region_key)




# # ── 3.8) Fetch stock’s monthly returns ─────────────────────────────────────
# start_date = f"{sel_year-5}-01-01"
# end_date   = f"{sel_year}-12-31"

# # grab returns for the first selected ticker
# returns = fetch_monthly_returns(
#     tickers=[sel_tickers[0]],
#     start=start_date,
#     end=end_date
# )
# st.sidebar.write("Sample stock returns:", returns.tail(2))

# base = df.query("Year == @sel_year and Ticker in @sel_tickers").copy()
# if base.empty:
#     st.warning("No data for that selection.")
#     st.stop()
# sim  = base.copy()
# # ────────────────────────────────────────────
# for ticker in sel_tickers:
    
#     # isolate this ticker’s data
#     t_base    = base[base.Ticker == ticker]
#     t_sim     = sim[sim.Ticker == ticker]
    
#     # ¶ fetch its excess returns
#     rets      = fetch_monthly_returns(
#                    tickers=[ticker],
#                    start=start_date,
#                    end=end_date
#                )
#     stock_exc = rets[ticker] - ff5["RF"]
    
#     # ¶ run the regressions
#     ff5_beta  = compute_ff5_betas(stock_exc, ff5)
#     capm_beta = compute_capm_beta(stock_exc, ff5)

#     # ── store these betas on our sim DataFrame for metrics display ──
#     sim.loc[sim.Ticker == ticker, "ff5_beta"]  = ff5_beta["Mkt-RF"]
#     sim.loc[sim.Ticker == ticker, "capm_beta"] = capm_beta


#     # ¶ display in sidebar
#     st.sidebar.markdown(f"### 📈 Betas for {ticker}")
#     if equity_model in ("FF5","Both"):
#         st.sidebar.write(f"FF5 β: {ff5_beta['Mkt-RF']:.3f}")
#     if equity_model in ("CAPM","Both"):
#         st.sidebar.write(f"CAPM β: {capm_beta:.3f}")
# # ─── 4) Filter & simulate ───────────────────────────────────────────────────────



# # ─── compute historical EV & net debt, and set unlevered multiple ─────────────
# hist_ev       = base["EV"].sum(skipna=True)
# hist_ebit     = base["EBITDA"].sum(skipna=True)
# hist_net_debt = base["Debt"].sum(skipna=True) - base["Cash"].sum(skipna=True)
# unlev_ev      = hist_ev - hist_net_debt
# ev_mult       = (unlev_ev / hist_ebit) if hist_ebit else 0.0


# sim = base.copy()
# for col, pct in [("EBITDA", ebt_adj),
#                  ("CapEx",  cpx_adj),
#                  ("Debt",   debt_adj),
#                  ("Cash",   cash_adj)]:
#     sim[col] = sim[col] * (1 + pct / 100)

# # apply the NWC % slider BEFORE OCF
# sim["ChangeNWC"]      = base["ChangeNWC"] * (1 + nwc_adj / 100)
# st.write("DEBUG ChangeNWC:", sim["ChangeNWC"].tolist())

# # keep the historical cash taxes constant unless you add a slider for it
# sim["CashTaxesPaid"]  = base["CashTaxesPaid"]

# # 1) recalc OCF = EBITDA – CashTaxesPaid – ΔNWC (ΔNWC still zero in this simple sim)
# sim["OCF"]   =    (      sim["EBITDA"] - sim["CashTaxesPaid"]- sim["ChangeNWC"])

# # 2) FCF = OCF – CapEx
# sim["FCF"]            = sim["OCF"] - sim["CapEx"]
# st.write("🔍 sim FCF after NWC adj:", sim["FCF"].tolist())

# # 3) EV and EV/EBITDA 

# # recompute sim net‐debt
# sim_net_debt = sim["Debt"] - sim["Cash"]

# # EV = EBITDA × unlevered‐multiple + change in net debt
# sim["EV"] = sim["EBITDA"] * ev_mult + (sim_net_debt - hist_net_debt)

# # sim["EV"] = sim["EBITDA"] * ev_mult

# sim["EV/EBITDA"]      = sim["EV"] / sim["EBITDA"].replace(0, pd.NA)



# # ─── 5) Top metrics: two‐row panels, 5 columns each ────────────────────────────
# hist_metrics = [
#     ("EBITDA",    "EBITDA",         "$ {:,.0f}"),
#     ("CapEx",     "CapEx",          "$ {:,.0f}"),
#     ("FCF",       "FCF",            "$ {:,.0f}"),
#     ("FCFF",      "FCFF",           "$ {:,.0f}"),    
#     ("FCFE",      "FCFE",           "$ {:,.0f}"),    
#     ("EV",        "EV",             "$ {:,.0f}"),
#     ("EV/EBITDA", "EV/EBITDA",      "{:.2f}x"),
#     # ────────────────────────────────────────────────────────────────
#     ("Debt",      "Debt",           "$ {:,.0f}"),
#     ("Cash",      "Cash",           "$ {:,.0f}"),
#     ("ΔNWC",      "ChangeNWC",      "$ {:,.0f}"),
#     ("Interest",  "InterestExpense","$ {:,.0f}M"),
#     ("Tax Rate",  "tax_rate",    "{:.1%}"), 
    
# ]

# # first 5 always go on row 1, next 4 on row 2 (with one blank placeholder)
# # two rows of 5 metrics each
# first5 = hist_metrics[:5]
# rest5  = hist_metrics[5:10]    # exactly the other five


#     # Row 2: next 4 + blank
# cols = st.columns(5)
# for (label, field, fmt), col in zip(rest5, cols):
#         if label is None:
#             col.write("")  # placeholder
#         else:
#             hist_val = base[field].sum(skipna=True)
#             sim_val  = sim[field].sum(skipna=True)
#             delta = ""
#             if pd.notna(hist_val) and pd.notna(sim_val) and hist_val:
#                 delta = f"{sim_val/hist_val - 1:+.1%}"
#             col.metric(label, fmt.format(sim_val) if pd.notna(sim_val) else "n/a", delta,
#                        help="FCF = EBITDA − CapEx" if field=="FCF" else "")




# # ─── 6) 3D Simulation: EBITDA vs CapEx vs EV ───────────────────────────────────
# st.markdown("### 🔭 3D Simulation: EBITDA vs CapEx vs EV")

# # 1) build combined DataFrame (must come after sim["FCF"] is recalculated)
# plot_df = pd.concat([
#     base.assign(Type="Base"),
#     sim.assign(Type="Simulated"),
# ])
# plot_df["FCF_mag"]   = plot_df["FCF"].abs().fillna(0)
# plot_df["FCF_label"] = plot_df["FCF"].apply(lambda x: "Positive" if x >= 0 else "Negative")

# # 2) compute raw min/max for each axis
# eb_min, eb_max = plot_df["EBITDA"].min(), plot_df["EBITDA"].max()
# cx_min, cx_max = plot_df["CapEx"].min(),  plot_df["CapEx"].max()
# ev_min, ev_max = plot_df["EV"].min(),     plot_df["EV"].max()

# # 3) add padding so the cube isn’t cramped
# pad = 0.05
# def padded(rmin, rmax, pad):
#     span = rmax - rmin
#     if span == 0:
#         buffer = abs(rmin) * pad if rmin != 0 else 1
#         return [rmin - buffer, rmax + buffer]
#     return [rmin - pad * span, rmax + pad * span]
# x_range = padded(eb_min, eb_max, pad)
# y_range = padded(cx_min, cx_max, pad)
# z_range = padded(ev_min, ev_max, 0.001)

# # 4) draw the 3D scatter, sizing by the updated FCF_mag
# fig3d = px.scatter_3d(
#     plot_df,
#     x="EBITDA", y="CapEx", z="EV",
#     color="FCF_label",
#     color_discrete_map={"Negative":"red","Positive":"green"},
#     symbol="Type",
#     size="FCF_mag",
#     size_max=26,                # ↑ bigger max so changes are obvious
#     hover_name="Ticker",
#     hover_data={
#         "Type":      True,
#         "EBITDA":    ":.2f",
#         "CapEx":     ":.2f",
#         "EV":        ":.2f",
#         "Debt":      ":.2f",
#         "Cash":      ":.2f",
#         "EV/EBITDA": ":.2f",
#         "FCF":       ":.2f",
#         "FCF_mag":   ":.4f",      # show magnitude to 4 decimals
#     },
#     template="plotly_dark",
#     title=f"Year {sel_year}: Base vs Simulated"
# )

# # 5) add the cube wireframe
# import plotly.graph_objects as go
# x0, x1 = x_range; y0, y1 = y_range; z0, z1 = z_range
# cube_x = [x0,x1,None, x1,x1,None, x1,x0,None, x0,x0,  x0,x1,None, x1,x1,None, x1,x0,None, x0,x0,  x0,x0,None, x1,x1,None, x1,x1,None, x0,x0]
# cube_y = [y0,y0,None, y0,y1,None, y1,y1,None, y1,y0,  y0,y0,None, y0,y1,None, y1,y1,None, y1,y0,  y0,y0,None, y1,y1,None, y1,y1,None, y0,y0]
# cube_z = [z0,z0,None, z0,z0,None, z0,z0,None, z0,z0,  z1,z1,None, z1,z1,None, z1,z1,None, z1,z1,  z0,z1,None, z0,z1,None, z0,z1,None, z0,z1]
# fig3d.add_trace(go.Scatter3d(
#     x=cube_x, y=cube_y, z=cube_z,
#     mode='lines',
#     line=dict(color="rgba(200,200,200,0.3)", width=1),
#     showlegend=False
# ))

# # 6) lock axis ranges + view
# fig3d.update_layout(
#     margin=dict(l=0,r=0,t=40,b=0),
#     width=800, height=600,
#     uirevision="fixed_view",
#     scene=dict(
#         aspectmode="cube",
#         xaxis=dict(autorange=False, range=x_range, showbackground=True, backgroundcolor="rgba(20,20,20,0.5)"),
#         yaxis=dict(autorange=False, range=y_range, showbackground=True, backgroundcolor="rgba(20,20,20,0.5)"),
#         zaxis=dict(autorange=False, range=z_range, showbackground=True, backgroundcolor="rgba(20,20,20,0.5)"),
#         camera=dict(eye=dict(x=1.8,y=1.4,z=1.2))
#     )
# )

# # 7) render it
# st.plotly_chart(fig3d, use_container_width=True)


# # ─── 7) EV/EBITDA & FCF Over Time ───────────────────────────────────────────────
# st.markdown("### 🔄 EV/EBITDA & FCF Over Time")
# time_df = df[df.Ticker.isin(sel_tickers)].copy()
# time_df["FCF"] = time_df["EBITDA"] - time_df["CapEx"]
# fig2 = px.line(
#     time_df, x="Year", y=["FCF","EV/EBITDA"],
#     color="Ticker", markers=True,
#     template="plotly_dark",
#     labels={
#         "value":"FCF (USD) / EV/EBITDA (x)",
#         "variable":"Metric",
#         "Ticker":"Company",
#     },
# )
# st.plotly_chart(fig2, use_container_width=True)

# # ─── 8) Data Table ─────────────────────────────────────────────────────────────
# st.markdown("### 📊 Data Table")
# st.dataframe(
#     sim[[
#         "Ticker","Year","EBITDA","CapEx",
#         "FCF","FCFF","FCFE",
#         "ChangeNWC","InterestExpense",
#         "EV","EV/EBITDA","Debt","Cash"
#     ]],
#     use_container_width=True, height=300
# )

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import zipfile
import io
import statsmodels.api as sm
from fetch_monthly_returns import fetch_monthly_returns, fetch_risk_free_rate, calculate_excess_returns
from fetch_ff5_urls import fetch_ff5_urls, download_and_extract_ff5_data
from fetch_damodaran_betas import fetch_damodaran_industry_betas, find_industry_beta, calculate_wacc_with_industry_beta
import re
import time
import numpy as np
import os
import uuid
from database import (
    init_database, store_financial_data, store_company_info, store_factor_data,
    store_beta_analysis, store_simulation, store_stock_returns, get_financial_data,
    get_factor_data, get_latest_beta_analysis, get_simulation_history, get_companies
)

# Page config
st.set_page_config(
    page_title="🚀 Starship Finance Simulator",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for the exact interface shown in screenshots
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Dark theme matching screenshots */
    .stApp {
        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%);
        color: #ffffff;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background: #1a1a2e;
        border-right: 1px solid #333;
    }
    
    /* Metric cards like in screenshots */
    .metric-card {
        background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
        border: 1px solid #3b82f6;
        border-radius: 8px;
        padding: 15px;
        margin: 5px;
        text-align: center;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .metric-title {
        font-size: 12px;
        font-weight: 500;
        color: #94a3b8;
        margin-bottom: 5px;
    }
    
    .metric-value {
        font-size: 24px;
        font-weight: 700;
        color: #ffffff;
    }
    
    .metric-change {
        font-size: 14px;
        margin-top: 5px;
    }
    
    .metric-change.positive {
        color: #10b981;
    }
    
    .metric-change.negative {
        color: #ef4444;
    }
    
    /* Section headers */
    .section-header {
        font-size: 20px;
        font-weight: 600;
        color: #ffffff;
        margin: 20px 0 15px 0;
        padding-bottom: 5px;
        border-bottom: 1px solid #374151;
    }
    
    /* Beta display cards */
    .beta-card {
        background: linear-gradient(135deg, #059669 0%, #10b981 100%);
        border: 1px solid #34d399;
        border-radius: 8px;
        padding: 15px;
        margin: 5px;
        text-align: center;
        color: white;
    }
    
    .beta-title {
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 5px;
    }
    
    .beta-value {
        font-size: 20px;
        font-weight: 700;
    }
    
    /* Toggle styling */
    .model-toggle {
        background: #374151;
        border-radius: 8px;
        padding: 10px;
        margin: 10px 0;
    }
    
    /* WACC display */
    .wacc-display {
        background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%);
        border: 1px solid #c084fc;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        margin: 20px 0;
    }
    
    .wacc-title {
        font-size: 16px;
        font-weight: 500;
        margin-bottom: 10px;
    }
    
    .wacc-value {
        font-size: 32px;
        font-weight: 700;
        color: #ffffff;
    }
    
    /* DCF Valuation card styling */
    .valuation-card {
        background: linear-gradient(135deg, #2d1b69 0%, #11998e 100%);
        border: 1px solid #00ff88;
        border-radius: 15px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 0 25px rgba(0, 255, 136, 0.4);
        animation: pulse-green 3s ease-in-out infinite;
    }
    
    .valuation-header {
        color: #00ff88;
        font-size: 16px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 15px;
        text-align: center;
    }
    
    .valuation-metric {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 10px 0;
        padding: 8px 0;
        border-bottom: 1px solid rgba(0, 255, 136, 0.2);
    }
    
    .metric-label {
        color: #a0a0a0;
        font-size: 14px;
        font-weight: 500;
    }
    
    .metric-value {
        color: #ffffff;
        font-size: 18px;
        font-weight: 700;
        text-shadow: 0 0 8px rgba(0, 255, 136, 0.6);
    }
    
    @keyframes pulse-green {
        0%, 100% { box-shadow: 0 0 25px rgba(0, 255, 136, 0.4); }
        50% { box-shadow: 0 0 35px rgba(0, 255, 136, 0.6); }
    }
</style>
""", unsafe_allow_html=True)

# Country to FF5 region mapping
FF5_REGIONS = {
    "us": "Fama/French North American 5 Factors",
    "de": "Fama/French European 5 Factors", 
    "au": "Fama/French Asia Pacific ex Japan 5 Factors",
    "nz": "Fama/French Asia Pacific ex Japan 5 Factors",
}

@st.cache_data
def load_ff5_data(region_name: str) -> pd.DataFrame:
    """Load FF5 factor data from downloaded files"""
    data_dir = Path("ff5_data")
    if not data_dir.exists():
        return None
    
    # Clean region name for filename matching
    clean_name = re.sub(r'[^\w\s-]', '', region_name).strip()
    clean_name = re.sub(r'[-\s]+', '_', clean_name)
    
    file_path = data_dir / f"{clean_name}.txt"
    if not file_path.exists():
        return None
    
    try:
        # Read FF5 data file (skip header rows, parse dates)
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find data section (typically after several header lines)
        lines = content.split('\n')
        data_start = 0
        for i, line in enumerate(lines):
            if re.match(r'^\s*\d{6}', line):  # Look for YYYYMM format
                data_start = i
                break
        
        if data_start == 0:
            return None
        
        # Parse the data
        data_lines = []
        for line in lines[data_start:]:
            if line.strip() and not line.strip().startswith('Copyright'):
                parts = line.strip().split()
                if len(parts) >= 6 and parts[0].isdigit():
                    data_lines.append(parts)
        
        if not data_lines:
            return None
        
        # Create DataFrame
        df = pd.DataFrame(data_lines, columns=['Date', 'Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA', 'RF'])
        
        # Convert date and numeric columns
        df['Date'] = pd.to_datetime(df['Date'], format='%Y%m')
        for col in ['Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA', 'RF']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df.set_index('Date', inplace=True)
        return df
        
    except Exception as e:
        st.error(f"Error loading FF5 data: {e}")
        return None

@st.cache_data
def compute_ff5_betas(stock_returns: pd.Series, ff5_data: pd.DataFrame) -> dict:
    """Compute Fama/French 5-factor betas"""
    try:
        # Align data
        combined = pd.concat([stock_returns, ff5_data[['Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA']]], axis=1).dropna()
        
        if len(combined) < 24:  # Need at least 2 years of data
            return None
        
        # Set up regression
        y = combined[stock_returns.name]
        X = sm.add_constant(combined[['Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA']])
        
        # Run regression
        model = sm.OLS(y, X).fit()
        
        return {
            'alpha': float(model.params['const']),
            'market_beta': float(model.params['Mkt-RF']),
            'smb_beta': float(model.params['SMB']),
            'hml_beta': float(model.params['HML']),
            'rmw_beta': float(model.params['RMW']),
            'cma_beta': float(model.params['CMA']),
            'r_squared': float(model.rsquared),
            'observations': len(combined)
        }
    except Exception as e:
        st.error(f"Error computing FF5 betas: {e}")
        return None

@st.cache_data  
def compute_capm_beta(stock_returns: pd.Series, ff5_data: pd.DataFrame) -> dict:
    """Compute CAPM beta"""
    try:
        # Align data
        combined = pd.concat([stock_returns, ff5_data[['Mkt-RF']]], axis=1).dropna()
        
        if len(combined) < 12:
            return None
        
        # Set up regression
        y = combined[stock_returns.name]
        X = sm.add_constant(combined['Mkt-RF'])
        
        # Run regression
        model = sm.OLS(y, X).fit()
        
        return {
            'alpha': float(model.params['const']),
            'market_beta': float(model.params['Mkt-RF']),
            'r_squared': float(model.rsquared),
            'observations': len(combined)
        }
    except Exception as e:
        st.error(f"Error computing CAPM beta: {e}")
        return None

def calculate_wacc(market_beta: float, risk_free_rate: float = 0.03, market_premium: float = 0.06, 
                  debt_ratio: float = 0.3, cost_of_debt: float = 0.05, tax_rate: float = 0.25) -> float:
    """Calculate WACC using beta"""
    cost_of_equity = risk_free_rate + market_beta * market_premium
    wacc = (1 - debt_ratio) * cost_of_equity + debt_ratio * cost_of_debt * (1 - tax_rate)
    return wacc

def calculate_terminal_value(final_fcf: float, growth_rate: float, discount_rate: float) -> float:
    """Calculate terminal value using Gordon Growth Model"""
    if discount_rate <= growth_rate:
        return 0  # Invalid assumption
    return final_fcf * (1 + growth_rate) / (discount_rate - growth_rate)

def calculate_dcf_valuation(cash_flows: list, discount_rate: float, terminal_growth: float = 0.025) -> dict:
    """
    Calculate DCF valuation for both FCFF and FCFE
    
    Args:
        cash_flows: List of annual cash flows
        discount_rate: WACC for FCFF or Cost of Equity for FCFE
        terminal_growth: Long-term growth rate (default 2.5%)
    
    Returns:
        Dict with present values, terminal value, and enterprise/equity value
    """
    if not cash_flows or len(cash_flows) < 2:
        return {"error": "Insufficient cash flow data"}
    
    # Project next 5 years based on historical growth
    historical_growth = []
    for i in range(1, len(cash_flows)):
        if cash_flows[i-1] != 0:
            growth = (cash_flows[i] - cash_flows[i-1]) / abs(cash_flows[i-1])
            historical_growth.append(growth)
    
    # Average historical growth, capped at reasonable bounds
    if historical_growth:
        avg_growth = np.median(historical_growth)
        avg_growth = max(min(avg_growth, 0.15), -0.10)  # Cap between -10% and 15%
    else:
        avg_growth = 0.05  # Default 5% growth
    
    # Project future cash flows
    last_cf = cash_flows[-1]
    projected_cfs = []
    
    for year in range(1, 6):  # 5-year projection
        projected_cf = last_cf * ((1 + avg_growth) ** year)
        projected_cfs.append(projected_cf)
    
    # Calculate present values
    pv_projected = []
    for i, cf in enumerate(projected_cfs, 1):
        pv = cf / ((1 + discount_rate) ** i)
        pv_projected.append(pv)
    
    # Terminal value
    terminal_cf = projected_cfs[-1]
    terminal_value = calculate_terminal_value(terminal_cf, terminal_growth, discount_rate)
    pv_terminal = terminal_value / ((1 + discount_rate) ** 5)
    
    # Total enterprise/equity value
    total_pv = sum(pv_projected) + pv_terminal
    
    return {
        "projected_cash_flows": projected_cfs,
        "pv_projected_cfs": pv_projected,
        "terminal_value": terminal_value,
        "pv_terminal": pv_terminal,
        "total_value": total_pv,
        "historical_growth": avg_growth,
        "terminal_growth": terminal_growth
    }

def calculate_intrinsic_stock_price(ticker_data: pd.DataFrame, wacc: float, cost_of_equity: float, 
                                  shares_outstanding: float = None) -> dict:
    """
    Calculate intrinsic stock price using both FCFF and FCFE models
    
    Args:
        ticker_data: DataFrame with financial data
        wacc: Weighted Average Cost of Capital
        cost_of_equity: Cost of Equity
        shares_outstanding: Number of shares outstanding (if known)
    
    Returns:
        Dict with valuation results for both models
    """
    results = {}
    
    # Get cash flows (remove NaN values)
    fcff_values = ticker_data['FCFF'].dropna().tolist()
    fcfe_values = ticker_data['FCFE'].dropna().tolist()
    
    if len(fcff_values) >= 2:
        # FCFF Model (Enterprise Value)
        fcff_valuation = calculate_dcf_valuation(fcff_values, wacc)
        
        if "error" not in fcff_valuation:
            # Convert to equity value (subtract net debt)
            latest_data = ticker_data.iloc[-1]
            net_debt = latest_data.get('Debt', 0) - latest_data.get('Cash', 0)
            equity_value_fcff = fcff_valuation['total_value'] - net_debt
            
            results['fcff_model'] = {
                'enterprise_value': fcff_valuation['total_value'],
                'net_debt': net_debt,
                'equity_value': equity_value_fcff,
                'valuation_details': fcff_valuation
            }
            
            if shares_outstanding:
                results['fcff_model']['price_per_share'] = equity_value_fcff / shares_outstanding
    
    if len(fcfe_values) >= 2:
        # FCFE Model (Direct Equity Value)
        fcfe_valuation = calculate_dcf_valuation(fcfe_values, cost_of_equity)
        
        if "error" not in fcfe_valuation:
            results['fcfe_model'] = {
                'equity_value': fcfe_valuation['total_value'],
                'valuation_details': fcfe_valuation
            }
            
            if shares_outstanding:
                results['fcfe_model']['price_per_share'] = fcfe_valuation['total_value'] / shares_outstanding
    
    return results

# Existing data loading functions
YEAR_ROW = 10
COLS = list(range(1, 16))

def load_sheet(xlsx: Path, sheet: str):
    try:
        df = pd.read_excel(xlsx, sheet_name=sheet, header=None, engine="openpyxl")
    except:
        return None, None
    if df.shape[0] <= YEAR_ROW or df.shape[1] <= max(COLS):
        return None, None
    years = df.iloc[YEAR_ROW, COLS].astype(int).tolist()
    return df, years

def grab_series(xlsx: Path, sheet: str, regex: str):
    df, years = load_sheet(xlsx, sheet)
    if df is None:
        return None
    col0 = df.iloc[:,0].astype(str).str.lower()
    mask = col0.str.contains(regex, regex=True, na=False)
    if not mask.any():
        return None
    row = df.loc[mask, :].iloc[0]
    return pd.to_numeric(row.iloc[COLS], errors="coerce").tolist()

@st.cache_data
def build_dataset():
    base = Path(__file__).parent
    rows = []

    for xlsx in base.rglob("*.xlsx"):
        ticker = xlsx.stem
        country = xlsx.parent.name.lower()

        _, years = load_sheet(xlsx, "Income Statement")
        if years is None:
            continue

        pretax = grab_series(xlsx, "Income Statement", r"income (?:before|pre)[ -]tax")
        taxcash = grab_series(xlsx, "Cash Flow", r"income taxes.*paid")

        if pretax and taxcash:
            tax_rate_series = [
                (t / p) if p not in (0, None) else 0.0
                for p, t in zip(pretax, taxcash)
            ]
        else:
            tax_rate_series = [0.0] * len(years)

        ebitda = grab_series(xlsx, "Income Statement", r"earnings before.*ebitda")
        capex = grab_series(xlsx, "Cash Flow", r"capital expenditure|capex")
        debt = grab_series(xlsx, "Balance Sheet", r"total debt|debt\b")
        cash = grab_series(xlsx, "Balance Sheet", r"cash and cash equivalents|cash$")
        ev = grab_series(xlsx, "Financial Summary", r"^enterprise value\s*$")
        taxes_cf = grab_series(xlsx, "Cash Flow", r"income taxes\s*-\s*paid")

        if None in (ebitda, capex, debt, cash, ev, taxes_cf):
            continue

        curr_assets = grab_series(xlsx, "Balance Sheet", r"total current assets")
        curr_liab = grab_series(xlsx, "Balance Sheet", r"total current liabilities")
        if curr_assets and curr_liab:
            nwc = [a - l for a, l in zip(curr_assets, curr_liab)]
            change_in_nwc = [0] + [nwc[i] - nwc[i-1] for i in range(1, len(nwc))]
        else:
            change_in_nwc = [0] * len(years)

        ie_is = grab_series(xlsx, "Income Statement", r"interest expense|finance costs")
        ie_cf = grab_series(xlsx, "Cash Flow", r"interest\s*paid")
        interest_expense = ie_is if ie_is is not None else (ie_cf or [0] * len(years))

        for i, (y,e,c,d,ca,v,t,nwc0,ie) in enumerate(zip(
            years, ebitda, capex, debt, cash, ev, taxes_cf,
            change_in_nwc, interest_expense
        )):
            rows.append({
                "Ticker": ticker,
                "Country": country,
                "Year": y,
                "EBITDA": e,
                "CapEx": c,
                "Debt": d,
                "Cash": ca,
                "EV": v,
                "CashTaxesPaid": t,
                "ChangeNWC": nwc0,
                "InterestExpense": ie,
                "tax_rate": tax_rate_series[i],
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["ΔDebt"] = df.groupby("Ticker")["Debt"].diff().fillna(0)
    df["ΔCash"] = df.groupby("Ticker")["Cash"].diff().fillna(0)

    df["FCFF"] = (
        df["EBITDA"]
      - df["CashTaxesPaid"]
      - df["ChangeNWC"]
      - df["CapEx"]
    )
    df["FCFE"] = (
        df["FCFF"]
      - df["InterestExpense"] * (1 - df["tax_rate"])
      + df["ΔDebt"]
      - df["ΔCash"]
    )
    df["FCF"] = (
        df["EBITDA"]
      - df["CashTaxesPaid"]
      - df["ChangeNWC"]
      - df["CapEx"]
    )
    df["EV/EBITDA"] = df["EV"] / df["EBITDA"].replace(0, pd.NA)

    return df

# Initialize database
@st.cache_resource
def setup_database():
    """Initialize database and populate with existing data"""
    init_database()
    
    # Check if we have data in the database
    existing_data = get_financial_data()
    if existing_data.empty:
        # Load data from Excel files and store in database
        excel_df = build_dataset()
        if not excel_df.empty:
            store_financial_data(excel_df)
            
            # Store company information
            for ticker in excel_df['Ticker'].unique():
                country = excel_df[excel_df['Ticker'] == ticker]['Country'].iloc[0]
                store_company_info(ticker, country)
            
            st.success(f"Initialized database with {len(excel_df)} financial records")
            return excel_df
        return pd.DataFrame()
    else:
        return existing_data

# Generate session ID for tracking simulations
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Main App
st.title("Companies")

# Setup database and load data
df = setup_database()

if df.empty:
    st.error("No data found. Please check your Excel files.")
    st.stop()

# Sidebar
with st.sidebar:
    st.header("🎯 Company Selection")
    
    # Company selector matching screenshot
    selected_ticker = st.selectbox(
        "Choose an option",
        options=["Choose an option"] + sorted(df["Ticker"].unique()),
        key="company_select"
    )
    
    if selected_ticker != "Choose an option":
        # Get country for selected ticker
        country = df[df["Ticker"] == selected_ticker]["Country"].iloc[0].lower()
        
        st.markdown("---")
        st.header("📊 Model Selection")
        
        # Model toggle
        model_choice = st.radio(
            "Beta Model:",
            ["CAPM", "FF5", "Both"],
            key="model_toggle"
        )
        
        st.markdown("---")
        st.header("⚙️ Simulations")
        
        # Year range for analysis
        available_years = sorted(df[df["Ticker"] == selected_ticker]["Year"].unique())
        year_range = st.slider(
            "Year Range",
            min_value=min(available_years),
            max_value=max(available_years),
            value=(min(available_years), max(available_years)),
            key="year_range"
        )
        
        # Simulation sliders matching screenshots
        st.subheader("Financial Metrics")
        
        ebitda_change = st.slider("EBITDA Δ%", -50, 50, 0, key="ebitda_sim")
        capex_change = st.slider("CapEx Δ%", -50, 50, 0, key="capex_sim")
        debt_change = st.slider("Debt Δ%", -50, 50, 0, key="debt_sim")
        cash_change = st.slider("Cash Δ%", -50, 50, 0, key="cash_sim")
        nwc_change = st.slider("NWC Δ%", -50, 50, 0, key="nwc_sim")
        
        # Unlevered multiple
        ev_ebitda_unlevered = st.slider(
            "EV/EBITDA (unlevered)",
            -50.0, 
            50.0, 
            0.0,
            step=0.1,
            key="ev_ebitda_unlev"
        )

# Main content
if selected_ticker != "Choose an option":
    ticker_data = df[df["Ticker"] == selected_ticker].copy()
    
    # Filter by year range
    ticker_data = ticker_data[
        (ticker_data["Year"] >= year_range[0]) & 
        (ticker_data["Year"] <= year_range[1])
    ].copy()
    
    if ticker_data.empty:
        st.error("No data available for selected year range")
        st.stop()
    
    # Get latest year data
    latest_year = ticker_data["Year"].max()
    latest_data = ticker_data[ticker_data["Year"] == latest_year].iloc[0]
    
    # Auto-download FF5 data if needed
    if model_choice in ["FF5", "Both"]:
        region_name = FF5_REGIONS.get(country)
        
        if region_name:
            with st.spinner(f"🔄 Fetching {region_name} factor data..."):
                try:
                    # Check if data exists, if not download
                    ff5_data = load_ff5_data(region_name)
                    if ff5_data is None:
                        # Download FF5 data automatically
                        download_and_extract_ff5_data()
                        ff5_data = load_ff5_data(region_name)
                    
                    if ff5_data is not None:
                        st.success(f"✅ Loaded {len(ff5_data)} months of factor data")
                        
                        # Get stock returns for beta calculation
                        try:
                            stock_returns = fetch_monthly_returns(
                                selected_ticker.replace('.O', ''), 
                                f"{year_range[0]}-01-01",
                                f"{year_range[1]}-12-31"
                            )
                            
                            # Calculate excess returns
                            rf_rate = fetch_risk_free_rate(
                                f"{year_range[0]}-01-01",
                                f"{year_range[1]}-12-31"
                            )
                            excess_returns = calculate_excess_returns(stock_returns, rf_rate)
                            
                            # Compute betas
                            if model_choice == "FF5":
                                betas = compute_ff5_betas(excess_returns, ff5_data)
                                if betas:
                                    wacc = calculate_wacc(betas['market_beta'])
                                    store_beta_analysis(selected_ticker, "FF5", betas, wacc)
                            elif model_choice == "CAPM":
                                betas = compute_capm_beta(excess_returns, ff5_data)
                                if betas:
                                    wacc = calculate_wacc(betas['market_beta'])
                                    store_beta_analysis(selected_ticker, "CAPM", betas, wacc)
                            else:  # Both
                                ff5_betas = compute_ff5_betas(excess_returns, ff5_data)
                                capm_betas = compute_capm_beta(excess_returns, ff5_data)
                                if ff5_betas:
                                    wacc_ff5 = calculate_wacc(ff5_betas['market_beta'])
                                    store_beta_analysis(selected_ticker, "FF5", ff5_betas, wacc_ff5)
                                if capm_betas:
                                    wacc_capm = calculate_wacc(capm_betas['market_beta'])
                                    store_beta_analysis(selected_ticker, "CAPM", capm_betas, wacc_capm)
                                betas = {"FF5": ff5_betas, "CAPM": capm_betas}
                            
                        except Exception as e:
                            st.warning(f"Could not fetch stock data: {e}")
                            betas = None
                            
                except Exception as e:
                    st.error(f"Error downloading factor data: {e}")
                    betas = None
        else:
            st.warning(f"No FF5 region mapping for country: {country}")
            betas = None
    else:
        betas = None
    
    # Historical Metrics Section
    st.markdown('<div class="section-header">Historical Metrics</div>', unsafe_allow_html=True)
    
    # Create metric cards matching screenshots
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">EBITDA</div>
            <div class="metric-value">$ {latest_data['EBITDA']:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">CapEx</div>
            <div class="metric-value">$ {latest_data['CapEx']:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">FCF</div>
            <div class="metric-value">$ {latest_data['FCF']:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">EV</div>
            <div class="metric-value">$ {latest_data['EV']:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        ev_ebitda_ratio = latest_data['EV'] / latest_data['EBITDA'] if latest_data['EBITDA'] != 0 else 0
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">EV/EBITDA</div>
            <div class="metric-value">{ev_ebitda_ratio:.1f}x</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Second row of metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Debt</div>
            <div class="metric-value">$ {latest_data['Debt']:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Cash</div>
            <div class="metric-value">$ {latest_data['Cash']:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">ΔNWC</div>
            <div class="metric-value">$ {latest_data['ChangeNWC']:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Interest</div>
            <div class="metric-value">$ {latest_data['InterestExpense']:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        tax_rate_pct = latest_data['tax_rate'] * 100
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Tax Rate</div>
            <div class="metric-value">{tax_rate_pct:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Apply simulations to create "Simulated Metrics"
    st.markdown('<div class="section-header">Simulated Metrics</div>', unsafe_allow_html=True)
    
    # Calculate simulated values
    sim_ebitda = latest_data['EBITDA'] * (1 + ebitda_change/100)
    sim_capex = latest_data['CapEx'] * (1 + capex_change/100)
    sim_debt = latest_data['Debt'] * (1 + debt_change/100)
    sim_cash = latest_data['Cash'] * (1 + cash_change/100)
    sim_nwc = latest_data['ChangeNWC'] * (1 + nwc_change/100)
    
    # Recalculate FCF and EV
    sim_fcf = sim_ebitda - latest_data['CashTaxesPaid'] - sim_nwc - sim_capex
    sim_ev = latest_data['EV'] * (1 + (ev_ebitda_unlevered/100))  # Adjust EV based on multiple change
    sim_ev_ebitda = sim_ev / sim_ebitda if sim_ebitda != 0 else 0
    
    # Store simulation in database
    simulation_params = {
        'ebitda_change': ebitda_change,
        'capex_change': capex_change,
        'debt_change': debt_change,
        'cash_change': cash_change,
        'nwc_change': nwc_change,
        'ev_ebitda_change': ev_ebitda_unlevered
    }
    
    simulation_results = {
        'simulated': {
            'ebitda': sim_ebitda,
            'capex': sim_capex,
            'debt': sim_debt,
            'cash': sim_cash,
            'fcf': sim_fcf,
            'ev': sim_ev,
            'ev_ebitda': sim_ev_ebitda
        },
        'original': {
            'ebitda': latest_data['EBITDA'],
            'capex': latest_data['CapEx'],
            'debt': latest_data['Debt'],
            'cash': latest_data['Cash'],
            'fcf': latest_data['FCF'],
            'ev': latest_data['EV'],
            'ev_ebitda': latest_data['EV/EBITDA']
        }
    }
    
    try:
        store_simulation(selected_ticker, st.session_state.session_id, simulation_params, simulation_results)
    except Exception as e:
        st.warning(f"Could not store simulation: {e}")
    
    # Simulated metrics cards
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        ebitda_pct_change = ((sim_ebitda / latest_data['EBITDA']) - 1) * 100
        change_color = "positive" if ebitda_pct_change >= 0 else "negative"
        change_symbol = "↑" if ebitda_pct_change >= 0 else "↓"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">EBITDA</div>
            <div class="metric-value">$ {sim_ebitda:,.0f}</div>
            <div class="metric-change {change_color}">{change_symbol} {abs(ebitda_pct_change):.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        capex_pct_change = ((sim_capex / latest_data['CapEx']) - 1) * 100
        change_color = "positive" if capex_pct_change >= 0 else "negative"
        change_symbol = "↑" if capex_pct_change >= 0 else "↓"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">CapEx</div>
            <div class="metric-value">$ {sim_capex:,.0f}</div>
            <div class="metric-change {change_color}">{change_symbol} {abs(capex_pct_change):.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        fcf_pct_change = ((sim_fcf / latest_data['FCF']) - 1) * 100 if latest_data['FCF'] != 0 else 0
        change_color = "positive" if fcf_pct_change >= 0 else "negative"
        change_symbol = "↑" if fcf_pct_change >= 0 else "↓"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">FCF</div>
            <div class="metric-value">$ {sim_fcf:,.0f}</div>
            <div class="metric-change {change_color}">{change_symbol} {abs(fcf_pct_change):.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        ev_pct_change = ((sim_ev / latest_data['EV']) - 1) * 100
        change_color = "positive" if ev_pct_change >= 0 else "negative"
        change_symbol = "↑" if ev_pct_change >= 0 else "↓"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">EV</div>
            <div class="metric-value">$ {sim_ev:,.0f}</div>
            <div class="metric-change {change_color}">{change_symbol} {abs(ev_pct_change):.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        ev_ebitda_pct_change = ((sim_ev_ebitda / ev_ebitda_ratio) - 1) * 100 if ev_ebitda_ratio != 0 else 0
        change_color = "positive" if ev_ebitda_pct_change >= 0 else "negative"
        change_symbol = "↑" if ev_ebitda_pct_change >= 0 else "↓"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">EV/EBITDA</div>
            <div class="metric-value">{sim_ev_ebitda:.1f}x</div>
            <div class="metric-change {change_color}">{change_symbol} {abs(ev_ebitda_pct_change):.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Second row simulated
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        debt_pct_change = ((sim_debt / latest_data['Debt']) - 1) * 100
        change_color = "positive" if debt_pct_change >= 0 else "negative"
        change_symbol = "↑" if debt_pct_change >= 0 else "↓"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Debt</div>
            <div class="metric-value">$ {sim_debt:,.0f}</div>
            <div class="metric-change {change_color}">{change_symbol} {abs(debt_pct_change):.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        cash_pct_change = ((sim_cash / latest_data['Cash']) - 1) * 100
        change_color = "positive" if cash_pct_change >= 0 else "negative"
        change_symbol = "↑" if cash_pct_change >= 0 else "↓"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Cash</div>
            <div class="metric-value">$ {sim_cash:,.0f}</div>
            <div class="metric-change {change_color}">{change_symbol} {abs(cash_pct_change):.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        nwc_pct_change = ((sim_nwc / latest_data['ChangeNWC']) - 1) * 100 if latest_data['ChangeNWC'] != 0 else 0
        change_color = "positive" if nwc_pct_change >= 0 else "negative"
        change_symbol = "↑" if nwc_pct_change >= 0 else "↓"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">ΔNWC</div>
            <div class="metric-value">$ {sim_nwc:,.0f}</div>
            <div class="metric-change {change_color}">{change_symbol} {abs(nwc_pct_change):.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Interest</div>
            <div class="metric-value">$ {latest_data['InterestExpense']:,.0f}</div>
            <div class="metric-change">↑ +0.0%</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Tax Rate</div>
            <div class="metric-value">{tax_rate_pct:.1f}%</div>
            <div class="metric-change">↑ +0.0%</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Beta Analysis Section
    if betas is not None and model_choice in ["FF5", "CAPM", "Both"]:
        st.markdown('<div class="section-header">Beta Analysis Results</div>', unsafe_allow_html=True)
        
        if model_choice == "Both" and isinstance(betas, dict):
            # Display both models
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("CAPM Model")
                if betas.get("CAPM"):
                    capm_data = betas["CAPM"]
                    st.markdown(f"""
                    <div class="beta-card">
                        <div class="beta-title">Market Beta</div>
                        <div class="beta-value">{capm_data['market_beta']:.3f}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"""
                    <div class="beta-card">
                        <div class="beta-title">Alpha</div>
                        <div class="beta-value">{capm_data['alpha']:.3f}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Calculate WACC using CAPM beta
                    wacc_capm = calculate_wacc(capm_data['market_beta'])
                    st.markdown(f"""
                    <div class="wacc-display">
                        <div class="wacc-title">WACC (CAPM)</div>
                        <div class="wacc-value">{wacc_capm*100:.2f}%</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            with col2:
                st.subheader("Fama/French 5-Factor")
                if betas.get("FF5"):
                    ff5_data = betas["FF5"]
                    
                    # Display all 5 factors
                    factor_names = [
                        ("Market Beta", "market_beta"),
                        ("SMB Beta", "smb_beta"), 
                        ("HML Beta", "hml_beta"),
                        ("RMW Beta", "rmw_beta"),
                        ("CMA Beta", "cma_beta")
                    ]
                    
                    for name, key in factor_names:
                        st.markdown(f"""
                        <div class="beta-card">
                            <div class="beta-title">{name}</div>
                            <div class="beta-value">{ff5_data[key]:.3f}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Calculate WACC using FF5 market beta
                    wacc_ff5 = calculate_wacc(ff5_data['market_beta'])
                    st.markdown(f"""
                    <div class="wacc-display">
                        <div class="wacc-title">WACC (FF5)</div>
                        <div class="wacc-value">{wacc_ff5*100:.2f}%</div>
                    </div>
                    """, unsafe_allow_html=True)
        
        elif model_choice == "FF5" and isinstance(betas, dict):
            # Display FF5 only
            st.subheader("Fama/French 5-Factor Model Results")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            factor_cols = [col1, col2, col3, col4, col5]
            factor_names = [
                ("Market Beta", "market_beta"),
                ("SMB Beta", "smb_beta"), 
                ("HML Beta", "hml_beta"),
                ("RMW Beta", "rmw_beta"),
                ("CMA Beta", "cma_beta")
            ]
            
            for i, (name, key) in enumerate(factor_names):
                with factor_cols[i]:
                    st.markdown(f"""
                    <div class="beta-card">
                        <div class="beta-title">{name}</div>
                        <div class="beta-value">{betas[key]:.3f}</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Industry Beta Comparison
            st.subheader("Industry Beta Benchmark")
            
            # Fetch Damodaran industry betas
            industry_betas_df = fetch_damodaran_industry_betas()
            
            if not industry_betas_df.empty:
                # Try to find matching industry beta
                company_info = ticker_data.iloc[0] if not ticker_data.empty else {}
                sector = company_info.get('Sector', '')
                industry = company_info.get('Industry', '')
                
                industry_match = find_industry_beta(industry_betas_df, sector, industry)
                
                if industry_match:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"""
                        <div class="beta-card">
                            <div class="beta-title">Company Beta</div>
                            <div class="beta-value">{betas['market_beta']:.3f}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown(f"""
                        <div class="beta-card">
                            <div class="beta-title">Industry Beta ({industry_match['industry']})</div>
                            <div class="beta-value">{industry_match['beta']:.3f}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # WACC calculations with both betas
                    wacc_results = calculate_wacc_with_industry_beta(
                        market_beta=betas['market_beta'],
                        industry_beta=industry_match['beta']
                    )
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"""
                        <div class="wacc-display">
                            <div class="wacc-title">Company WACC (FF5 Model)</div>
                            <div class="wacc-value">{wacc_results['company_wacc']['wacc']*100:.2f}%</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown(f"""
                        <div class="wacc-display">
                            <div class="wacc-title">Industry Benchmark WACC</div>
                            <div class="wacc-value">{wacc_results['industry_wacc']['wacc']*100:.2f}%</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Store beta analysis with WACC
                    store_beta_analysis(
                        ticker=selected_ticker,
                        model_type="FF5",
                        betas=betas,
                        wacc=wacc_results['company_wacc']['wacc']
                    )
                else:
                    # No industry match found, use company beta only
                    wacc = calculate_wacc(betas['market_beta'])
                    st.markdown(f"""
                    <div class="wacc-display">
                        <div class="wacc-title">Company WACC (FF5 Model)</div>
                        <div class="wacc-value">{wacc*100:.2f}%</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    store_beta_analysis(
                        ticker=selected_ticker,
                        model_type="FF5",
                        betas=betas,
                        wacc=wacc
                    )
            else:
                # Fallback to basic WACC calculation
                wacc = calculate_wacc(betas['market_beta'])
                st.markdown(f"""
                <div class="wacc-display">
                    <div class="wacc-title">Company WACC (FF5 Model)</div>
                    <div class="wacc-value">{wacc*100:.2f}%</div>
                </div>
                """, unsafe_allow_html=True)
                
                store_beta_analysis(
                    ticker=selected_ticker,
                    model_type="FF5",
                    betas=betas,
                    wacc=wacc
                )
        
        elif model_choice == "CAPM" and isinstance(betas, dict):
            # Display CAPM only
            st.subheader("CAPM Model Results")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"""
                <div class="beta-card">
                    <div class="beta-title">Market Beta</div>
                    <div class="beta-value">{betas['market_beta']:.3f}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="beta-card">
                    <div class="beta-title">Alpha</div>
                    <div class="beta-value">{betas['alpha']:.3f}</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Industry Beta Comparison for CAPM
            st.subheader("Industry Beta Benchmark")
            
            # Fetch Damodaran industry betas
            industry_betas_df = fetch_damodaran_industry_betas()
            
            if not industry_betas_df.empty:
                # Try to find matching industry beta
                company_info = ticker_data.iloc[0] if not ticker_data.empty else {}
                sector = company_info.get('Sector', '')
                industry = company_info.get('Industry', '')
                
                industry_match = find_industry_beta(industry_betas_df, sector, industry)
                
                if industry_match:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"""
                        <div class="beta-card">
                            <div class="beta-title">Company Beta</div>
                            <div class="beta-value">{betas['market_beta']:.3f}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown(f"""
                        <div class="beta-card">
                            <div class="beta-title">Industry Beta ({industry_match['industry']})</div>
                            <div class="beta-value">{industry_match['beta']:.3f}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # WACC calculations with both betas
                    wacc_results = calculate_wacc_with_industry_beta(
                        market_beta=betas['market_beta'],
                        industry_beta=industry_match['beta']
                    )
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"""
                        <div class="wacc-display">
                            <div class="wacc-title">Company WACC (CAPM Model)</div>
                            <div class="wacc-value">{wacc_results['company_wacc']['wacc']*100:.2f}%</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown(f"""
                        <div class="wacc-display">
                            <div class="wacc-title">Industry Benchmark WACC</div>
                            <div class="wacc-value">{wacc_results['industry_wacc']['wacc']*100:.2f}%</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Store beta analysis with WACC
                    store_beta_analysis(
                        ticker=selected_ticker,
                        model_type="CAPM",
                        betas=betas,
                        wacc=wacc_results['company_wacc']['wacc']
                    )
                else:
                    # No industry match found, use company beta only
                    wacc = calculate_wacc(betas['market_beta'])
                    st.markdown(f"""
                    <div class="wacc-display">
                        <div class="wacc-title">Company WACC (CAPM Model)</div>
                        <div class="wacc-value">{wacc*100:.2f}%</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    store_beta_analysis(
                        ticker=selected_ticker,
                        model_type="CAPM",
                        betas=betas,
                        wacc=wacc
                    )
            else:
                # Fallback to basic WACC calculation
                wacc = calculate_wacc(betas['market_beta'])
                st.markdown(f"""
                <div class="wacc-display">
                    <div class="wacc-title">Company WACC (CAPM Model)</div>
                    <div class="wacc-value">{wacc*100:.2f}%</div>
                </div>
                """, unsafe_allow_html=True)
                
                store_beta_analysis(
                    ticker=selected_ticker,
                    model_type="CAPM",
                    betas=betas,
                    wacc=wacc
                )
    
    # DCF Valuation Section
    st.markdown('<div class="section-header">💎 DCF Intrinsic Stock Price Valuation</div>', unsafe_allow_html=True)
    
    # Get the appropriate discount rates
    if model_choice == "FF5" and isinstance(betas, dict):
        company_wacc = wacc_results['company_wacc']['wacc'] if 'wacc_results' in locals() and wacc_results else calculate_wacc(betas['market_beta'])
        cost_of_equity = calculate_wacc(betas['market_beta']) + 0.02  # Add risk premium for equity
    elif model_choice == "CAPM" and isinstance(betas, dict):
        company_wacc = wacc if 'wacc' in locals() else calculate_wacc(betas['market_beta'])
        cost_of_equity = 0.03 + (betas['market_beta'] * 0.06)  # Risk-free + (beta * market premium)
    else:
        company_wacc = 0.10  # Default WACC
        cost_of_equity = 0.12  # Default cost of equity
    
    # User inputs for valuation parameters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        shares_outstanding = st.number_input(
            "Shares Outstanding (millions)",
            min_value=1.0,
            max_value=10000.0,
            value=100.0,
            step=1.0,
            help="Enter the number of shares outstanding in millions"
        )
    
    with col2:
        terminal_growth = st.slider(
            "Terminal Growth Rate",
            min_value=0.0,
            max_value=5.0,
            value=2.5,
            step=0.1,
            format="%.1f%%",
            help="Long-term growth rate for terminal value calculation"
        ) / 100
    
    with col3:
        projection_years = st.selectbox(
            "Projection Period",
            options=[3, 5, 7, 10],
            index=1,
            help="Number of years to project cash flows"
        )
    
    # Calculate DCF valuation
    if not ticker_data.empty:
        valuation_results = calculate_intrinsic_stock_price(
            ticker_data=ticker_data,
            wacc=company_wacc,
            cost_of_equity=cost_of_equity,
            shares_outstanding=shares_outstanding * 1_000_000  # Convert to actual shares
        )
        
        if valuation_results:
            # Display results in cards
            col1, col2 = st.columns(2)
            
            # FCFF Model Results
            if 'fcff_model' in valuation_results:
                with col1:
                    fcff = valuation_results['fcff_model']
                    st.markdown(f"""
                    <div class="valuation-card">
                        <div class="valuation-header">FCFF Model (Enterprise Value)</div>
                        <div class="valuation-metric">
                            <div class="metric-label">Enterprise Value</div>
                            <div class="metric-value">${fcff['enterprise_value']:,.0f}</div>
                        </div>
                        <div class="valuation-metric">
                            <div class="metric-label">Net Debt</div>
                            <div class="metric-value">${fcff['net_debt']:,.0f}</div>
                        </div>
                        <div class="valuation-metric">
                            <div class="metric-label">Equity Value</div>
                            <div class="metric-value">${fcff['equity_value']:,.0f}</div>
                        </div>
                        {f'<div class="valuation-metric"><div class="metric-label">Price per Share</div><div class="metric-value">${fcff["price_per_share"]:.2f}</div></div>' if 'price_per_share' in fcff else ''}
                    </div>
                    """, unsafe_allow_html=True)
            
            # FCFE Model Results
            if 'fcfe_model' in valuation_results:
                with col2:
                    fcfe = valuation_results['fcfe_model']
                    st.markdown(f"""
                    <div class="valuation-card">
                        <div class="valuation-header">FCFE Model (Direct Equity)</div>
                        <div class="valuation-metric">
                            <div class="metric-label">Equity Value</div>
                            <div class="metric-value">${fcfe['equity_value']:,.0f}</div>
                        </div>
                        {f'<div class="valuation-metric"><div class="metric-label">Price per Share</div><div class="metric-value">${fcfe["price_per_share"]:.2f}</div></div>' if 'price_per_share' in fcfe else ''}
                        <div class="valuation-metric">
                            <div class="metric-label">Discount Rate (Cost of Equity)</div>
                            <div class="metric-value">{cost_of_equity:.1%}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Cash Flow Analysis Chart
            st.subheader("📈 Historical & Projected Cash Flows")
            
            # Create cash flow projection chart
            fig_cf = go.Figure()
            
            # Historical FCFF
            if 'fcff_model' in valuation_results:
                fcff_details = valuation_results['fcff_model']['valuation_details']
                historical_fcff = ticker_data['FCFF'].dropna().tolist()
                historical_years = ticker_data[ticker_data['FCFF'].notna()]['Year'].tolist()
                
                fig_cf.add_trace(go.Scatter(
                    x=historical_years,
                    y=historical_fcff,
                    mode='lines+markers',
                    name='Historical FCFF',
                    line=dict(color='cyan', width=3),
                    marker=dict(size=8)
                ))
                
                # Projected FCFF
                projection_years_list = list(range(historical_years[-1] + 1, historical_years[-1] + 6))
                fig_cf.add_trace(go.Scatter(
                    x=projection_years_list,
                    y=fcff_details['projected_cash_flows'],
                    mode='lines+markers',
                    name='Projected FCFF',
                    line=dict(color='orange', width=3, dash='dash'),
                    marker=dict(size=8, symbol='diamond')
                ))
            
            # Historical FCFE
            if 'fcfe_model' in valuation_results:
                historical_fcfe = ticker_data['FCFE'].dropna().tolist()
                historical_years_fcfe = ticker_data[ticker_data['FCFE'].notna()]['Year'].tolist()
                
                fig_cf.add_trace(go.Scatter(
                    x=historical_years_fcfe,
                    y=historical_fcfe,
                    mode='lines+markers',
                    name='Historical FCFE',
                    line=dict(color='lightgreen', width=2),
                    marker=dict(size=6)
                ))
            
            fig_cf.update_layout(
                title="Cash Flow Analysis",
                xaxis_title="Year",
                yaxis_title="Cash Flow ($)",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white'),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            st.plotly_chart(fig_cf, use_container_width=True)
            
            # Valuation Summary Table
            st.subheader("📋 Valuation Summary")
            
            summary_data = []
            if 'fcff_model' in valuation_results and 'price_per_share' in valuation_results['fcff_model']:
                summary_data.append({
                    'Model': 'FCFF (Enterprise Value)',
                    'Intrinsic Price': f"${valuation_results['fcff_model']['price_per_share']:.2f}",
                    'Discount Rate': f"{company_wacc:.1%}",
                    'Growth Rate': f"{terminal_growth:.1%}"
                })
            
            if 'fcfe_model' in valuation_results and 'price_per_share' in valuation_results['fcfe_model']:
                summary_data.append({
                    'Model': 'FCFE (Direct Equity)',
                    'Intrinsic Price': f"${valuation_results['fcfe_model']['price_per_share']:.2f}",
                    'Discount Rate': f"{cost_of_equity:.1%}",
                    'Growth Rate': f"{terminal_growth:.1%}"
                })
            
            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                st.dataframe(summary_df, use_container_width=True, hide_index=True)
        else:
            st.warning("Insufficient cash flow data for DCF valuation. Need at least 2 years of FCFF or FCFE data.")
    
    # 3D Visualization matching screenshots
    st.markdown('<div class="section-header">📊 EV/EBITDA & FCF Over Time</div>', unsafe_allow_html=True)
    
    # Create 3D scatter plot
    fig = go.Figure(data=[go.Scatter3d(
        x=ticker_data['Year'],
        y=ticker_data['EV/EBITDA'].fillna(0),
        z=ticker_data['FCF'],
        mode='markers+lines',
        marker=dict(
            size=8,
            color=ticker_data['FCF'],
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(title="FCF")
        ),
        line=dict(
            color='cyan',
            width=3
        ),
        text=[f"Year: {year}<br>EV/EBITDA: {ev_ebitda:.1f}x<br>FCF: ${fcf:,.0f}" 
              for year, ev_ebitda, fcf in zip(ticker_data['Year'], 
                                            ticker_data['EV/EBITDA'].fillna(0),
                                            ticker_data['FCF'])],
        hovertemplate='%{text}<extra></extra>'
    )])
    
    # Add simulated point as a diamond
    fig.add_trace(go.Scatter3d(
        x=[latest_year],
        y=[sim_ev_ebitda],
        z=[sim_fcf],
        mode='markers',
        marker=dict(
            size=15,
            color='red',
            symbol='diamond',
            line=dict(
                color='white',
                width=2
            )
        ),
        name='Simulated',
        text=f"Simulated<br>EV/EBITDA: {sim_ev_ebitda:.1f}x<br>FCF: ${sim_fcf:,.0f}",
        hovertemplate='%{text}<extra></extra>'
    ))
    
    fig.update_layout(
        scene=dict(
            xaxis_title='Year',
            yaxis_title='EV/EBITDA',
            zaxis_title='FCF',
            bgcolor='rgba(0,0,0,0)',
            xaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)"),
            yaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)"),
            zaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)")
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        height=600
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Time series chart
    fig2 = go.Figure()
    
    fig2.add_trace(go.Scatter(
        x=ticker_data['Year'],
        y=ticker_data['FCF'],
        mode='lines+markers',
        name='FCF (USD)',
        line=dict(color='#00ffff', width=3),
        marker=dict(size=8)
    ))
    
    fig2.add_trace(go.Scatter(
        x=ticker_data['Year'],
        y=ticker_data['EBITDA'],
        mode='lines+markers',
        name='EBITDA (USD)',
        line=dict(color='#39ff14', width=3),
        marker=dict(size=8)
    ))
    
    fig2.update_layout(
        xaxis_title='Year',
        yaxis_title='FCF (USD) / EBITDA (USD)',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        xaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.1)"),
        height=400
    )
    
    st.plotly_chart(fig2, use_container_width=True)
    
    # Data Table matching screenshots
    st.markdown('<div class="section-header">📋 Data Table</div>', unsafe_allow_html=True)
    
    # Display data table with selected columns
    display_cols = ['Ticker', 'Year', 'EBITDA', 'CapEx', 'FCF', 'FCFF', 'FCFE', 
                   'ChangeNWC', 'InterestExpense', 'EV', 'EV/EBITDA', 'Debt', 'Cash']
    
    display_data = ticker_data[display_cols].copy()
    
    # Format numbers for display
    for col in ['EBITDA', 'CapEx', 'FCF', 'FCFF', 'FCFE', 'ChangeNWC', 'InterestExpense', 'EV', 'Debt', 'Cash']:
        if col in display_data.columns:
            display_data[col] = display_data[col].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "")
    
    if 'EV/EBITDA' in display_data.columns:
        display_data['EV/EBITDA'] = display_data['EV/EBITDA'].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "")
    
    st.dataframe(
        display_data,
        use_container_width=True,
        height=300
    )
    
    # Database Dashboard Section
    st.markdown('<div class="section-header">📊 Analysis History Dashboard</div>', unsafe_allow_html=True)
    
    # Historical Beta Analyses
    with st.expander("🧮 Historical Beta Analyses", expanded=False):
        try:
            ff5_analysis = get_latest_beta_analysis(selected_ticker, "FF5")
            capm_analysis = get_latest_beta_analysis(selected_ticker, "CAPM")
            
            if ff5_analysis or capm_analysis:
                col1, col2 = st.columns(2)
                
                with col1:
                    if ff5_analysis:
                        st.markdown("**Latest FF5 Analysis**")
                        st.json({
                            "Date": ff5_analysis['analysis_date'].strftime("%Y-%m-%d %H:%M"),
                            "Alpha": f"{ff5_analysis['alpha']:.4f}",
                            "Market Beta": f"{ff5_analysis['market_beta']:.4f}",
                            "SMB Beta": f"{ff5_analysis['smb_beta']:.4f}" if ff5_analysis['smb_beta'] else "N/A",
                            "HML Beta": f"{ff5_analysis['hml_beta']:.4f}" if ff5_analysis['hml_beta'] else "N/A",
                            "RMW Beta": f"{ff5_analysis['rmw_beta']:.4f}" if ff5_analysis['rmw_beta'] else "N/A",
                            "CMA Beta": f"{ff5_analysis['cma_beta']:.4f}" if ff5_analysis['cma_beta'] else "N/A",
                            "R-Squared": f"{ff5_analysis['r_squared']:.4f}" if ff5_analysis['r_squared'] else "N/A",
                            "WACC": f"{ff5_analysis['wacc']:.2%}" if ff5_analysis['wacc'] else "N/A"
                        })
                    else:
                        st.info("No FF5 analysis found")
                
                with col2:
                    if capm_analysis:
                        st.markdown("**Latest CAPM Analysis**")
                        st.json({
                            "Date": capm_analysis['analysis_date'].strftime("%Y-%m-%d %H:%M"),
                            "Alpha": f"{capm_analysis['alpha']:.4f}",
                            "Market Beta": f"{capm_analysis['market_beta']:.4f}",
                            "R-Squared": f"{capm_analysis['r_squared']:.4f}" if capm_analysis['r_squared'] else "N/A",
                            "WACC": f"{capm_analysis['wacc']:.2%}" if capm_analysis['wacc'] else "N/A"
                        })
                    else:
                        st.info("No CAPM analysis found")
            else:
                st.info("No beta analyses found for this ticker")
        except Exception as e:
            st.warning(f"Could not load beta analysis history: {e}")
    
    # Simulation History
    with st.expander("🎯 Recent Simulations", expanded=False):
        try:
            sim_history = get_simulation_history(selected_ticker, limit=5)
            
            if sim_history:
                for i, sim in enumerate(sim_history):
                    with st.container():
                        st.markdown(f"**Simulation {i+1}** - {sim['date'].strftime('%Y-%m-%d %H:%M')}")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Parameters:**")
                            st.json({
                                "EBITDA Change": f"{sim['parameters']['ebitda_change']:.1f}%",
                                "CapEx Change": f"{sim['parameters']['capex_change']:.1f}%",
                                "Debt Change": f"{sim['parameters']['debt_change']:.1f}%",
                                "Cash Change": f"{sim['parameters']['cash_change']:.1f}%",
                                "NWC Change": f"{sim['parameters']['nwc_change']:.1f}%",
                                "EV/EBITDA Change": f"{sim['parameters']['ev_ebitda_change']:.1f}%"
                            })
                        
                        with col2:
                            if sim['simulated_metrics'] and sim['original_metrics']:
                                st.markdown("**Impact:**")
                                simulated = sim['simulated_metrics']
                                original = sim['original_metrics']
                                
                                fcf_change = ((simulated['fcf'] / original['fcf']) - 1) * 100 if original['fcf'] != 0 else 0
                                ev_change = ((simulated['ev'] / original['ev']) - 1) * 100 if original['ev'] != 0 else 0
                                
                                st.json({
                                    "FCF Change": f"{fcf_change:.1f}%",
                                    "EV Change": f"{ev_change:.1f}%",
                                    "New EV/EBITDA": f"{simulated['ev_ebitda']:.2f}x"
                                })
                        
                        st.divider()
            else:
                st.info("No simulation history found for this ticker")
        except Exception as e:
            st.warning(f"Could not load simulation history: {e}")
    
    # Database Statistics
    with st.expander("📈 Database Statistics", expanded=False):
        try:
            companies = get_companies()
            total_companies = len(companies)
            
            # Count records by country
            countries = {}
            for comp in companies:
                country = comp['country']
                countries[country] = countries.get(country, 0) + 1
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Companies", total_companies)
                st.markdown("**Companies by Country:**")
                for country, count in countries.items():
                    st.write(f"• {country}: {count}")
            
            with col2:
                # Get total financial records
                all_financial_data = get_financial_data()
                st.metric("Financial Records", len(all_financial_data))
                
                if not all_financial_data.empty:
                    years = all_financial_data['Year'].unique()
                    st.write(f"**Year Range:** {min(years)} - {max(years)}")
                
        except Exception as e:
            st.warning(f"Could not load database statistics: {e}")

else:
    st.info("👆 Please select a company from the sidebar to begin analysis")
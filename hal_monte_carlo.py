"""
HAL (Hindustan Aeronautics) - Monte Carlo DCF
20,000 simulations over the DCF's key drivers. Self-contained; mirrors the Excel model (HAL_Model.xlsx).
Run:  python hal_monte_carlo.py
Outputs: hal_mc_results.json, hal_mc_chart.png
"""
import json
import numpy as np

# ---- Inputs (same as Excel 'Assumptions' sheet) ----
CMP, SHARES = 4655.60, 66.88
DEPOSITS, INVEST, DEBT = 42425.0, 1914.0, 66.0
RF, BETA, ERP = 0.070, 0.95, 0.050
KE = RF + BETA * ERP
YEARFRAC = 193 / 365
BASE_REV = 33089.0
GROWTH = np.array([0.11, 0.13, 0.13, 0.11, 0.10, 0.09, 0.08, 0.07, 0.065, 0.06])
MARGIN = np.array([0.295] + [0.30] * 9)
CAPEX = np.array([0.075, 0.075, 0.07, 0.065, 0.06] + [0.055] * 5)
DA, TAX, NWC, G0, CASH_CREDIT = 0.042, 0.25, 0.10, 0.05, 0.50

def dcf_vec(gshift, mshift, cscale, nwc, wacc, g, cc):
    n = len(wacc)
    gr = np.tile(GROWTH, (n, 1)); gr[:, :5] += gshift[:, None]
    mg = MARGIN[None, :] + mshift[:, None]
    cx = CAPEX[None, :] * cscale[:, None]
    rev = BASE_REV * np.cumprod(1 + gr, axis=1)
    prev = np.concatenate([np.full((n, 1), BASE_REV), rev[:, :-1]], axis=1)
    ebitda = rev * mg; d = rev * DA
    nopat = (ebitda - d) * (1 - TAX)
    fcff = nopat + d - rev * cx - (rev - prev) * nwc[:, None]
    t = np.arange(10) + 0.5
    df = 1 / (1 + wacc[:, None]) ** t[None, :]
    pv = (fcff * df).sum(axis=1)
    tv = fcff[:, -1] * (1 + g) / (wacc - g)
    pvtv = tv / (1 + wacc) ** t[-1]
    eq = pv + pvtv + cc * (DEPOSITS + INVEST) - DEBT
    return eq / SHARES * (1 + wacc) ** YEARFRAC

def run(n=20000, seed=42):
    rng = np.random.default_rng(seed)
    gshift = rng.normal(0, 0.025, n)
    mshift = rng.normal(0, 0.018, n)
    cscale = rng.lognormal(0, 0.12, n)
    nwc = rng.uniform(0.0, 0.20, n)
    wacc = np.clip(rng.normal(KE, 0.008, n), 0.08, 0.15)
    g = np.clip(rng.normal(G0, 0.005, n), 0.035, 0.065)
    g = np.minimum(g, wacc - 0.035)
    cc = rng.uniform(0, 1, n)
    v = dcf_vec(gshift, mshift, cscale, nwc, wacc, g, cc)
    drivers = {"WACC": wacc, "Terminal growth (g)": g, "Revenue growth shift (FY27-31)": gshift,
               "EBITDA margin shift": mshift, "Capex scale": cscale, "NWC % of incr. revenue": nwc,
               "Cash credit %": cc}
    corr = {k: float(np.corrcoef(x, v)[0, 1]) for k, x in drivers.items()}
    return v, corr

if __name__ == "__main__":
    base = dcf_vec(*(np.array([x]) for x in (0.0, 0.0, 1.0, NWC, KE, G0, CASH_CREDIT)))[0]
    v, corr = run()
    pct = {p: float(np.percentile(v, p)) for p in (5, 10, 25, 50, 75, 90, 95)}
    out = {"base_case_dcf": float(base), "median": pct[50], "mean": float(v.mean()),
           "prob_above_cmp": float((v > CMP).mean()), "prob_above_half_cmp": float((v > 0.5 * CMP).mean()),
           "percentiles": pct, "correlations": corr, "cmp": CMP, "n": len(v)}
    json.dump(out, open("hal_mc_results.json", "w"), indent=2)
    np.save("hal_mc_values.npy", v)
    print(json.dumps(out, indent=2))
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(11, 4))
        ax[0].hist(v, bins=120, color="#1F2A44")
        ax[0].axvline(CMP, color="#A52A2A", ls="--", label=f"CMP = Rs{CMP:,.0f}")
        ax[0].axvline(pct[50], color="#B8860B", label=f"Median = Rs{pct[50]:,.0f}")
        ax[0].set_title("Distribution of intrinsic value / share"); ax[0].set_xlabel("Rs per share"); ax[0].legend()
        ks = sorted(corr, key=lambda k: abs(corr[k]))
        ax[1].barh(ks, [corr[k] for k in ks], color=["#1E6B3C" if corr[k] > 0 else "#A52A2A" for k in ks])
        ax[1].set_title("Driver sensitivity (correlation to value/share)")
        plt.tight_layout(); plt.savefig("hal_mc_chart.png", dpi=160)
    except Exception as e:
        print("chart skipped:", e)

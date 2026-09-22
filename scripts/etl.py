"""
1단계 ETL: Quality Audit 원본(연도별) → 정제된 AWB 단위 분석 테이블

입력 (config.YEARS)
  - data/raw/quality_audit_{year}.xlsx  (헤더 행 'AWB Number' 자동 탐지, 마지막 합계행 제외)
  - data/raw/aircraft_daily_{year}.xlsx (일자별 기종현황 → 기종·노선권역 정보만 사용)
  - data/raw/user_analysis_2025.xlsx    ('환율' 시트: 2025 월별 평균 환율)

출력
  - data/processed/awb_clean.pkl / .csv : 전 연도 통합 정제 테이블 (year 컬럼)
  - data/processed/fx_monthly.csv       : 연도·월별 환율 테이블
  - data/processed/etl_report.json      : 연도별 정제 로그
"""
import json
import warnings

import openpyxl
import pandas as pd

from config import (FX_2026_OVERRIDE, PROCESSED, REVENUE_COL, USER_ANALYSIS_FILE, WEIGHT_COL, YEARS,
                    agent_group, region_of)
from customers import lookup as customer_lookup

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------- 로드
def find_header_row(path) -> int:
    """'AWB Number'가 있는 행(0-based)을 탐지."""
    ws = openpyxl.load_workbook(path, read_only=True).worksheets[0]
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=60, values_only=True)):
        if "AWB Number" in [v for v in row if v is not None]:
            return i
    raise ValueError(f"header row not found: {path}")


def load_quality_audit(year: int) -> pd.DataFrame:
    cache = PROCESSED / f"qa_raw_{year}.pkl"
    if year == 2025 and (PROCESSED / "qa_raw.pkl").exists() and not cache.exists():
        cache = PROCESSED / "qa_raw.pkl"
    if cache.exists():
        return pd.read_pickle(cache)
    path = YEARS[year]["qa"]
    df = pd.read_excel(path, header=find_header_row(path))
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]
    df.to_pickle(PROCESSED / f"qa_raw_{year}.pkl")
    return df


def load_fx() -> pd.DataFrame:
    """연도·통화·월별 환율 long 테이블. 2025: 사용자 '환율' 시트. 2026: OVERRIDE 또는 2025-12 환율 fallback."""
    raw = pd.read_excel(USER_ANALYSIS_FILE, sheet_name="환율", header=None)
    hdr_idx = raw.index[raw.iloc[:, 1].astype(str).str.strip() == "통화"][0]
    tbl = raw.iloc[hdr_idx + 1:, 1:14].copy()
    tbl.columns = ["currency"] + list(range(1, 13))
    tbl = tbl.dropna(subset=["currency"])
    tbl = tbl[tbl["currency"].astype(str).str.len() == 3]
    fx25 = tbl.melt(id_vars="currency", var_name="month", value_name="rate")
    fx25["year"] = 2025
    fx25["month"] = fx25["month"].astype(int)
    fx25["rate"] = fx25["rate"].astype(float)
    fx25["source"] = "2025 월평균(ECB 교차)"

    dec = fx25[fx25["month"] == 12].set_index("currency")["rate"]
    rows = []
    for cur in dec.index:
        for m in YEARS[2026]["months"]:
            if cur in FX_2026_OVERRIDE and len(FX_2026_OVERRIDE[cur]) >= m:
                rows.append(dict(currency=cur, month=m, rate=float(FX_2026_OVERRIDE[cur][m - 1]), year=2026, source="2026 확정 월평균"))
            else:
                rows.append(dict(currency=cur, month=m, rate=float(dec[cur]), year=2026, source="2025-12 환율 잠정 적용"))
    return pd.concat([fx25, pd.DataFrame(rows)], ignore_index=True)[["year", "currency", "month", "rate", "source"]]


def load_aircraft(year: int) -> pd.DataFrame:
    """일자별 기종현황 → (date, fno) 별 기종/노선/권역. 화물 실적 컬럼은 사용하지 않음."""
    ac = pd.read_excel(YEARS[year]["aircraft"])
    ac = ac[ac["bound"].isin(["Outbound", "Inbound"])].copy()
    ac["date"] = pd.to_datetime(ac["출발일"], errors="coerce").dt.normalize()
    ac = ac[ac["date"].notna()]
    ac["fno"] = ac["flightno"].astype(str).str.extract(r"(\d+)")[0].str.lstrip("0")
    ac = ac.rename(columns={"A/C(소)": "aircraft", "노선": "ac_route", "Line": "ac_line"})
    ac = ac[ac["aircraft"].notna() & (ac["aircraft"] != "-")]
    return ac.drop_duplicates(["date", "fno"])[["date", "fno", "aircraft", "ac_route", "ac_line", "bound"]]


# ---------------------------------------------------------------- 정제
def clean(df: pd.DataFrame, fx: pd.DataFrame, ac: pd.DataFrame, year: int) -> tuple[pd.DataFrame, dict]:
    rep = {"year": year, "rows_raw": int(len(df))}

    df = df[df["AWB Number"].notna()].copy()
    rep["rows_after_total_row_drop"] = int(len(df))

    dup_mask = df.duplicated(subset=["AWB Number", "First Flight Date", "Origin", "Destination", REVENUE_COL], keep="first")
    rep["duplicate_awb_rows_dropped"] = int(dup_mask.sum())
    df = df[~dup_mask].copy()

    df["First Flight Date"] = pd.to_datetime(df["First Flight Date"])
    df["AWB Execution Date"] = pd.to_datetime(df["AWB Execution Date"])
    df = df[df["First Flight Date"].dt.year == year].copy()
    rep["rows_in_year"] = int(len(df))
    df["year"] = year
    df["month"] = df["First Flight Date"].dt.month
    df["ym"] = df["First Flight Date"].dt.strftime("%Y-%m")
    df["quarter"] = "Q" + df["First Flight Date"].dt.quarter.astype(str)
    df["weekday"] = df["First Flight Date"].dt.day_name().str[:3]

    fxy = fx[fx["year"] == year][["currency", "month", "rate", "source"]].rename(columns={"currency": "AWB Currency", "source": "fx_source"})
    df = df.merge(fxy, on=["AWB Currency", "month"], how="left")
    rep["rows_missing_fx"] = int(df["rate"].isna().sum())
    df["rate"] = df["rate"].fillna(1.0)
    df["rev_krw"] = df[REVENUE_COL].fillna(0) * df["rate"]
    df["net_rev_krw"] = df["Net Revenue"].fillna(0) * df["rate"]
    df["iata_charge_krw"] = df["Audited IATA Charge"].fillna(0) * df["rate"]
    df["market_charge_krw"] = df["Audited Market Charge"].fillna(0) * df["rate"]

    df["cw_kg"] = df[WEIGHT_COL].fillna(0)
    df["gw_kg"] = df["Gross Weight"].fillna(0)
    df["vol_kg"] = df["Volume Weight"].fillna(0)
    df["yield_krw_per_kg"] = (df["rev_krw"] / df["cw_kg"]).where(df["cw_kg"] > 0)
    df["density_flag"] = pd.cut(
        (df["vol_kg"] / df["gw_kg"]).where(df["gw_kg"] > 0),
        bins=[0, 0.8, 1.2, 100], labels=["고밀도(중량)", "표준", "저밀도(용적)"],
    ).astype(str).replace("nan", "미확인")

    df["route"] = df["Origin"] + "→" + df["Destination"]
    df["origin_region"] = df["Origin"].map(region_of)
    df["dest_region"] = df["Destination"].map(region_of)
    df["direction"] = df["Origin"].apply(lambda o: "Outbound(한국출발)" if region_of(o) == "한국" else "Inbound(해외출발)")
    df["market_region"] = df.apply(lambda r: r["dest_region"] if r["direction"].startswith("Outbound") else r["origin_region"], axis=1)
    rep["unmapped_airports"] = sorted({c for c in pd.concat([df["Origin"], df["Destination"]]).unique() if region_of(c) == "기타"})

    df["agent_group"] = df["Bill-To Party Name"].map(agent_group)
    cust = df["Bill-To Party Name"].map(customer_lookup).apply(pd.Series)
    df[["customer_no", "customer_name", "customer_type", "customer_mapped"]] = cust[["customer_no", "customer_name", "customer_type", "mapped"]].values
    rep["customer_master_rev_share"] = round(float(df.loc[df["customer_mapped"] == True, "rev_krw"].sum() / df["rev_krw"].sum()), 4)
    rep["unmapped_bill_to"] = df.loc[df["customer_mapped"] == False].groupby("Bill-To Party Name")["rev_krw"].sum().round().sort_values(ascending=False).to_dict()

    df["shc_list"] = df["SHC"].fillna("").apply(lambda s: [c.strip() for c in s.split(",") if c.strip()])
    df["shc_primary"] = df["shc_list"].apply(lambda l: next((c for c in l if c != "GEN"), "GEN" if l else "NONE"))

    df["is_spot"] = df["Spot Rate Status"].eq("Approved")
    df["has_discrepancy"] = df["Discrepancy - Manually Resolved"].notna() | df["Discrepancy - Auto Resolved"].notna()
    df["billing_status"] = df["Outbound Billing Status"].fillna("미청구/미분류")
    df["audit_status"] = df["AWB Quality Audit Status"]
    df["is_voided"] = df["audit_status"].eq("Voided")
    df["is_zero_rev"] = df["rev_krw"] <= 0
    rep["voided_rows"] = int(df["is_voided"].sum())
    rep["zero_or_negative_revenue_rows"] = int(df["is_zero_rev"].sum())

    df["fno"] = df["First Flight Number"].astype(str).str.extract(r"(\d+)")[0].str.lstrip("0")
    df["carrier"] = df["First Flight Number"].astype(str).str.extract(r"^([A-Z]{2})")[0].fillna("TW")
    df["date"] = df["First Flight Date"].dt.normalize()
    df = df.merge(ac, on=["date", "fno"], how="left")
    df["aircraft"] = df["aircraft"].fillna("미확인")
    df["aircraft_family"] = df["aircraft"].map(
        lambda a: "A330(광동체)" if a.startswith("A330") else
                  "B777(광동체)" if a.startswith("B777") else
                  "B737(협동체)" if a.startswith("B737") else "미확인")
    rep["aircraft_join_rate"] = round(float((df["aircraft"] != "미확인").mean()), 4)
    rep["aircraft_unmatched_flights"] = df.loc[df["aircraft"] == "미확인", "First Flight Number"].value_counts().head(10).to_dict()

    rep["rows_final"] = int(len(df))
    rep["total_rev_krw"] = round(float(df["rev_krw"].sum()))
    rep["total_cw_kg"] = float(df["cw_kg"].sum())
    rep["months"] = sorted(df["month"].unique().tolist())
    return df, rep


KEEP_COLS = [
    "AWB Number", "First Flight Date", "AWB Execution Date", "year", "month", "ym", "quarter", "weekday",
    "First Flight Number", "carrier", "fno", "aircraft", "aircraft_family", "ac_line",
    "Origin", "Destination", "route", "origin_region", "dest_region", "direction", "market_region",
    "Bill-To Party Name", "agent_group", "customer_no", "customer_name", "customer_type", "customer_mapped", "Agent Name", "Outbound Customer", "Payment Type",
    "AWB Currency", "rate", "fx_source", REVENUE_COL, "rev_krw", "Net Revenue", "net_rev_krw", "Discount",
    "Audited IATA Charge", "iata_charge_krw", "Audited Market Charge", "market_charge_krw",
    "Audited IATA Rate", "Audited Market Rate",
    "Pieces", "gw_kg", "vol_kg", "cw_kg", "Volume", "yield_krw_per_kg", "density_flag",
    "SHC", "shc_list", "shc_primary", "Commodity", "Product",
    "Spot Rate Status", "is_spot", "Spot Rate ID", "has_discrepancy", "Discrepancy - Manually Resolved",
    "audit_status", "billing_status", "is_voided", "is_zero_rev",
]


def main():
    PROCESSED.mkdir(parents=True, exist_ok=True)
    fx = load_fx()
    frames, reports = [], {}
    for year in YEARS:
        if not YEARS[year]["qa"].exists():
            print(f"skip {year}: file not found")
            continue
        print(f"[{year}] loading...")
        df, ac = load_quality_audit(year), load_aircraft(year)
        print(f"[{year}] cleaning...")
        clean_df, rep = clean(df, fx, ac, year)
        frames.append(clean_df[KEEP_COLS])
        reports[str(year)] = rep
    out = pd.concat(frames, ignore_index=True)
    out.to_pickle(PROCESSED / "awb_clean.pkl")
    out.assign(shc_list=out["shc_list"].apply(",".join)).to_csv(PROCESSED / "awb_clean.csv", index=False, encoding="utf-8-sig")
    fx.to_csv(PROCESSED / "fx_monthly.csv", index=False)
    (PROCESSED / "etl_report.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2))
    for y, r in reports.items():
        print(f"== {y}: rows {r['rows_final']:,} | rev {r['total_rev_krw']/1e8:,.1f}억 | cw {r['total_cw_kg']/1000:,.0f}t | "
              f"aircraft join {r['aircraft_join_rate']:.1%} | customer master {r['customer_master_rev_share']:.1%} | unmapped airports {r['unmapped_airports']}")


if __name__ == "__main__":
    main()

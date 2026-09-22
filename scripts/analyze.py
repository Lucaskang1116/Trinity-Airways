"""
2단계 분석: 정제 테이블(awb_clean.pkl) → KPI 집계 JSON(대시보드용) + Excel 리포트

출력
  - public/data/dashboard.json : 대시보드에서 로드하는 모든 집계
  - output/cargo_revenue_2025_analysis.xlsx : 시트별 집계 리포트
"""
import json
from collections import Counter

import pandas as pd

from config import BASE_YEAR, CURRENT_YEAR, FX_2026_FALLBACK_NOTE, PROCESSED, PUBLIC_DATA, ROOT, SHC_MEANING, YEARS

OUTPUT = ROOT / "output"
MONTHS = list(range(1, 13))


def r0(x):  # 정수 반올림
    return int(round(float(x))) if pd.notna(x) else 0


def r2(x):
    return round(float(x), 2) if pd.notna(x) else None


def agg_block(g: pd.DataFrame) -> dict:
    rev, cw = g["rev_krw"].sum(), g["cw_kg"].sum()
    return {
        "awb": int(len(g)),
        "rev": r0(rev),
        "cw": r0(cw),
        "rev_per_awb": r0(rev / len(g)) if len(g) else 0,
        "yield": r2(rev / cw) if cw else None,
    }


def group_table(df, by, top=None, total_rev=None, extra=None):
    total_rev = total_rev or df["rev_krw"].sum()
    rows = []
    for key, g in df.groupby(by, dropna=False):
        row = {"key": key if isinstance(key, str) else str(key)} if not isinstance(by, list) else dict(zip(by, key))
        row.update(agg_block(g))
        row["share"] = round(row["rev"] / total_rev, 4) if total_rev else 0
        if extra:
            row.update(extra(g))
        rows.append(row)
    rows.sort(key=lambda r: -r["rev"])
    return rows[:top] if top else rows


def monthly_series(df, by, keys):
    """by 컬럼의 keys 각각에 대한 월별 매출/무게 시리즈."""
    out = {}
    for k in keys:
        g = df[df[by] == k]
        m = g.groupby("month").agg(rev=("rev_krw", "sum"), cw=("cw_kg", "sum"), awb=("AWB Number", "count"))
        m = m.reindex(MONTHS, fill_value=0)
        out[k] = {"rev": [r0(v) for v in m["rev"]], "cw": [r0(v) for v in m["cw"]], "awb": [int(v) for v in m["awb"]]}
    return out


def build(df_all: pd.DataFrame, year: int) -> dict:
    """연도별 전체 KPI 집계 dict 생성."""
    global MONTHS
    MONTHS = YEARS[year]["months"]
    df = df_all[(df_all["year"] == year) & (~df_all["is_voided"])].copy()
    total_rev = df["rev_krw"].sum()
    total_cw = df["cw_kg"].sum()

    # ---------- 1. 요약 KPI
    monthly = df.groupby("month").agg(awb=("AWB Number", "count"), rev=("rev_krw", "sum"), cw=("cw_kg", "sum"),
                                      gw=("gw_kg", "sum"), pieces=("Pieces", "sum")).reindex(MONTHS, fill_value=0)
    monthly["yield"] = monthly["rev"] / monthly["cw"]
    monthly["rev_per_awb"] = monthly["rev"] / monthly["awb"]
    monthly["mom"] = monthly["rev"].pct_change()
    monthly["share"] = monthly["rev"] / total_rev
    monthly["cum_rev"] = monthly["rev"].cumsum()
    h1, h2 = monthly.loc[1:6, "rev"].sum(), monthly.loc[7:12, "rev"].sum() if len(MONTHS) > 6 else 0
    best_m = int(monthly["rev"].idxmax())
    agent_rank = group_table(df, "agent_group")
    top5_share = sum(r["share"] for r in agent_rank[:5])

    summary = {
        "station": "ICN", "year": year, "period": f"{year}-01-01 ~ {year}-{MONTHS[-1]:02d}-{pd.Timestamp(year, MONTHS[-1], 1).days_in_month}",
        "months_available": len(MONTHS), "is_partial_year": len(MONTHS) < 12,
        "total_rev": r0(total_rev), "total_cw": r0(total_cw), "total_awb": int(len(df)),
        "total_gw": r0(df["gw_kg"].sum()), "total_pieces": r0(df["Pieces"].sum()),
        "rev_per_awb": r0(total_rev / len(df)), "yield": r2(total_rev / total_cw),
        "best_month": best_m, "best_month_rev": r0(monthly.loc[best_m, "rev"]),
        "h1_rev": r0(h1), "h2_rev": r0(h2), "h2_vs_h1": round(h2 / h1 - 1, 4) if h2 else None,
        "dec_vs_jan": round(monthly.loc[MONTHS[-1], "rev"] / monthly.loc[1, "rev"] - 1, 4), "last_month": MONTHS[-1],
        "top5_agent_share": round(top5_share, 4), "top1_agent": agent_rank[0]["key"], "top1_agent_share": agent_rank[0]["share"],
        "outbound_share": round(df.loc[df["direction"].str.startswith("Outbound"), "rev_krw"].sum() / total_rev, 4),
        "krw_share": round(df.loc[df["AWB Currency"] == "KRW", "rev_krw"].sum() / total_rev, 4),
        "spot_share": round(df.loc[df["is_spot"], "rev_krw"].sum() / total_rev, 4),
        "zero_rev_awb": int(df["is_zero_rev"].sum()),
        "route_count": int(df["route"].nunique()), "dest_count": int(df["Destination"].nunique()),
        "agent_count": int(df["Bill-To Party Name"].nunique()), "agent_group_count": int(df["agent_group"].nunique()),
    }

    # ---------- 2. 월별
    monthly_rows = [{"month": int(m), "awb": int(r.awb), "rev": r0(r.rev), "cw": r0(r.cw), "gw": r0(r.gw), "pieces": r0(r.pieces),
                     "yield": r2(r["yield"]), "rev_per_awb": r0(r.rev_per_awb),
                     "mom": r2(r.mom * 100) if pd.notna(r.mom) else None, "share": round(r.share, 4), "cum_rev": r0(r.cum_rev)}
                    for m, r in monthly.iterrows()]
    quarterly = group_table(df, "quarter"); quarterly.sort(key=lambda r: r["key"])
    weekday = group_table(df, "weekday")
    wd_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday.sort(key=lambda r: wd_order.index(r["key"]))

    # ---------- 3. 통화
    currency = group_table(df, "AWB Currency", extra=lambda g: {"avg_rate": r2(g["rate"].mean()), "rev_local": r0(g["Billing Amount - Outbound"].sum())})
    currency_monthly = monthly_series(df, "AWB Currency", [c["key"] for c in currency])

    # ---------- 4. 노선/권역/방향
    routes = group_table(df, "route", top=30, extra=lambda g: {"origin": g["Origin"].iloc[0], "dest": g["Destination"].iloc[0],
                                                              "direction": g["direction"].iloc[0], "region": g["market_region"].iloc[0]})
    origins = group_table(df, "Origin", top=20)
    dests = group_table(df, "Destination", top=20)
    regions = group_table(df, "market_region")
    direction = group_table(df, "direction")
    region_monthly = monthly_series(df, "market_region", [r["key"] for r in regions])
    direction_monthly = monthly_series(df, "direction", [d["key"] for d in direction])
    # 권역 x 방향 매트릭스
    region_dir = group_table(df, ["market_region", "direction"])

    # ---------- 5. 대리점
    agents_raw = group_table(df, "Bill-To Party Name", extra=lambda g: {"group": g["agent_group"].iloc[0], "currency": g["AWB Currency"].mode().iloc[0],
                                                                        "spot_share": r2(g.loc[g["is_spot"], "rev_krw"].sum() / g["rev_krw"].sum() * 100) if g["rev_krw"].sum() else 0})
    agents_group = group_table(df, "agent_group", extra=lambda g: {"members": sorted(g["Bill-To Party Name"].unique().tolist()),
                                                                   "top_route": g.groupby("route")["rev_krw"].sum().idxmax(),
                                                                   "main_region": g.groupby("market_region")["rev_krw"].sum().idxmax()})
    top15 = [a["key"] for a in agents_group[:15]]
    agent_monthly = monthly_series(df, "agent_group", top15)
    others = df[~df["agent_group"].isin(top15)]
    om = others.groupby("month").agg(rev=("rev_krw", "sum"), cw=("cw_kg", "sum"), awb=("AWB Number", "count")).reindex(MONTHS, fill_value=0)
    agent_monthly["기타"] = {"rev": [r0(v) for v in om["rev"]], "cw": [r0(v) for v in om["cw"]], "awb": [int(v) for v in om["awb"]]}
    # 집중도(HHI, 누적 비중)
    shares = [a["share"] for a in agents_group]
    hhi = round(sum(s * s for s in shares) * 10000)
    cum = 0; cum_share = []
    for a in agents_group:
        cum += a["share"]; cum_share.append(round(cum, 4))

    # ---------- 5b. 고객 마스터 (해외발/인천발 업체정보)
    customer_type = group_table(df, "customer_type")
    customer_type_monthly = monthly_series(df, "customer_type", [c["key"] for c in customer_type])
    customers = group_table(df, "customer_name", extra=lambda g: {"customer_no": g["customer_no"].iloc[0], "type": g["customer_type"].iloc[0],
                                                                  "mapped": bool(g["customer_mapped"].iloc[0]),
                                                                  "bill_to": sorted(g["Bill-To Party Name"].unique().tolist()),
                                                                  "currency": g["AWB Currency"].mode().iloc[0],
                                                                  "top_route": g.groupby("route")["rev_krw"].sum().idxmax(),
                                                                  "spot_share": r2(g.loc[g["is_spot"], "rev_krw"].sum() / g["rev_krw"].sum() * 100) if g["rev_krw"].sum() else 0})
    cust_top = [c["key"] for c in customers if c["mapped"]][:12]
    customer_monthly = monthly_series(df, "customer_name", cust_top)
    from customers import CUSTOMERS
    seen = {c["key"] for c in customers}
    customers_no_data = [{"customer_no": c["no"], "name": c["name"], "type": c["type"], "currency": c["cur"], "origin": c["origin"]} for c in CUSTOMERS if c["name"] not in seen]
    customer_type_yield_monthly = {}
    for ct in [c["key"] for c in customer_type]:
        g = df[df["customer_type"] == ct].groupby("month").agg(rev=("rev_krw", "sum"), cw=("cw_kg", "sum")).reindex(MONTHS)
        customer_type_yield_monthly[ct] = [r2(a / b) if b and b > 0 else None for a, b in zip(g["rev"], g["cw"])]

    # ---------- 6. SHC(품목)
    ex = df[["shc_list", "rev_krw", "cw_kg"]].explode("shc_list").dropna(subset=["shc_list"])
    shc_tags = []
    for tag, g in ex.groupby("shc_list"):
        shc_tags.append({"key": tag, "meaning": SHC_MEANING.get(tag, ""), "awb": int(len(g)), "rev": r0(g["rev_krw"].sum()), "cw": r0(g["cw_kg"].sum()),
                         "awb_share": round(len(g) / len(df), 4), "rev_share": round(g["rev_krw"].sum() / total_rev, 4),
                         "yield": r2(g["rev_krw"].sum() / g["cw_kg"].sum()) if g["cw_kg"].sum() else None})
    shc_tags.sort(key=lambda r: -r["rev"])
    shc_primary = group_table(df, "shc_primary", top=20, extra=lambda g: {"meaning": SHC_MEANING.get(g["shc_primary"].iloc[0], "")})
    shc_combo = group_table(df.assign(combo=df["SHC"].fillna("(없음)")), "combo", top=20)
    shc_primary_monthly = monthly_series(df, "shc_primary", [s["key"] for s in shc_primary[:8]])

    # ---------- 7. 무게/밀도/단가 분포
    bins = [0, 45, 100, 300, 500, 1000, 3000, 10_000, 10_000_000]
    labels = ["~45kg", "45~100", "100~300", "300~500", "500~1t", "1~3t", "3~10t", "10t+"]
    df["cw_band"] = pd.cut(df["cw_kg"], bins=bins, labels=labels, include_lowest=True).astype(str)
    weight_band = group_table(df, "cw_band"); weight_band.sort(key=lambda r: labels.index(r["key"]) if r["key"] in labels else 99)
    density = group_table(df, "density_flag")
    ybins = [0, 500, 1000, 1500, 2000, 3000, 5000, 10000, 1e9]
    ylabels = ["~500", "500~1k", "1k~1.5k", "1.5k~2k", "2k~3k", "3k~5k", "5k~10k", "10k+"]
    yd = df[df["yield_krw_per_kg"].notna()].copy()
    yd["yield_band"] = pd.cut(yd["yield_krw_per_kg"], bins=ybins, labels=ylabels).astype(str)
    yield_band = group_table(yd, "yield_band"); yield_band.sort(key=lambda r: ylabels.index(r["key"]) if r["key"] in ylabels else 99)
    # 월별 kg당 단가: 권역별
    yield_region_monthly = {}
    for reg in [r["key"] for r in regions]:
        g = df[df["market_region"] == reg].groupby("month").agg(rev=("rev_krw", "sum"), cw=("cw_kg", "sum")).reindex(MONTHS)
        yield_region_monthly[reg] = [r2(a / b) if b and b > 0 else None for a, b in zip(g["rev"], g["cw"])]

    # ---------- 8. 기종 (일자별 기종현황 조인)
    aircraft = group_table(df, "aircraft", extra=lambda g: {"family": g["aircraft_family"].iloc[0], "flights": int(g.groupby(["First Flight Date", "fno"]).ngroups),
                                                             "cw_per_flight": r0(g["cw_kg"].sum() / g.groupby(["First Flight Date", "fno"]).ngroups)})
    aircraft_family = group_table(df, "aircraft_family")
    aircraft_monthly = monthly_series(df, "aircraft", [a["key"] for a in aircraft])
    aircraft_region = group_table(df, ["aircraft_family", "market_region"])
    # 기종 x 노선 top
    aircraft_route = group_table(df, ["aircraft", "route"], top=30)

    # ---------- 9. 스팟/할인/불일치/청구상태
    spot = group_table(df.assign(spot=df["is_spot"].map({True: "Spot Rate", False: "Contract/Tariff"})), "spot")
    spot_monthly = monthly_series(df.assign(spot=df["is_spot"].map({True: "Spot Rate", False: "Contract/Tariff"})), "spot", ["Spot Rate", "Contract/Tariff"])
    billing_status = group_table(df, "billing_status")
    audit_status = group_table(df, "audit_status")
    discrepancy = group_table(df.assign(d=df["Discrepancy - Manually Resolved"].fillna("(불일치 없음)")), "d", top=10)
    disc_total = r0((df["Discount"].fillna(0) * df["rate"]).sum())
    iata_vs_billing = {"iata_charge_krw": r0(df["iata_charge_krw"].sum()), "market_charge_krw": r0(df["market_charge_krw"].sum()),
                       "billing_krw": r0(total_rev), "discount_krw": disc_total,
                       "billing_to_iata_ratio": r2(total_rev / df["iata_charge_krw"].sum() * 100) if df["iata_charge_krw"].sum() else None}

    # ---------- 10. 상위 Commodity
    commodity = group_table(df.assign(c=df["Commodity"].fillna("(미기재)").str.upper().str.strip()), "c", top=25)

    # ---------- 11. 일별 시계열 (라인차트)
    daily = df.groupby("First Flight Date").agg(rev=("rev_krw", "sum"), cw=("cw_kg", "sum"), awb=("AWB Number", "count"))
    daily = daily.reindex(pd.date_range(f"{year}-01-01", f"{year}-{MONTHS[-1]:02d}-{pd.Timestamp(year, MONTHS[-1], 1).days_in_month}"), fill_value=0)
    daily_rows = {"date": [d.strftime("%Y-%m-%d") for d in daily.index], "rev": [r0(v) for v in daily["rev"]],
                  "cw": [r0(v) for v in daily["cw"]], "awb": [int(v) for v in daily["awb"]]}

    D_MAPPED = df.loc[df["customer_mapped"] == True, "rev_krw"].sum() / total_rev
    # ---------- 12. 인사이트 자동 도출
    insights = []
    insights.append(f"연간 매출 {total_rev/1e8:,.1f}억원, AWB {len(df):,}건, 유상중량 {total_cw/1000:,.0f}톤. AWB당 평균 {total_rev/len(df)/1e4:,.0f}만원, kg당 {total_rev/total_cw:,.0f}원.")
    if len(MONTHS) == 12:
        insights.append(f"하반기(7~12월) 매출 {h2/1e8:,.0f}억은 상반기 {h1/1e8:,.0f}억 대비 {(h2/h1-1)*100:+.0f}%. 12월 매출은 1월 대비 {(monthly.loc[12,'rev']/monthly.loc[1,'rev']-1)*100:+.0f}% — 연중 지속적인 우상향 성장.")
    else:
        insights.append(f"{year}년은 1~{MONTHS[-1]}월 {len(MONTHS)}개월 실적. 월평균 {total_rev/len(MONTHS)/1e8:,.1f}억, 단순 연환산 시 약 {total_rev/len(MONTHS)*12/1e8:,.0f}억 규모.")
    top_mom = monthly["mom"].dropna().sort_values(ascending=False).head(2)
    insights.append(f"최대 매출 월은 {best_m}월({monthly.loc[best_m,'rev']/1e8:,.1f}억, {monthly.loc[best_m,'share']*100:.1f}%). 전월 대비 상승폭이 큰 달: " + ", ".join(f"{int(m)}월({v*100:+.0f}%)" for m, v in top_mom.items()) + ".")
    ob = direction[0] if direction[0]["key"].startswith("Outbound") else direction[1]
    insights.append(f"한국 출발(Outbound) 매출 비중 {summary['outbound_share']*100:.0f}%. 해외 출발 화물은 건수 비중이 높으나 단가가 낮음(kg당 {[d for d in direction if d['key'].startswith('Inbound')][0]['yield']:,.0f}원 vs {ob['yield']:,.0f}원).")
    insights.append(f"권역별로는 {regions[0]['key']}({regions[0]['share']*100:.0f}%), {regions[1]['key']}({regions[1]['share']*100:.0f}%), {regions[2]['key']}({regions[2]['share']*100:.0f}%) 순. 상위 노선: {routes[0]['key']} {routes[0]['share']*100:.1f}%, {routes[1]['key']} {routes[1]['share']*100:.1f}%, {routes[2]['key']} {routes[2]['share']*100:.1f}%.")
    insights.append(f"대리점 집중도: Top1 {agents_group[0]['key']} {agents_group[0]['share']*100:.1f}%, Top5 {top5_share*100:.0f}%, HHI {hhi} ({'높음' if hhi>2500 else '중간' if hhi>1500 else '낮음'} 수준 집중). {agents_group[1]['key']}·{agents_group[2]['key']}가 2~3위.")
    icn = next(c for c in customer_type if c["key"] == "인천발"); ovs = next(c for c in customer_type if c["key"] == "해외발")
    insights.append(f"고객 구분(업체 마스터 기준): 인천발 업체 {icn['rev']/1e8:,.0f}억({icn['share']*100:.0f}%, kg당 {icn['yield']:,.0f}원) vs 해외발 업체 {ovs['rev']/1e8:,.0f}억({ovs['share']*100:.0f}%, kg당 {ovs['yield']:,.0f}원). 마스터 미등재 Bill-To(동남·TAMEX·RAON·항공사 등) 매출 {(1-D_MAPPED)*100:.0f}%는 추정 구분.")
    hi_yield = [s for s in shc_tags if s["awb"] >= 300 and s["yield"]][:]
    hi_yield.sort(key=lambda s: -s["yield"])
    insights.append(f"SHC 기준 고단가 품목(300건 이상): {', '.join(f'{s['key']}({s['meaning']}) {s['yield']:,.0f}원/kg' for s in hi_yield[:4])}. 약품(MSD)·전자(ELI)·배터리(BSA)가 매출 기여 상위.")
    wb_fam = aircraft_family[0]
    insights.append(f"기종별: {wb_fam['key']} 매출 비중 {wb_fam['share']*100:.0f}%. " + ", ".join(f"{a['key']} {a['share']*100:.0f}%" for a in aircraft[:4]) + ". 광동체(A330/B777) 투입 노선이 화물 매출의 핵심.")
    insights.append(f"Spot Rate 승인 건 매출 비중 {summary['spot_share']*100:.0f}%. 청구 기준 매출은 IATA 감사요금 대비 {iata_vs_billing['billing_to_iata_ratio']:.0f}% 수준(할인·시장가 적용).")
    rep = json.loads((PROCESSED / "etl_report.json").read_text())[str(year)]
    insights.append(f"데이터 품질: 원본 {rep['rows_raw']:,}행 중 완전중복 {rep['duplicate_awb_rows_dropped']}건 제거, Voided {rep['voided_rows']}건 제외, 매출 0원 AWB {summary['zero_rev_awb']}건(FOC/무상 등). 기종 매칭율 {rep['aircraft_join_rate']*100:.1f}%(KE 편명 등 타사 운항편은 미매칭)." + (f" {FX_2026_FALLBACK_NOTE}." if year == 2026 else ""))

    data = {
        "meta": {"generated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), "source": f"Quality Audit Analysis {year} (ICN)", "year": year,
                 "fx_note": "외화는 First Flight Date 월의 월평균 환율(ECB 교차) 적용 원화 환산" + (f" · {FX_2026_FALLBACK_NOTE}" if year == 2026 else ""),
                 "revenue_basis": "Billing Amount - Outbound", "weight_basis": "Audited Chargeable Weight", "months": MONTHS},
        "summary": summary, "insights": insights,
        "monthly": monthly_rows, "quarterly": quarterly, "weekday": weekday, "daily": daily_rows,
        "currency": currency, "currency_monthly": currency_monthly,
        "routes": routes, "origins": origins, "dests": dests, "regions": regions, "direction": direction,
        "region_monthly": region_monthly, "direction_monthly": direction_monthly, "region_direction": region_dir,
        "customer_type": customer_type, "customer_type_monthly": customer_type_monthly, "customers": customers, "customer_monthly": customer_monthly,
        "customers_no_data": customers_no_data, "customer_type_yield_monthly": customer_type_yield_monthly,
        "agents_raw": agents_raw, "agents_group": agents_group, "agent_monthly": agent_monthly, "agent_hhi": hhi, "agent_cum_share": cum_share,
        "shc_tags": shc_tags, "shc_primary": shc_primary, "shc_combo": shc_combo, "shc_primary_monthly": shc_primary_monthly,
        "weight_band": weight_band, "density": density, "yield_band": yield_band, "yield_region_monthly": yield_region_monthly,
        "aircraft": aircraft, "aircraft_family": aircraft_family, "aircraft_monthly": aircraft_monthly, "aircraft_region": aircraft_region, "aircraft_route": aircraft_route,
        "spot": spot, "spot_monthly": spot_monthly, "billing_status": billing_status, "audit_status": audit_status, "discrepancy": discrepancy,
        "iata_vs_billing": iata_vs_billing, "commodity": commodity,
    }
    data["_excel"] = dict(summary=summary, insights=insights, monthly_rows=monthly_rows, quarterly=quarterly, currency=currency, routes=routes,
                          regions=regions, region_dir=region_dir, customer_type=customer_type, customers=customers, agents_raw=agents_raw,
                          agents_group=agents_group, agent_monthly=agent_monthly, shc_tags=shc_tags, shc_primary=shc_primary, weight_band=weight_band,
                          yield_band=yield_band, aircraft=aircraft, aircraft_region=aircraft_region, aircraft_route=aircraft_route, spot=spot,
                          billing_status=billing_status, commodity=commodity)
    return data


def write_excel(data: dict, year: int):
    e = data["_excel"]
    summary, insights, monthly_rows, quarterly, currency, routes = e["summary"], e["insights"], e["monthly_rows"], e["quarterly"], e["currency"], e["routes"]
    regions, region_dir, customer_type, customers, agents_raw, agents_group = e["regions"], e["region_dir"], e["customer_type"], e["customers"], e["agents_raw"], e["agents_group"]
    agent_monthly, shc_tags, shc_primary, weight_band, yield_band = e["agent_monthly"], e["shc_tags"], e["shc_primary"], e["weight_band"], e["yield_band"]
    aircraft, aircraft_region, aircraft_route, spot, billing_status, commodity = e["aircraft"], e["aircraft_region"], e["aircraft_route"], e["spot"], e["billing_status"], e["commodity"]
    MONTHS = YEARS[year]["months"]
    OUTPUT.mkdir(exist_ok=True)
    with pd.ExcelWriter(OUTPUT / f"cargo_revenue_{year}_analysis.xlsx", engine="openpyxl") as xw:
        pd.DataFrame([summary]).T.rename(columns={0: "값"}).to_excel(xw, sheet_name="요약")
        pd.DataFrame({"인사이트": insights}).to_excel(xw, sheet_name="인사이트", index=False)
        pd.DataFrame(monthly_rows).to_excel(xw, sheet_name="월별", index=False)
        pd.DataFrame(quarterly).to_excel(xw, sheet_name="분기별", index=False)
        pd.DataFrame(currency).to_excel(xw, sheet_name="통화별", index=False)
        pd.DataFrame(routes).to_excel(xw, sheet_name="노선Top30", index=False)
        pd.DataFrame(regions).to_excel(xw, sheet_name="권역별", index=False)
        pd.DataFrame(region_dir).to_excel(xw, sheet_name="권역x방향", index=False)
        pd.DataFrame(customer_type).to_excel(xw, sheet_name="해외발vs인천발", index=False)
        pd.DataFrame(customers).assign(bill_to=lambda d: d["bill_to"].apply("·".join)).to_excel(xw, sheet_name="고객사(마스터)", index=False)
        pd.DataFrame(agents_raw).to_excel(xw, sheet_name="대리점(BillTo)", index=False)
        pd.DataFrame(agents_group).assign(members=lambda d: d["members"].apply("·".join)).to_excel(xw, sheet_name="대리점그룹", index=False)
        am = pd.DataFrame({k: v["rev"] for k, v in agent_monthly.items()}, index=[f"{m}월" for m in MONTHS]); am.to_excel(xw, sheet_name="월별x대리점그룹")
        pd.DataFrame(shc_tags).to_excel(xw, sheet_name="SHC태그", index=False)
        pd.DataFrame(shc_primary).to_excel(xw, sheet_name="SHC대표코드", index=False)
        pd.DataFrame(weight_band).to_excel(xw, sheet_name="무게구간", index=False)
        pd.DataFrame(yield_band).to_excel(xw, sheet_name="단가구간", index=False)
        pd.DataFrame(aircraft).to_excel(xw, sheet_name="기종별", index=False)
        pd.DataFrame(aircraft_region).to_excel(xw, sheet_name="기종x권역", index=False)
        pd.DataFrame(aircraft_route).to_excel(xw, sheet_name="기종x노선", index=False)
        pd.DataFrame(spot).to_excel(xw, sheet_name="스팟", index=False)
        pd.DataFrame(billing_status).to_excel(xw, sheet_name="청구상태", index=False)
        pd.DataFrame(commodity).to_excel(xw, sheet_name="Commodity", index=False)
    print(f"excel written: cargo_revenue_{year}_analysis.xlsx")


# ---------------------------------------------------------------- YoY 비교
def build_yoy(df_all: pd.DataFrame) -> dict:
    """전년 동기(1~N월) 대비 비교. N = 당해년도 가용 월수."""
    cur, base = CURRENT_YEAR, BASE_YEAR
    months = YEARS[cur]["months"]
    d = df_all[~df_all["is_voided"]]
    c = d[(d["year"] == cur)]
    b = d[(d["year"] == base) & (d["month"].isin(months))]
    b_full = d[d["year"] == base]

    def blk(g):
        return agg_block(g) if len(g) else {"awb": 0, "rev": 0, "cw": 0, "rev_per_awb": 0, "yield": None}

    def delta(a, b_):
        return {"rev_diff": a["rev"] - b_["rev"], "rev_pct": round((a["rev"] / b_["rev"] - 1) * 100, 1) if b_["rev"] else None,
                "cw_pct": round((a["cw"] / b_["cw"] - 1) * 100, 1) if b_["cw"] else None,
                "awb_pct": round((a["awb"] / b_["awb"] - 1) * 100, 1) if b_["awb"] else None,
                "yield_pct": round((a["yield"] / b_["yield"] - 1) * 100, 1) if a["yield"] and b_["yield"] else None}

    tot_c, tot_b = blk(c), blk(b)
    summary = {"cur_year": cur, "base_year": base, "months": months, "cur": tot_c, "base": tot_b, "delta": delta(tot_c, tot_b),
               "base_full_year_rev": r0(b_full["rev_krw"].sum()),
               "cur_annualized_rev": r0(tot_c["rev"] / len(months) * 12),
               "progress_vs_base_full": round(tot_c["rev"] / b_full["rev_krw"].sum(), 4)}

    # 월별 비교
    mc = c.groupby("month").agg(rev=("rev_krw", "sum"), cw=("cw_kg", "sum"), awb=("AWB Number", "count")).reindex(range(1, 13), fill_value=0)
    mb = b_full.groupby("month").agg(rev=("rev_krw", "sum"), cw=("cw_kg", "sum"), awb=("AWB Number", "count")).reindex(range(1, 13), fill_value=0)
    monthly = []
    for m in range(1, 13):
        row = {"month": m, "cur_rev": r0(mc.loc[m, "rev"]) if m in months else None, "base_rev": r0(mb.loc[m, "rev"]),
               "cur_cw": r0(mc.loc[m, "cw"]) if m in months else None, "base_cw": r0(mb.loc[m, "cw"]),
               "cur_awb": int(mc.loc[m, "awb"]) if m in months else None, "base_awb": int(mb.loc[m, "awb"]),
               "cur_yield": r2(mc.loc[m, "rev"] / mc.loc[m, "cw"]) if m in months and mc.loc[m, "cw"] else None,
               "base_yield": r2(mb.loc[m, "rev"] / mb.loc[m, "cw"]) if mb.loc[m, "cw"] else None}
        row["yoy_pct"] = round((row["cur_rev"] / row["base_rev"] - 1) * 100, 1) if row["cur_rev"] is not None and row["base_rev"] else None
        monthly.append(row)
    cum_c, cum_b = mc["rev"].cumsum(), mb["rev"].cumsum()
    cumulative = {"cur": [r0(cum_c.loc[m]) if m in months else None for m in range(1, 13)], "base": [r0(cum_b.loc[m]) for m in range(1, 13)]}

    def compare(by, top=None, min_rev=0):
        gc = {k: blk(g) for k, g in c.groupby(by)}
        gb = {k: blk(g) for k, g in b.groupby(by)}
        gb_full = b_full.groupby(by)["rev_krw"].sum().to_dict()
        rows = []
        for k in set(gc) | set(gb):
            a, bb = gc.get(k, blk(c.iloc[0:0])), gb.get(k, blk(b.iloc[0:0]))
            if max(a["rev"], bb["rev"]) < min_rev:
                continue
            # 신규: 전년 연간 실적 자체가 없음 / 이탈: 당해 실적 없음 / 동기無: 전년 하반기부터 시작(동기 비교 불가)
            status = ("신규" if gb_full.get(k, 0) <= 0 and a["rev"] > 0 else
                      "이탈" if a["rev"] == 0 and bb["rev"] > 0 else
                      "동기無" if bb["rev"] == 0 and a["rev"] > 0 else "유지")
            rows.append({"key": k if isinstance(k, str) else str(k), "cur": a, "base": bb, **delta(a, bb), "status": status,
                         "share_cur": round(a["rev"] / tot_c["rev"], 4) if tot_c["rev"] else 0, "share_base": round(bb["rev"] / tot_b["rev"], 4) if tot_b["rev"] else 0})
        rows.sort(key=lambda r: -r["cur"]["rev"])
        return rows[:top] if top else rows

    yoy = {"summary": summary, "monthly": monthly, "cumulative": cumulative,
           "region": compare("market_region"), "direction": compare("direction"), "customer_type": compare("customer_type"),
           "customer": compare("customer_name", min_rev=1e7), "agent_group": compare("agent_group", top=25),
           "route": compare("route", top=40, min_rev=5e7), "origin": compare("Origin", top=20), "dest": compare("Destination", top=20, min_rev=5e7),
           "aircraft": compare("aircraft"), "aircraft_family": compare("aircraft_family"),
           "shc_primary": compare("shc_primary", top=15), "currency": compare("AWB Currency"),
           "spot": compare(c.assign(_s=c["is_spot"].map({True: "Spot Rate", False: "Contract/Tariff"}))["_s"].name if False else "is_spot")}
    # spot key 보기 좋게
    for r in yoy["spot"]:
        r["key"] = "Spot Rate" if r["key"] == "True" else "Contract/Tariff"

    # SHC 태그 비교(explode)
    def shc_cmp(frame):
        ex = frame[["shc_list", "rev_krw", "cw_kg"]].explode("shc_list").dropna(subset=["shc_list"])
        return {k: {"rev": r0(g["rev_krw"].sum()), "cw": r0(g["cw_kg"].sum()), "awb": int(len(g))} for k, g in ex.groupby("shc_list")}
    sc, sb = shc_cmp(c), shc_cmp(b)
    tags = []
    for k in set(sc) | set(sb):
        a, bb = sc.get(k, {"rev": 0, "cw": 0, "awb": 0}), sb.get(k, {"rev": 0, "cw": 0, "awb": 0})
        if max(a["rev"], bb["rev"]) < 1e8:
            continue
        tags.append({"key": k, "meaning": SHC_MEANING.get(k, ""), "cur": a, "base": bb, "rev_pct": round((a["rev"] / bb["rev"] - 1) * 100, 1) if bb["rev"] else None, "rev_diff": a["rev"] - bb["rev"]})
    tags.sort(key=lambda r: -r["cur"]["rev"])
    yoy["shc_tags"] = tags

    # 증감 기여도 Top (노선/고객사)
    yoy["route_contrib_up"] = sorted([r for r in yoy["route"] if r["rev_diff"] > 0], key=lambda r: -r["rev_diff"])[:10]
    yoy["route_contrib_down"] = sorted([r for r in yoy["route"] if r["rev_diff"] < 0], key=lambda r: r["rev_diff"])[:10]
    yoy["customer_contrib_up"] = sorted([r for r in yoy["customer"] if r["rev_diff"] > 0], key=lambda r: -r["rev_diff"])[:10]
    yoy["customer_contrib_down"] = sorted([r for r in yoy["customer"] if r["rev_diff"] < 0], key=lambda r: r["rev_diff"])[:10]

    # 인사이트
    s_, dlt = summary, summary["delta"]
    ins = [f"{cur}년 1~{months[-1]}월 매출 {tot_c['rev']/1e8:,.1f}억 — 전년 동기 {tot_b['rev']/1e8:,.1f}억 대비 {dlt['rev_pct']:+.1f}% ({dlt['rev_diff']/1e8:+,.1f}억). "
           f"유상중량 {dlt['cw_pct']:+.1f}%, AWB {dlt['awb_pct']:+.1f}%, kg당 단가 {dlt['yield_pct']:+.1f}%.",
           f"{len(months)}개월 만에 {base}년 연간 매출({s_['base_full_year_rev']/1e8:,.0f}억)의 {s_['progress_vs_base_full']*100:.0f}% 달성. 단순 연환산 {s_['cur_annualized_rev']/1e8:,.0f}억."]
    best = max((r for r in monthly if r["yoy_pct"] is not None), key=lambda r: r["yoy_pct"])
    worst = min((r for r in monthly if r["yoy_pct"] is not None), key=lambda r: r["yoy_pct"])
    ins.append(f"월별 YoY 최고 {best['month']}월 {best['yoy_pct']:+.0f}%, 최저 {worst['month']}월 {worst['yoy_pct']:+.0f}%. " +
               ("하반기 진입(7~8월) 시 전년 수준으로 수렴 — 2025년 하반기 고성장 기저효과." if all(r["yoy_pct"] is not None and abs(r["yoy_pct"]) < 15 for r in monthly if r["month"] in (7, 8)) else ""))
    up = yoy["route_contrib_up"][:3]; dn = yoy["route_contrib_down"][:3]
    ins.append("매출 증가 기여 노선: " + ", ".join(f"{r['key']} {r['rev_diff']/1e8:+.1f}억" for r in up) + " / 감소 노선: " + ", ".join(f"{r['key']} {r['rev_diff']/1e8:+.1f}억" for r in dn) + ".")
    rg = sorted(yoy["region"], key=lambda r: -r["rev_diff"])
    ins.append("권역별 증감: " + ", ".join(f"{r['key']} {r['rev_diff']/1e8:+.0f}억({r['rev_pct']:+.0f}%)" if r["rev_pct"] is not None else f"{r['key']} {r['rev_diff']/1e8:+.0f}억(신규)" for r in rg[:4]) + " … " + ", ".join(f"{r['key']} {r['rev_diff']/1e8:+.0f}억" for r in rg[-2:]) + ".")
    ct = {r["key"]: r for r in yoy["customer_type"]}
    if "인천발" in ct and "해외발" in ct:
        ins.append(f"인천발 업체 {ct['인천발']['rev_pct']:+.0f}% ({ct['인천발']['cur']['rev']/1e8:,.0f}억), 해외발 업체 {ct['해외발']['rev_pct']:+.0f}% ({ct['해외발']['cur']['rev']/1e8:,.0f}억). "
                   f"신규 고객사({cur}년 첫 실적): {', '.join(r['key'] for r in yoy['customer'] if r['status']=='신규') or '없음'}. "
                   f"전년 하반기 시작(동기 비교 불가): {', '.join(r['key'] for r in yoy['customer'] if r['status']=='동기無') or '없음'}. "
                   f"이탈: {', '.join(r['key'] for r in yoy['customer'] if r['status']=='이탈') or '없음'}.")
    cu = yoy["customer_contrib_up"][:3]; cd = yoy["customer_contrib_down"][:3]
    ins.append("고객사 증가 기여: " + ", ".join(f"{r['key']} {r['rev_diff']/1e8:+.1f}억" for r in cu) + " / 감소: " + ", ".join(f"{r['key']} {r['rev_diff']/1e8:+.1f}억" for r in cd) + ".")
    ac = sorted(yoy["aircraft"], key=lambda r: -r["rev_diff"])
    ins.append("기종별 증감: " + ", ".join(f"{r['key']} {r['rev_diff']/1e8:+.0f}억({r['rev_pct']:+.0f}%)" for r in ac if r["rev_pct"] is not None and r["key"] != "미확인") + ".")
    ins.append(f"환율: 양 연도 모두 ECB 참고환율 월평균(원/외화 1단위) 적용. {cur}년 외화 매출 비중 약 {(1 - ct.get('인천발', {}).get('cur', {}).get('rev', 0) / tot_c['rev']) * 100 if tot_c['rev'] else 0:.0f}%. 원화 기준 YoY에는 환율 변동 효과 포함(EUR +6~10%, USD ±3%).")
    yoy["insights"] = ins
    return yoy


def write_yoy_excel(yoy: dict):
    OUTPUT.mkdir(exist_ok=True)
    flat = lambda rows: pd.DataFrame([{"key": r["key"], "status": r.get("status", ""), f"{yoy['summary']['cur_year']}_rev": r["cur"]["rev"], f"{yoy['summary']['base_year']}_rev": r["base"]["rev"],
                                       "rev_diff": r["rev_diff"], "rev_pct": r.get("rev_pct"), f"{yoy['summary']['cur_year']}_cw": r["cur"]["cw"], f"{yoy['summary']['base_year']}_cw": r["base"]["cw"],
                                       "cw_pct": r.get("cw_pct"), f"{yoy['summary']['cur_year']}_awb": r["cur"]["awb"], f"{yoy['summary']['base_year']}_awb": r["base"]["awb"],
                                       f"{yoy['summary']['cur_year']}_yield": r["cur"]["yield"], f"{yoy['summary']['base_year']}_yield": r["base"]["yield"], "yield_pct": r.get("yield_pct")} for r in rows])
    with pd.ExcelWriter(OUTPUT / f"cargo_revenue_yoy_{yoy['summary']['cur_year']}_vs_{yoy['summary']['base_year']}.xlsx", engine="openpyxl") as xw:
        pd.DataFrame({"인사이트": yoy["insights"]}).to_excel(xw, sheet_name="인사이트", index=False)
        pd.DataFrame(yoy["monthly"]).to_excel(xw, sheet_name="월별YoY", index=False)
        for name, key in [("권역", "region"), ("방향", "direction"), ("고객구분", "customer_type"), ("고객사", "customer"), ("대리점그룹", "agent_group"),
                          ("노선", "route"), ("출발지", "origin"), ("목적지", "dest"), ("기종", "aircraft"), ("SHC대표", "shc_primary"), ("통화", "currency"), ("Spot", "spot")]:
            flat(yoy[key]).to_excel(xw, sheet_name=name, index=False)
    print("excel written: yoy")


def main():
    df_all = pd.read_pickle(PROCESSED / "awb_clean.pkl")
    PUBLIC_DATA.mkdir(parents=True, exist_ok=True)
    years = sorted(df_all["year"].unique().tolist())
    for y in years:
        data = build(df_all, y)
        write_excel(data, y)
        data.pop("_excel")
        (PUBLIC_DATA / f"dashboard_{y}.json").write_text(json.dumps(data, ensure_ascii=False))
        print(f"dashboard_{y}.json written:", (PUBLIC_DATA / f"dashboard_{y}.json").stat().st_size // 1024, "KB")
    yoy = build_yoy(df_all)
    (PUBLIC_DATA / "yoy.json").write_text(json.dumps(yoy, ensure_ascii=False))
    write_yoy_excel(yoy)
    (PUBLIC_DATA / "index.json").write_text(json.dumps({"years": years, "current": CURRENT_YEAR, "base": BASE_YEAR,
                                                         "generated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False))
    legacy = PUBLIC_DATA / "dashboard.json"
    if legacy.exists():
        legacy.unlink()
    for i in yoy["insights"]:
        print("-", i)


if __name__ == "__main__":
    main()

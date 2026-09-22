"""
고객(업체) 마스터 — 사용자 제공 '해외발/인천발 업체정보' 기준.
Bill-To Party Name(Quality Audit) → 고객번호/업체명/구분 매핑에 사용.
bill_to: 해당 고객으로 귀속되는 Bill-To Party Name 목록(정확 매칭).
"""

CUSTOMERS = [
    # ---- 해외발 ----
    dict(no="100534", name="Stellar Way",                         type="해외발", cur="USD", origin="다낭발",   bill_to=["STELLAR WAY"]),
    dict(no="100869", name="ILG Aviation Australasia Pty Ltd",    type="해외발", cur="AUD", origin="시드니발", bill_to=["ILG"]),
    dict(no="100738", name="International Aircargo System Inc.", type="해외발", cur="JPY", origin="일본발",   bill_to=["IAS KIX", "IAS NRT"]),
    dict(no="100685", name="DP Aviation Partners Pte Ltd",        type="해외발", cur="SGD", origin="싱가포르발", bill_to=["DP SIN", "DP SGN"]),
    dict(no="100854", name="ATC Aviation Services AG",            type="해외발", cur="EUR", origin="유럽발",   bill_to=["ATC FRA", "ATC CDG", "ATC BCN", "ATC FCO", "ATC ZAG"]),
    dict(no="100932", name="(주) 스카우트",                         type="해외발", cur="KRW", origin="비슈케크발", bill_to=["SCOUT CO., LTD (FRU)", "SCOUT CO., LTD TAS"]),
    dict(no="100952", name="AVIAWORLD LLC",                       type="해외발", cur="CAD", origin="벤쿠버발", bill_to=["AVIAWORLD LLC"]),
    dict(no="100963", name="Bridge Air Agency",                   type="해외발", cur="HKD", origin="홍콩발",   bill_to=["BRIDGE AIR"]),
    dict(no="100518", name="Pantos Logistics Japan",              type="해외발", cur="JPY", origin="일본발",   bill_to=["LX PANTOS KE NRT", "LX PANTOS KE KIX"]),
    dict(no="101002", name="CONCORDE YVR",                        type="해외발", cur="CAD", origin="벤쿠버발", bill_to=["GROUP CONCORDE YVR"]),
    dict(no="100697", name="DEEPE AVIATION",                      type="해외발", cur="USD", origin="하노이발", bill_to=["DP HAN"]),
    dict(no="101011", name="(주) 페이버스",                         type="해외발", cur="KRW", origin="비슈케크발", bill_to=["FAVORS (BSZ)"]),
    dict(no="101020", name="Sea 2 Sky Co., Ltd.",                 type="해외발", cur="USD", origin="방콕발",   bill_to=["SEA2SKY BKK"]),
    dict(no="101014", name="PT. Global Cargo Services",           type="해외발", cur="USD", origin="자카르타발", bill_to=["PT. GCS CGK"]),
    # ---- 인천발 ----
    dict(no="100560", name="주식회사 에프티엘 코리아",       type="인천발", cur="KRW", origin="인천발", bill_to=["FTL KOREA CASS", "FTL KOREA CSA"]),
    dict(no="100894", name="㈜엑스트란스에어",              type="인천발", cur="KRW", origin="인천발", bill_to=["EXTRANS AIR CASS"]),
    dict(no="100925", name="주식회사 트렌스올",             type="인천발", cur="KRW", origin="인천발", bill_to=["TRANSALL KR CASS"]),
    dict(no="100926", name="주식회사 아이노마드",           type="인천발", cur="KRW", origin="인천발", bill_to=["I-NOMAD KR CASS"]),
    dict(no="100929", name="세중해운 주식회사",             type="인천발", cur="KRW", origin="인천발", bill_to=["SEJUNG KR CASS"]),
    dict(no="100931", name="트리플크라운인터내셔날",         type="인천발", cur="KRW", origin="인천발", bill_to=["TRIPLE CROWN KR CASS"]),
    dict(no="100932", name="㈜스카우트",                   type="인천발", cur="KRW", origin="인천발", bill_to=["SCOUT CO., LTD CASS"]),
    dict(no="100980", name="주식회사 글로벌맥스카고",        type="인천발", cur="KRW", origin="인천발", bill_to=["GLOBAL MAX CARGO CO., LTD", "GLOBAL MAX CARGO CO., LTD (NON CASS)"]),
    dict(no="100981", name="디에이치엘글로벌포워딩코리아",   type="인천발", cur="KRW", origin="인천발", bill_to=["DHL GLOBAL FORWARDING KOREA LTD"]),
    dict(no="100996", name="(주)디에스브이에어앤씨",         type="인천발", cur="KRW", origin="인천발", bill_to=["DSV AIR SEA KR LTD"]),
    dict(no="100563", name="대한통운",                     type="인천발", cur="KRW", origin="인천발", bill_to=["CJ LOGISTICS CORPORATION"]),
    dict(no="100999", name="비투엘물류 주식회사",           type="인천발", cur="KRW", origin="인천발", bill_to=["BTL LOGISTICS CO.,LTD."]),
    dict(no="101001", name="주식회사 엘엑스판토스",          type="인천발", cur="KRW", origin="인천발", bill_to=["LX PANTOS CO., LTD."]),
    dict(no="101008", name="㈜이카고웨이로지스틱스코리아",   type="인천발", cur="KRW", origin="인천발", bill_to=["E-CARGOWAY LOGISTICS KOREA CO.,LTD"]),
]

# 마스터에 없는 Bill-To — 매출 규모 기준 별도 표기(추정 구분). 마스터 확정 시 위 목록으로 이동.
UNMAPPED_HINT = {
    "DONGNAM KR CASS": ("인천발", "DONGNAM(동남)"), "DONGNAM ICN CSA": ("인천발", "DONGNAM(동남)"),
    "TAMEX CSA": ("인천발", "TAMEX"), "RAON AIRFREIGHT CO., LTD": ("인천발", "RAON"), "RAON AIRFREIGHT CO., LTD (NON CASS)": ("인천발", "RAON"),
    "TAMS INC.": ("인천발", "TAMS"), "IAG CARGO LIMITED": ("인천발", "항공사(Interline)"), "EMIRATES SPA": ("인천발", "항공사(Interline)"),
    "ITA AIRWAYS": ("인천발", "항공사(Interline)"), "LATAM CARGO": ("인천발", "항공사(Interline)"), "AMERICAN AIRLINES": ("인천발", "항공사(Interline)"),
    "AIR ASTANA": ("해외발", "항공사(Interline)"), "T WAY AIR CO LTD": ("인천발", "자사(FOC)"),
    "DELTA VN": ("해외발", "DELTA VN(다낭)"), "AVIANCA CARGO": ("인천발", "항공사(Interline)"), "THE HWA CHEONG INC.": ("인천발", "THE HWA CHEONG"), "AIR INCHEON": ("해외발", "AIR INCHEON(정저우)"), "WALKIN": ("해외발", "WALKIN(정저우)"),
}

_BILL_TO_INDEX = {b: c for c in CUSTOMERS for b in c["bill_to"]}


def lookup(bill_to_name: str) -> dict:
    """Bill-To Party Name → {customer_no, customer_name, customer_type, mapped}"""
    c = _BILL_TO_INDEX.get(bill_to_name)
    if c:
        return dict(customer_no=c["no"], customer_name=c["name"], customer_type=c["type"], mapped=True)
    typ, nm = UNMAPPED_HINT.get(bill_to_name, ("미분류", bill_to_name))
    return dict(customer_no="", customer_name=nm, customer_type=typ, mapped=False)

"""분석 공통 설정: 경로, 대리점 그룹핑 규칙, SHC 코드 의미, 노선 권역."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
PUBLIC_DATA = ROOT / "public" / "data"

USER_ANALYSIS_FILE = RAW / "user_analysis_2025.xlsx"  # Quality_Audit_2025_월별_매출 분석.xlsx (2025 환율 시트 사용)

# 연도별 원본 파일 (Quality Audit / 일자별 기종현황). 헤더 행은 'AWB Number'를 자동 탐지.
YEARS = {
    2025: dict(qa=RAW / "quality_audit_2025.xlsx", aircraft=RAW / "aircraft_daily_2025.xlsx", months=list(range(1, 13))),
    2026: dict(qa=RAW / "quality_audit_2026.xlsx", aircraft=RAW / "aircraft_daily_2026.xlsx", months=list(range(1, 9))),
}
CURRENT_YEAR, BASE_YEAR = 2026, 2025

# 2026 환율: 확정 월평균 환율 미수령 → 임시로 2025년 12월 월평균 환율(ECB 교차)을 전월 동일 적용.
# 사용자 분석 파일과 동일 방식의 2026 월별 환율을 받으면 아래 dict에 {통화: [1월..N월]} 형태로 입력하면 우선 적용됨.
# 2026 월별 평균 환율 (원/외화 1단위, ECB 일별 참고환율 원화 환산 후 월별 산술평균). 사용자 확정 제공(2026-09-22).
# 9월은 9/1~9/21 공시분 잠정 평균.
FX_2026_OVERRIDE: dict[str, list[float]] = {
    "KRW": [1.00] * 9,
    "USD": [1457.21, 1448.23, 1490.88, 1481.35, 1490.92, 1530.14, 1490.85, 1402.99, 1358.21],
    "EUR": [1710.38, 1712.39, 1723.13, 1734.05, 1740.27, 1762.32, 1702.16, 1626.41, 1571.46],
    "SGD": [1138.24, 1143.14, 1165.08, 1161.26, 1168.72, 1188.08, 1154.28, 1099.24, 1069.11],
    "HKD": [186.90, 185.28, 190.49, 189.10, 190.34, 195.23, 190.13, 178.89, 173.18],
    "JPY": [9.30, 9.33, 9.40, 9.31, 9.42, 9.52, 9.17, 8.84, 8.71],
    "AUD": [988.54, 1021.53, 1046.29, 1051.67, 1070.44, 1075.26, 1038.12, 996.27, 972.94],
    "CAD": [1057.55, 1060.93, 1087.30, 1077.31, 1085.82, 1090.23, 1055.93, 1008.75, 978.39],
}
FX_2026_FALLBACK_NOTE = "2026 외화는 ECB 참고환율 월평균(확정, 1~8월) 적용"
STATION = "ICN"

# 매출 기준 컬럼
REVENUE_COL = "Billing Amount - Outbound"
WEIGHT_COL = "Audited Chargeable Weight"

# 대리점 2차 그룹핑 규칙 (사용자 분석 '대리점순위_2차' 시트와 동일)
# key: Bill-To Party Name 접두어/정확 매칭, value: 그룹명
AGENT_GROUP_RULES = [
    (("FTL KOREA CASS", "FTL KOREA CSA"), "FTL KOREA"),
    (("ATC FRA", "ATC CDG", "ATC BCN", "ATC FCO", "ATC ZAG"), "ATC (유럽계)"),
    (("EXTRANS AIR CASS",), "EXTRANS AIR"),
    (("DP SIN", "DP SGN", "DP HAN"), "DP (SIN/SGN/HAN)"),
    (("BRIDGE AIR",), "BRIDGE AIR"),
    (("TRIPLE CROWN KR CASS",), "TRIPLE CROWN KR CASS"),
    (("DONGNAM ICN CSA", "DONGNAM KR CASS"), "DONGNAM"),
    (("TAMEX CSA",), "TAMEX CSA"),
    (("SEJUNG KR CASS",), "SEJUNG KR CASS"),
    (("TRANSALL KR CASS",), "TRANSALL KR CASS"),
    (("RAON AIRFREIGHT CO., LTD", "RAON AIRFREIGHT CO., LTD (NON CASS)"), "RAON AIRFREIGHT CO., LTD"),
    (("I-NOMAD KR CASS",), "I-NOMAD KR CASS"),
    (("STELLAR WAY",), "STELLAR WAY"),
    (("IAS KIX", "IAS NRT"), "IAS"),
    (("GLOBAL MAX CARGO CO., LTD",), "GLOBAL MAX CARGO CO., LTD"),
    (("SCOUT CO., LTD CASS", "SCOUT CO., LTD (FRU)", "SCOUT CO., LTD TAS"), "SCOUT CO., LTD"),
    (("LX PANTOS KE NRT", "LX PANTOS KE KIX"), "LX PANTOS"),
]

def agent_group(name: str) -> str:
    """Bill-To Party Name → 대리점 그룹명. 규칙에 없으면 원래 이름 유지."""
    if not isinstance(name, str):
        return "UNKNOWN"
    n = name.strip()
    for members, grp in AGENT_GROUP_RULES:
        if n in members:
            return grp
    return n

# SHC(Special Handling Code) 참고 의미
SHC_MEANING = {
    "GEN": "일반화물", "SPX": "보안검색 완료화물", "MSD": "약품", "ELI": "리튬이온배터리(장비내장)",
    "EAP": "전자부품", "BUP": "BUP(대리점 자체 ULD)", "PER": "신선화물", "COL": "냉장(2~8℃)",
    "NSC": "비보안 화물", "EAW": "환적 동물/온도", "MAL": "우편", "HEA": "중량물", "BSA": "배터리",
    "RMD": "의료기기", "ICE": "드라이아이스", "ELM": "리튬메탈(장비내장)", "DGR": "위험물",
    "FRO": "냉동", "XPS": "특송", "PEM": "육류", "CON": "화물 통합", "ECC": "e-Commerce",
    "PIL": "의약품", "PES": "수산물", "CRT": "온도관리(15~25℃)", "FOC": "무상", "PEP": "과일/야채",
    "EAT": "식품", "DGD": "위험물(서류)", "EXP": "긴급", "AOG": "항공기 부품(긴급)", "AVI": "생동물",
    "BIG": "대형화물", "OHG": "오버행", "RPB": "리튬이온배터리 단품", "PEF": "화훼", "VAL": "귀중품", "HUM": "유해",
}

# 공항 → 권역 (일자별 기종현황 Line 컬럼 기준으로 보완)
REGION_OF = {
    "ICN": "한국", "PUS": "한국", "TAE": "한국", "CJJ": "한국", "CJU": "한국", "GMP": "한국",
    "KIX": "일본", "NRT": "일본", "FUK": "일본", "CTS": "일본", "OKA": "일본", "NGO": "일본", "HND": "일본", "KMJ": "일본", "OIT": "일본", "KOJ": "일본", "SDJ": "일본", "HIJ": "일본", "KIJ": "일본", "MMY": "일본",
    "HKG": "중국/홍콩", "PVG": "중국/홍콩", "SHA": "중국/홍콩", "TSN": "중국/홍콩", "CGO": "중국/홍콩", "MFM": "중국/홍콩", "YNJ": "중국/홍콩", "WUH": "중국/홍콩", "SJW": "중국/홍콩", "PEK": "중국/홍콩", "SZX": "중국/홍콩", "CAN": "중국/홍콩", "HGH": "중국/홍콩",
    "TPE": "대만", "KHH": "대만",
    "SIN": "동남아", "BKK": "동남아", "DAD": "동남아", "SGN": "동남아", "HAN": "동남아", "CXR": "동남아", "CNX": "동남아", "MNL": "동남아", "CEB": "동남아", "KLO": "동남아", "KUL": "동남아", "DPS": "동남아", "CGK": "동남아", "HKT": "동남아", "RGN": "동남아", "VTE": "동남아", "PNH": "동남아", "CRK": "동남아", "PQC": "동남아",
    "SYD": "대양주", "MEL": "대양주", "BNE": "대양주", "GUM": "대양주", "SPN": "대양주",
    "FRA": "유럽", "CDG": "유럽", "BCN": "유럽", "FCO": "유럽", "ZAG": "유럽", "WAW": "유럽", "MAD": "유럽", "MXP": "유럽", "AMS": "유럽", "LHR": "유럽", "VIE": "유럽", "PRG": "유럽", "MUC": "유럽",
    "FRU": "러시아/중앙아", "TAS": "러시아/중앙아", "ALA": "러시아/중앙아", "ULN": "러시아/중앙아", "VVO": "러시아/중앙아", "UUS": "러시아/중앙아",
    "YVR": "미주", "LAX": "미주", "JFK": "미주", "SFO": "미주", "SEA": "미주", "YYZ": "미주", "YYC": "미주", "DFW": "미주", "MIA": "미주",
    # 이원 구간(interline/beyond) 목적지 — 유럽
    "LGG": "유럽", "ANR": "유럽", "BRU": "유럽", "VLC": "유럽", "BIO": "유럽", "NAP": "유럽", "VCE": "유럽", "OSL": "유럽", "GVA": "유럽",
    "ZRH": "유럽", "HAM": "유럽", "DUS": "유럽", "BLQ": "유럽", "FLR": "유럽", "GOA": "유럽", "LJU": "유럽", "SJJ": "유럽", "ATH": "유럽",
    "IST": "유럽", "SVO": "유럽", "LIL": "유럽", "MRS": "유럽", "LYS": "유럽", "BOD": "유럽", "MAN": "유럽", "DUB": "유럽", "ARN": "유럽",
    "HEL": "유럽", "LUX": "유럽", "BUD": "유럽", "VIT": "유럽", "TBS": "유럽", "EVN": "유럽", "GYD": "유럽",
    # 중동
    "DXB": "중동", "DWC": "중동", "AUH": "중동", "DOH": "중동", "SHJ": "중동", "MCT": "중동", "BAH": "중동", "KWI": "중동", "RUH": "중동",
    "JED": "중동", "DMM": "중동", "AMM": "중동", "BEY": "중동", "TLV": "중동", "BGW": "중동", "EBL": "중동", "IKA": "중동", "SLL": "중동",
    # 중남미
    "BOG": "중남미", "MEX": "중남미", "GDL": "중남미", "SDQ": "중남미", "ASU": "중남미", "MVD": "중남미", "LIM": "중남미", "GUA": "중남미",
    "SCL": "중남미", "CCS": "중남미", "GEO": "중남미", "SAL": "중남미", "CNF": "중남미", "VVI": "중남미", "SAP": "중남미", "CWB": "중남미",
    "NVT": "중남미", "SSA": "중남미", "VIX": "중남미", "MDE": "중남미", "LPB": "중남미", "GRU": "중남미", "PUQ": "중남미", "HAV": "중남미",
    "GIG": "중남미", "PUJ": "중남미", "BSB": "중남미", "FOR": "중남미", "PTY": "중남미", "FLN": "중남미", "SJO": "중남미", "GYE": "중남미",
    "BEL": "중남미", "REC": "중남미", "VCP": "중남미", "MAO": "중남미", "JOI": "중남미", "CUN": "중남미", "UIO": "중남미", "PBM": "중남미",
    "EZE": "중남미", "GCM": "중남미", "MGA": "중남미", "POS": "중남미", "SLZ": "중남미", "COR": "중남미", "CLO": "중남미", "NAT": "중남미",
    "AUA": "중남미", "PTP": "중남미", "SJU": "중남미", "FPO": "중남미", "MPN": "중남미",
    # 아프리카
    "CAI": "아프리카", "CMN": "아프리카", "NBO": "아프리카", "ADD": "아프리카", "DAR": "아프리카", "EBB": "아프리카", "OXB": "아프리카",
    "RUN": "아프리카", "TMS": "아프리카", "VXE": "아프리카", "RAI": "아프리카", "SID": "아프리카",
    # 서남아/기타 아시아
    "DAC": "서남아", "BOM": "서남아", "MAA": "서남아", "KHI": "서남아", "KTI": "동남아",
    # 중국 추가
    "CTU": "중국/홍콩", "TAO": "중국/홍콩", "CKG": "중국/홍콩",
    # 중앙아시아 추가
    "UBN": "러시아/중앙아", "BSZ": "러시아/중앙아", "SWK": "러시아/중앙아", "BSR": "중동",
    # 2026 추가 — 미주(북미)
    "ATL": "미주", "BNA": "미주", "BOS": "미주", "CLT": "미주", "CMH": "미주", "DEN": "미주", "DTW": "미주", "ELP": "미주", "IAD": "미주",
    "IAH": "미주", "IND": "미주", "LIT": "미주", "LRD": "미주", "MCI": "미주", "MCO": "미주", "MEM": "미주", "MSP": "미주", "ORD": "미주",
    "PHL": "미주", "SDF": "미주", "SLC": "미주", "STL": "미주", "TPA": "미주", "TUL": "미주", "YEG": "미주", "YUL": "미주", "YWG": "미주",
    # 2026 추가 — 중남미
    "BAQ": "중남미", "BGI": "중남미", "CUR": "중남미", "KIN": "중남미", "MTY": "중남미", "POA": "중남미", "VLN": "중남미",
    # 2026 추가 — 유럽/아프리카/서남아/기타
    "LIS": "유럽", "LPA": "유럽", "MHG": "유럽", "NTE": "유럽", "ACC": "아프리카", "LOS": "아프리카", "MPM": "아프리카", "TUN": "아프리카", "POG": "아프리카",
    "AMD": "서남아", "BLR": "서남아", "CCU": "서남아", "DEL": "서남아", "HYD": "서남아", "MJI": "아프리카", "PEN": "동남아", "PER": "대양주", "SHE": "중국/홍콩",
    "ANU": "중남미", "BDA": "미주", "EWR": "미주", "LAS": "미주", "PIT": "미주", "YOW": "미주", "YYJ": "미주", "YYT": "미주", "NLU": "중남미",
    "HME": "아프리카", "PHC": "아프리카", "NQZ": "러시아/중앙아", "YNT": "중국/홍콩",
}

def region_of(code: str) -> str:
    return REGION_OF.get(code, "기타")

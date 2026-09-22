# 2025~2026 화물 매출 분석 (Trinity Airways · ICN)

Quality Audit Analysis(QLTAUDANLRPT) 2025년 1~12월 AWB 데이터를 기반으로 화물 매출을 분석하고,
인터랙티브 웹 대시보드로 시각화하는 프로젝트입니다.

## 데이터 소스

| 파일 | 용도 |
|---|---|
| `Quality Audit Analysis_2025_1~12월.xlsx` | **기준 데이터(2025).** AWB 40,179건 × 86컬럼 (헤더 행 자동 탐지, 마지막 행은 합계) |
| `Quality Audit Analysis_2026_1~8월.xlsx` | **기준 데이터(2026, 1~8월).** AWB 30,691건, 동일 86컬럼 (헤더 30행) |
| `Quality_Audit_2025_월별_매출 분석.xlsx` | 사용자 사전 분석. `환율` 시트(월별 평균 환율, ECB 교차)와 대리점 그룹핑 규칙을 그대로 채택 |
| `일자별 기종현황_2025년.xlsx` / `_2026년.xlsx` | **일자·편명별 기종 정보만 사용** (화물수입/무게 컬럼은 참고용, 미사용) |

> 원본 파일은 `data/raw/`에 두며 git에는 커밋하지 않습니다(.gitignore).

## 분석 기준

- **매출**: `Billing Amount - Outbound` × First Flight Date 월의 월평균 환율 → 원화 환산
  - 환율: ECB 일별 참고환율 원화 환산 후 월별 산술평균(원/외화 1단위, JPY는 1엔 기준). 2025는 사용자 분석 파일 `환율` 시트, 2026은 `config.FX_2026_OVERRIDE`(1~9월 확정, 9월은 9/21까지 잠정)
- **YoY**: 2026 1~8월 vs 2025 1~8월(전년 동기). 신규/이탈 판정은 2025 연간 실적 기준
- **무게**: `Audited Chargeable Weight` (유상중량, kg)
- **월 귀속**: `First Flight Date`
- **정제**: 합계행 제거, 완전중복 AWB 3건 제거, `Voided` 2건 제외 → 분석 모집단 40,174건
- **기종 조인**: `First Flight Date` + 편명(숫자) ↔ 일자별 기종현황 `출발일` + `flightno` (2025 99.8% / 2026 97.8%, KE 편명 등 타사 운항편은 미매칭)
- **검증**: 사용자 분석 총매출 665.77억 / 유상중량 38,208.8톤과 일치(중복 제거분 차이 0.003%)

## 프로젝트 구조

```
scripts/
  config.py      연도별 파일(YEARS)·환율 정책·대리점 그룹핑·SHC 의미·공항→권역 매핑
  customers.py   고객(업체) 마스터 — 해외발/인천발 고객번호·업체명 ↔ Bill-To Party Name 매핑
  etl.py         1단계: 연도별 원본 → 통합 정제 AWB 테이블 (data/processed/awb_clean.*, year 컬럼)
  analyze.py     2단계: 연도별 KPI → public/data/dashboard_{year}.json, YoY → yoy.json, Excel 리포트
public/
  index.html     대시보드 (정적 SPA, Chart.js)
  static/        app.js / style.css
  data/          index.json · dashboard_2025.json · dashboard_2026.json · yoy.json
output/
  cargo_revenue_2025_analysis.xlsx / cargo_revenue_2026_analysis.xlsx  연도별 집계(23시트)
  cargo_revenue_yoy_2026_vs_2025.xlsx  전년 동기 비교(14시트)
```

## 실행 방법

```bash
# 1. 원본 파일 배치
cp "Quality Audit Analysis_2025_1~12월.xlsx"      data/raw/quality_audit_2025.xlsx
cp "Quality_Audit_2025_월별_매출 분석.xlsx"       data/raw/user_analysis_2025.xlsx
cp "일자별 기종현황_2025년.xlsx"                  data/raw/aircraft_daily_2025.xlsx
cp "Quality Audit Analysis_2026_1~8월.xlsx"       data/raw/quality_audit_2026.xlsx
cp "일자별 기종현황_2026년.xlsx"                  data/raw/aircraft_daily_2026.xlsx

# 2. 파이프라인
pip install -r requirements.txt
python scripts/etl.py        # 정제 (최초 1회 엑셀 로딩 약 25초)
python scripts/analyze.py    # KPI 집계 + JSON + Excel 리포트

# 3. 대시보드 (정적 서빙)
python -m http.server 8080 --directory public
```

## 대시보드 탭

상단 **연도 선택(2025 / 2026)** 으로 모든 탭이 해당 연도 기준으로 전환됩니다.

0. **전년 대비(YoY)** – 월별/누적 비교, 중량·단가 비교, 권역·노선·고객사 증감 기여, 기종·해외발/인천발 비교, 상세 비교표(신규/이탈 표시)
1. **종합** – KPI 카드, 월별 매출/중량, 권역 비중, 대리점·노선 Top10, 자동 인사이트
2. **월별 추이** – 전월대비, AWB당 매출, Yield, 누적, 분기, 요일, 일별(7일 이동평균)
3. **노선/권역** – 권역·방향별 월별 스택, Origin/Destination Top, 권역 Yield, 노선 Top30
4. **고객사(해외발/인천발)** – 업체 마스터 기준 구분별 월별 매출·단가, 고객사 Top15, 실적표, 실적 없는 마스터 고객
5. **대리점** – 파레토(누적비중), 규모 vs 단가 버블, 월별×그룹, 1차/2차 순위표
6. **품목(SHC)** – 태그별 매출/단가, 대표 SHC 비중·월별, Commodity Top25
7. **기종** – 기종별 비중·월별·편당 중량·kg당 단가, 기종계열×권역, 기종×노선
8. **단가/무게** – 중량 구간, 단가 구간, 밀도 구분, 통화 구성, 권역별 월별 Yield
9. **감사/청구** – Spot vs 계약, 청구 상태, IATA/시장/청구 요금 비교, 불일치 유형

## 주요 결과 (2026 1~8월 vs 전년 동기)

- 매출 **619.0억 (+65.2%, +244.4억)**, 유상중량 +22.0%, AWB +33.8%, kg당 단가 2,294원(+35.5%)
- 8개월 만에 2025 연간 매출의 93% 달성, 단순 연환산 928억
- 월별 YoY 4월 +162% 최고, 7~8월은 전년 수준 수렴(2025 하반기 고성장 기저효과)
- 증가 기여: 미주 +80억(ICN→YVR +67억), 동남아 +42억(ICN→CGK +26억), 유럽 +49억 / 감소: ICN→LGG −7억
- 고객사: 트리플크라운 +54억, 엑스트란스에어 +46억, FTL코리아 +39억 / DONGNAM −24억, TAMEX −20억(이탈·축소)
- 신규 고객사(2026 첫 실적): 엘엑스판토스, 대한통운(CJ), PT. GCS, 비투엘물류, 이카고웨이

## 주요 결과 (2025)

- 연간 매출 **665.7억원**, AWB 40,174건, 유상중량 38,206톤, kg당 1,742원
- 하반기 매출이 상반기 대비 **+83%**, 12월(81.6억)이 최대
- 권역: 유럽 50% · 동남아 18% · 대양주 10%. 한국출발(Outbound) 매출 67%
- 대리점: FTL KOREA 25.3%, Top5 65% (HHI 1,206)
- 기종: 광동체(A330/B777) 매출 비중 96%

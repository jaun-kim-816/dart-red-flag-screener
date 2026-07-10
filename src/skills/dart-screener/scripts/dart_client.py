#!/usr/bin/env python3
"""DART Open API 클라이언트 — 재무 레드플래그 스크리닝용 데이터 수집·지표 계산.

표준 라이브러리만 사용 (의존성 없음). Python 3.9+.

사용법:
  python3 dart_client.py find <기업명>                    # 기업 고유번호 검색
  python3 dart_client.py collect <corp_code> [--years N] [--fs CFS|OFS]
                                                          # 최근 N개년 재무제표 수집 (기본 3)
  python3 dart_client.py metrics <corp_code> [--years N] [--fs CFS|OFS] [--end YYYY]
                                                          # 레드플래그 룰 계산용 지표 JSON 출력
                                                          # --end: 마지막 사업연도 지정 (과거 시점 백테스트용)
  python3 dart_client.py company <corp_code>              # 기업개황 (업종코드 등 — 동종업계 확인용)

API 키: 환경변수 DART_API_KEY 또는 실행 위치 상위 경로의 .env 파일(DART_API_KEY=...).
키는 어떤 출력에도 포함되지 않는다.
"""

import json
import os
import re
import ssl
import sys
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

BASE = "https://opendart.fss.or.kr/api"
CACHE_DIR = os.path.join(tempfile.gettempdir(), "dart-screener-cache")

# 사업보고서(11011) 기준. fnlttSinglAcntAll은 2015 사업연도 이후 제공.
REPORT_ANNUAL = "11011"


def _load_api_key():
    key = os.environ.get("DART_API_KEY", "").strip()
    if key:
        return key
    # 현재 디렉토리부터 상위로 올라가며 .env 탐색
    d = os.getcwd()
    while True:
        env_path = os.path.join(d, ".env")
        if os.path.isfile(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    m = re.match(r"\s*DART_API_KEY\s*=\s*(.+)\s*$", line)
                    if m:
                        return m.group(1).strip().strip('"').strip("'")
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    sys.exit("오류: DART_API_KEY가 없습니다. 환경변수 또는 .env에 설정하세요. "
             "(무료 발급: https://opendart.fss.or.kr)")


def _get(url, params):
    params = dict(params)
    params["crtfc_key"] = _load_api_key()
    qs = urllib.parse.urlencode(params)
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url + "?" + qs, headers={"User-Agent": "dart-screener/1.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        return resp.read()


def _corp_code_xml():
    """corpCode.zip 다운로드 후 캐시. 반환: CORPCODE.xml 경로."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    xml_path = os.path.join(CACHE_DIR, "CORPCODE.xml")
    if os.path.isfile(xml_path) and os.path.getsize(xml_path) > 1000:
        return xml_path
    raw = _get(BASE + "/corpCode.xml", {})
    zip_path = os.path.join(CACHE_DIR, "corpCode.zip")
    with open(zip_path, "wb") as f:
        f.write(raw)
    with zipfile.ZipFile(zip_path) as z:
        z.extract("CORPCODE.xml", CACHE_DIR)
    return xml_path


def cmd_find(name_query):
    """기업명 부분일치 검색 → 상장사 우선 정렬로 후보 출력."""
    xml_path = _corp_code_xml()
    results = []
    for _, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag == "list":
            corp_name = (elem.findtext("corp_name") or "").strip()
            if name_query in corp_name:
                results.append({
                    "corp_code": (elem.findtext("corp_code") or "").strip(),
                    "corp_name": corp_name,
                    "stock_code": (elem.findtext("stock_code") or "").strip(),
                })
            elem.clear()
    # 상장사(stock_code 있음) 우선, 이름 짧은 순
    results.sort(key=lambda r: (r["stock_code"] == "", len(r["corp_name"])))
    print(json.dumps(results[:15], ensure_ascii=False, indent=2))


def _fetch_fs(corp_code, year, fs_div):
    raw = _get(BASE + "/fnlttSinglAcntAll.json", {
        "corp_code": corp_code,
        "bsns_year": str(year),
        "reprt_code": REPORT_ANNUAL,
        "fs_div": fs_div,
    })
    data = json.loads(raw.decode("utf-8"))
    if data.get("status") != "000":
        return None, data.get("message", "unknown")
    return data.get("list", []), None


def _to_num(s):
    if not s:
        return None
    s = s.replace(",", "").strip()
    if s in ("-", ""):
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return None


# 계정 표준화: account_id(IFRS 태그) 우선, 없으면 account_nm 부분일치
ACCOUNT_MAP = [
    # key, sj_div, ifrs ids, name patterns
    ("revenue", "IS", ["ifrs-full_Revenue", "ifrs_Revenue"], ["매출액", "영업수익", "수익(매출액)"]),
    ("cogs", "IS", ["ifrs-full_CostOfSales", "ifrs_CostOfSales"], ["매출원가", "영업비용"]),
    ("operating_income", "IS", ["dart_OperatingIncomeLoss"], ["영업이익", "영업이익(손실)"]),
    ("net_income", "IS", ["ifrs-full_ProfitLoss", "ifrs_ProfitLoss"], ["당기순이익", "당기순이익(손실)", "연결당기순이익"]),
    ("trade_receivables", "BS", ["ifrs-full_TradeAndOtherCurrentReceivables", "ifrs_TradeAndOtherCurrentReceivables"], ["매출채권", "매출채권및기타채권", "매출채권 및 기타채권", "매출채권및기타유동채권"]),
    ("inventories", "BS", ["ifrs-full_Inventories", "ifrs_Inventories"], ["재고자산"]),
    ("total_assets", "BS", ["ifrs-full_Assets", "ifrs_Assets"], ["자산총계"]),
    ("total_equity", "BS", ["ifrs-full_Equity", "ifrs_Equity"], ["자본총계"]),
    ("intangibles", "BS", ["ifrs-full_IntangibleAssetsOtherThanGoodwill"], ["무형자산"]),
    ("goodwill", "BS", ["ifrs-full_Goodwill"], ["영업권"]),
    ("dev_costs", "BS", [], ["개발비"]),
    ("provisions", "BS", ["ifrs-full_CurrentProvisions", "ifrs-full_NoncurrentProvisions", "ifrs-full_OtherLongtermProvisions"], ["충당부채", "공사손실충당부채", "하자보수충당부채"]),
    ("allowance_dtr", "BS", [], ["대손충당금"]),
    ("assoc_investments", "BS", ["ifrs-full_InvestmentsInAssociatesAccountedForUsingEquityMethod", "ifrs-full_InvestmentAccountedForUsingEquityMethod"], ["관계기업투자", "지분법적용투자주식", "관계기업및공동기업투자", "종속기업, 관계기업 및 공동기업 투자"]),
    ("equity_method_pl", "IS", ["ifrs-full_ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod"], ["지분법손익", "지분법이익", "지분법손실"]),
    ("cfo", "CF", ["ifrs-full_CashFlowsFromUsedInOperatingActivities", "ifrs_CashFlowsFromUsedInOperatingActivities"], ["영업활동현금흐름", "영업활동으로 인한 현금흐름", "영업활동으로인한현금흐름"]),
    ("convertible_bonds", "BS", [], ["전환사채"]),
    ("derivative_liab", "BS", [], ["파생상품부채", "파생상품금융부채", "전환권"]),
    ("borrowings", "BS", ["ifrs-full_Borrowings", "ifrs-full_CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings"], ["차입금", "단기차입금", "장기차입금"]),
]

SJ_ALIASES = {"IS": ("IS", "CIS"), "BS": ("BS",), "CF": ("CF",)}


def _extract_accounts(rows):
    """API 응답 rows에서 표준화된 계정값 추출. 동일 key에 복수 매칭 시 합산(충당부채·차입금 등)."""
    out = {}
    matched_names = {}
    for key, sj, ids, patterns in ACCOUNT_MAP:
        total = None
        names = []
        for row in rows:
            if row.get("sj_div") not in SJ_ALIASES[sj]:
                continue
            acc_id = (row.get("account_id") or "").strip()
            acc_nm = (row.get("account_nm") or "").strip()
            hit = acc_id in ids or any(p in acc_nm.replace(" ", "") or p in acc_nm for p in patterns)
            if not hit:
                continue
            val = _to_num(row.get("thstrm_amount"))
            if val is None:
                continue
            # 표준 IFRS id 정확 일치는 단독 채택(중복 방지), 이름 매칭은 합산
            if acc_id in ids:
                total = val
                names = [acc_nm]
                break
            total = (total or 0) + val
            names.append(acc_nm)
        if total is not None:
            out[key] = total
            matched_names[key] = names
    return out, matched_names


def _collect_years(corp_code, n_years, fs_div, end_year=None):
    """최근 n개년 수집. end_year 지정 시 그 연도를 마지막으로 과거 방향 수집(백테스트용)."""
    import datetime
    years_data = []
    year = end_year if end_year else datetime.date.today().year - 1
    tried = 0
    while len(years_data) < n_years and tried < n_years + 3:
        rows, err = _fetch_fs(corp_code, year, fs_div)
        if rows:
            accounts, names = _extract_accounts(rows)
            years_data.append({"year": year, "accounts": accounts, "matched_names": names,
                               "n_rows": len(rows)})
        year -= 1
        tried += 1
    years_data.sort(key=lambda d: d["year"])
    return years_data


def cmd_collect(corp_code, n_years, fs_div, end_year=None):
    data = _collect_years(corp_code, n_years, fs_div, end_year)
    if not data:
        # 연결(CFS) 실패 시 별도(OFS) 폴백 안내
        sys.exit("오류: 재무제표를 찾지 못했습니다. fs_div를 OFS(별도)로 바꿔 시도하세요. "
                 "(fnlttSinglAcntAll은 2015 사업연도 이후 상장사만 지원)")
    print(json.dumps({"corp_code": corp_code, "fs_div": fs_div, "years": data},
                     ensure_ascii=False, indent=2))


def _growth(cur, prev):
    if cur is None or prev in (None, 0):
        return None
    return round((cur - prev) / abs(prev) * 100, 2)


def _ratio(a, b):
    if a is None or b in (None, 0):
        return None
    return round(a / b * 100, 2)


def cmd_metrics(corp_code, n_years, fs_div, end_year=None):
    """레드플래그 룰(R1~R9) 계산에 필요한 지표를 연도별로 산출."""
    data = _collect_years(corp_code, n_years, fs_div, end_year)
    if not data:
        sys.exit("오류: 재무제표를 찾지 못했습니다. --fs OFS 로 재시도하세요.")
    metrics = []
    for i, d in enumerate(data):
        a = d["accounts"]
        prev = data[i - 1]["accounts"] if i > 0 else {}
        m = {
            "year": d["year"],
            "revenue": a.get("revenue"),
            "revenue_growth_pct": _growth(a.get("revenue"), prev.get("revenue")),
            "receivables": a.get("trade_receivables"),
            "receivables_growth_pct": _growth(a.get("trade_receivables"), prev.get("trade_receivables")),
            "inventories": a.get("inventories"),
            "inventories_growth_pct": _growth(a.get("inventories"), prev.get("inventories")),
            "cogs_growth_pct": _growth(a.get("cogs"), prev.get("cogs")),
            "gross_margin_pct": (round((a["revenue"] - a["cogs"]) / a["revenue"] * 100, 2)
                                 if a.get("revenue") and a.get("cogs") else None),
            "operating_income": a.get("operating_income"),
            "cfo": a.get("cfo"),
            "oi_minus_cfo": (a["operating_income"] - a["cfo"]
                             if a.get("operating_income") is not None and a.get("cfo") is not None else None),
            "oi_minus_cfo_over_assets_pct": _ratio(
                (a["operating_income"] - a["cfo"])
                if a.get("operating_income") is not None and a.get("cfo") is not None else None,
                a.get("total_assets")),
            "provisions": a.get("provisions"),
            "provisions_growth_pct": _growth(a.get("provisions"), prev.get("provisions")),
            "receivables_over_revenue_pct": _ratio(a.get("trade_receivables"), a.get("revenue")),
            "intangibles_growth_pct": _growth(a.get("intangibles"), prev.get("intangibles")),
            "goodwill_over_assets_pct": _ratio(a.get("goodwill"), a.get("total_assets")),
            "dev_costs": a.get("dev_costs"),
            "assoc_investments": a.get("assoc_investments"),
            "assoc_investments_growth_pct": _growth(a.get("assoc_investments"), prev.get("assoc_investments")),
            "equity_method_pl": a.get("equity_method_pl"),
            "equity_method_yield_pct": _ratio(a.get("equity_method_pl"), a.get("assoc_investments")),
            "convertible_bonds": a.get("convertible_bonds"),
            "derivative_liab": a.get("derivative_liab"),
            "borrowings_growth_pct": _growth(a.get("borrowings"), prev.get("borrowings")),
            "equity": a.get("total_equity"),
            "net_income": a.get("net_income"),
        }
        metrics.append(m)
    print(json.dumps({"corp_code": corp_code, "fs_div": fs_div,
                      "note": "growth(%)는 전년 대비. 첫 연도는 비교 대상이 없어 null.",
                      "metrics": metrics}, ensure_ascii=False, indent=2))


def cmd_company(corp_code):
    """기업개황 조회 — 업종코드(induty_code)로 동종업계 여부 교차 확인."""
    raw = _get(BASE + "/company.json", {"corp_code": corp_code})
    data = json.loads(raw.decode("utf-8"))
    if data.get("status") != "000":
        sys.exit("오류: " + data.get("message", "unknown"))
    keep = {k: data.get(k) for k in
            ("corp_name", "corp_name_eng", "stock_code", "corp_cls", "induty_code", "est_dt", "acc_mt")}
    print(json.dumps(keep, ensure_ascii=False, indent=2))


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    cmd = args[0]
    n_years = 3
    fs_div = "CFS"
    end_year = None
    rest = []
    i = 1
    while i < len(args):
        if args[i] == "--years":
            n_years = int(args[i + 1]); i += 2
        elif args[i] == "--fs":
            fs_div = args[i + 1].upper(); i += 2
        elif args[i] == "--end":
            end_year = int(args[i + 1]); i += 2
        else:
            rest.append(args[i]); i += 1
    if cmd == "find" and rest:
        cmd_find(rest[0])
    elif cmd == "collect" and rest:
        cmd_collect(rest[0], n_years, fs_div, end_year)
    elif cmd == "metrics" and rest:
        cmd_metrics(rest[0], n_years, fs_div, end_year)
    elif cmd == "company" and rest:
        cmd_company(rest[0])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

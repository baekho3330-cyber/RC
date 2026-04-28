"""
리뷰 분석 프로그램 - 웹사이트 URL로 리뷰 수집 + Claude AI 분석
지원: 현대리바트몰 · 오늘의집
사용법: python analyze.py
"""
import sys
import io
import os
import re
from pathlib import Path
from datetime import datetime
import anthropic

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding="utf-8", errors="replace")

OUTPUT_DIR = "output"
Path(OUTPUT_DIR).mkdir(exist_ok=True)

# ── 사이트 감지 ────────────────────────────────────────────────────────────
SITE_PATTERNS = {
    "livart":   r"hyundailivart\.co\.kr",
    "ohou":     r"(?:store\.)?ohou\.se",
    "hanssem":  r"store\.hanssem\.com",
}

SITE_NAMES = {
    "livart":   "현대리바트몰",
    "ohou":     "오늘의집",
    "hanssem":  "한샘몰",
}


def detect_site(text: str) -> str | None:
    for site, pat in SITE_PATTERNS.items():
        if re.search(pat, text, re.IGNORECASE):
            return site
    return None


# ── 사이트별 크롤러 호출 ───────────────────────────────────────────────────

def crawl_livart(url: str, max_reviews: int) -> tuple[list[dict], dict]:
    from crawler import crawl_livart_reviews
    return crawl_livart_reviews(url, max_reviews=max_reviews), {}


def crawl_ohou(url: str, max_reviews: int) -> tuple[list[dict], dict]:
    from ohou_analyzer import extract_product_id, fetch_all_reviews
    pid = extract_product_id(url)
    if not pid:
        raise ValueError("오늘의집 상품 ID를 URL에서 추출할 수 없습니다.")
    reviews, stats = fetch_all_reviews(pid)
    return reviews[:max_reviews], stats


def crawl_hanssem(url: str, max_reviews: int) -> tuple[list[dict], dict]:
    from hanssem_crawler import crawl_hanssem_reviews
    return crawl_hanssem_reviews(url, max_reviews=max_reviews), {}


CRAWLERS = {
    "livart":  crawl_livart,
    "ohou":    crawl_ohou,
    "hanssem": crawl_hanssem,
}


# ── 리뷰 텍스트 구성 (Claude 입력용) ──────────────────────────────────────

def _field(review: dict, *keys: str) -> str:
    for k in keys:
        v = review.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def build_review_text(reviews: list[dict], stats: dict = {}) -> str:
    if not reviews:
        return ""

    total = len(reviews)
    ratings = [r.get("별점") for r in reviews
               if isinstance(r.get("별점"), (int, float)) and r.get("별점")]
    avg = sum(ratings) / len(ratings) if ratings else 0
    product_name = _field(reviews[0], "상품명", "상품") or "상품"

    lines = [
        f"[상품] {product_name}",
        f"[총 리뷰] {total}개 | 평균 별점: {avg:.2f}/5.00",
    ]
    if stats:
        dist = [stats.get(f"countFor{i}", 0) for i in [5, 4, 3, 2, 1]]
        lines.append(
            f"[별점 분포] 5점:{dist[0]}  4점:{dist[1]}  3점:{dist[2]}  "
            f"2점:{dist[3]}  1점:{dist[4]}"
        )
    lines.append("")

    for i, r in enumerate(reviews, 1):
        content = _field(r, "리뷰내용", "내용", "content", "reviewContent")
        if not content:
            continue
        rating = _field(r, "별점", "rating", "starScore")
        date   = _field(r, "작성일", "date", "created_at")
        option = _field(r, "구매옵션", "옵션", "option", "purchaseOption")

        meta = f"[{i}] 별점:{rating}"
        if option:
            meta += f" | 옵션:{option}"
        if date:
            meta += f" | 날짜:{date}"
        lines += [meta, content, ""]

    return "\n".join(lines)


# ── Claude AI 분석 ────────────────────────────────────────────────────────

ANALYSIS_SYSTEM = (
    "당신은 소비자 리뷰 분석 전문가입니다. "
    "주어진 리뷰 데이터를 바탕으로 마케팅팀·제품팀·경영진이 즉시 활용할 수 있는 "
    "구조화된 한국어 분석 보고서를 작성합니다."
)

ANALYSIS_TEMPLATE = """\
다음은 '{product}' 상품의 실제 구매자 리뷰 데이터입니다.

{review_text}

---

위 리뷰를 분석하여 다음 구조로 보고서를 작성해주세요:

## 1. 종합 요약
- 전반적인 고객 만족도 평가
- 핵심 키워드 (긍정 5개 / 부정 5개)

## 2. 긍정 분석
- 가장 많이 언급된 강점 (상위 5개, 각 근거 리뷰 인용 포함)
- 구매 만족의 주요 이유

## 3. 부정/개선 분석
- 불만 사항 및 개선 요청 (상위 5개, 근거 인용 포함)
- 반복적으로 나타나는 문제점

## 4. 옵션별 분석
- 인기 옵션 및 각 옵션의 만족도 차이
- 옵션 선택 시 주의사항

## 5. 사용 맥락 분석
- 주요 구매 목적 및 사용 대상
- 사용 기간별 만족도 변화 (언급된 경우)

## 6. 경쟁력 인사이트
- 가성비 관련 언급
- 타 브랜드·제품과의 비교

## 7. 개선 제안 (우선순위 Top 3)
- 즉시 개선 가능한 사항
- 중장기 개선 사항

## 8. 마케팅 활용 포인트
- 광고 카피로 활용 가능한 실제 리뷰 문구 3개
- 타겟 고객군 제안
"""


def analyze_with_claude(review_text: str, product_name: str, api_key: str) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    prompt = ANALYSIS_TEMPLATE.format(product=product_name, review_text=review_text)

    print("\n[*] Claude AI 분석 중...\n")
    report = ""

    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=8000,
        system=ANALYSIS_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            report += text

    print("\n")
    return report


# ── Excel 저장 ────────────────────────────────────────────────────────────

COL_WIDTHS = {
    "리뷰ID": 14, "상품명": 40, "상품ID": 14, "카탈로그ID": 14,
    "별점": 8, "제목": 30, "리뷰내용": 80, "내용": 80,
    "작성자": 15, "작성일": 12, "구매옵션": 25, "옵션": 25,
    "미디어타입": 10, "미디어": 10, "도움수": 10, "토픽": 25,
    "브랜드": 12, "리뷰타입": 15, "사용기간": 12,
}


def save_results(
    reviews: list[dict], report: str, site: str, product_name: str,
    output_dir: str = OUTPUT_DIR,
) -> tuple[str, str]:
    import pandas as pd
    from openpyxl.styles import Font, PatternFill, Alignment

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r'[\\/:*?"<>|]', "_", product_name)[:30]
    prefix = f"{output_dir}/{site}_{safe}_{ts}"

    df = pd.DataFrame(reviews)
    # 쿠팡은 '내용' → '리뷰내용' 통일
    if "내용" in df.columns and "리뷰내용" not in df.columns:
        df = df.rename(columns={"내용": "리뷰내용"})
    if "리뷰내용" in df.columns:
        before = len(df)
        df = df.drop_duplicates(subset=["리뷰내용"])
        df = df[df["리뷰내용"].str.strip().str.len() > 0]
        if (removed := before - len(df)):
            print(f"[*] 중복/빈 리뷰 제거: {removed}건")
    df = df.reset_index(drop=True)

    total = len(df)
    ratings = [r.get("별점") for r in reviews
               if isinstance(r.get("별점"), (int, float)) and r.get("별점")]
    avg = round(sum(ratings) / len(ratings), 2) if ratings else 0

    H_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    H_FONT = Font(color="FFFFFF", bold=True)
    content_col = next((i for i, c in enumerate(df.columns, 1) if c == "리뷰내용"), None)

    # 리뷰 데이터 Excel
    reviews_path = f"{prefix}_reviews.xlsx"
    with pd.ExcelWriter(reviews_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="리뷰데이터", index=False)
        ws = writer.sheets["리뷰데이터"]
        for cell in ws[1]:
            cell.fill = H_FILL
            cell.font = H_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for i, col in enumerate(df.columns, 1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = COL_WIDTHS.get(col, 15)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(
                    wrap_text=(cell.column == content_col), vertical="top"
                )
        for rn in range(2, ws.max_row + 1):
            ws.row_dimensions[rn].height = 55

    # 보고서 Excel
    report_path = f"{prefix}_report.xlsx"
    with pd.ExcelWriter(report_path, engine="openpyxl") as writer:
        pd.DataFrame({"AI 분석 보고서": [report]}).to_excel(
            writer, sheet_name="AI분석보고서", index=False
        )
        ws = writer.sheets["AI분석보고서"]
        ws.column_dimensions["A"].width = 130
        ws["A1"].fill = H_FILL
        ws["A1"].font = H_FONT
        ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[2].height = max(600, len(report) // 2)

        pd.DataFrame({
            "항목": ["총 리뷰", "평균 별점", "상품명", "수집 사이트", "분석 일시"],
            "값":   [
                total, avg, product_name,
                SITE_NAMES.get(site, site),
                datetime.now().strftime("%Y-%m-%d %H:%M"),
            ],
        }).to_excel(writer, sheet_name="수집통계", index=False)
        ws2 = writer.sheets["수집통계"]
        for cell in ws2[1]:
            cell.fill = H_FILL
            cell.font = H_FONT
        ws2.column_dimensions["A"].width = 15
        ws2.column_dimensions["B"].width = 40

    print(f"[*] 리뷰 데이터  : {reviews_path}  ({total}건)")
    print(f"[*] AI 분석 보고서: {report_path}")
    return reviews_path, report_path


# ── 메인 ─────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("  리뷰 분석 프로그램")
    print("  지원 사이트: 현대리바트몰 · 오늘의집 · 한샘몰")
    print("=" * 65)

    url = input("\n상품 URL 입력:\n> ").strip()
    if not url:
        print("[!] URL을 입력해주세요.")
        sys.exit(1)

    site = detect_site(url)
    if not site:
        print("\n[지원 URL 형식]")
        print("  현대리바트몰: https://www.hyundailivart.co.kr/p/P...")
        print("  오늘의집:    https://store.ohou.se/goods/...")
        print("  한샘몰:      https://store.hanssem.com/goods/...")
        sys.exit(1)

    print(f"\n[*] 감지된 사이트: {SITE_NAMES.get(site, site)}")

    try:
        max_reviews = int(
            input("\n최대 수집 리뷰 수 (기본: 500, 전체: 0): ").strip() or "500"
        )
        if max_reviews <= 0:
            max_reviews = 99999
    except ValueError:
        max_reviews = 500

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        api_key = input("\nAnthropic API 키 입력 (sk-ant-...):\n> ").strip()
    if not api_key:
        print("[!] API 키가 없습니다. ANTHROPIC_API_KEY 환경변수를 설정하거나 직접 입력하세요.")
        sys.exit(1)

    print(f"\n[*] 리뷰 수집 시작 (최대 {max_reviews}개)")
    print("-" * 65)

    try:
        reviews, stats = CRAWLERS[site](url, max_reviews)
    except Exception as e:
        print(f"\n[!] 크롤링 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    if not reviews:
        print("\n[!] 수집된 리뷰가 없습니다.")
        sys.exit(1)

    print(f"\n[*] 총 {len(reviews)}개 리뷰 수집 완료")

    product_name = (
        next((_field(r, "상품명", "상품") for r in reviews
              if _field(r, "상품명", "상품")), None)
        or "상품"
    )

    review_text = build_review_text(reviews, stats)
    report = analyze_with_claude(review_text, product_name, api_key)

    print("-" * 65)
    reviews_path, report_path = save_results(reviews, report, site, product_name)

    print("\n" + "=" * 65)
    print("[완료]")
    print(f"  리뷰 데이터  : {reviews_path}")
    print(f"  AI 분석 보고서: {report_path}")
    print("=" * 65)


if __name__ == "__main__":
    main()

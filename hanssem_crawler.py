"""
한샘몰 상품 리뷰 크롤러
- gateway.hanssem.com API 직접 호출 (인증 불필요)
- 페이지네이션 자동 처리
"""
import re
import time
import requests


API_BASE = "https://gateway.hanssem.com/hanssem/goods-service/api/v1/goods"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Origin": "https://store.hanssem.com",
}


def extract_goods_no(url: str) -> str | None:
    """한샘몰 상품 URL에서 goodsNo 추출"""
    m = re.search(r"/goods/(\d+)", url)
    return m.group(1) if m else None


def fetch_product_name(goods_no: str) -> str:
    """상품 페이지 HTML에서 상품명 추출"""
    try:
        r = requests.get(
            f"https://store.hanssem.com/goods/{goods_no}",
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=10,
        )
        m = re.search(r'"gdsNm":"([^"]+)"', r.text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return f"한샘 상품 {goods_no}"


def fetch_all_reviews(goods_no: str, max_reviews: int = 99999) -> list[dict]:
    """한샘몰 리뷰 전체 수집"""
    session = requests.Session()
    session.headers.update({
        **HEADERS,
        "Referer": f"https://store.hanssem.com/goods/{goods_no}",
    })

    url = f"{API_BASE}/{goods_no}/evaluations"
    page = 1
    page_size = 20
    all_reviews = []
    total = None

    while True:
        params = {"page": page, "size": page_size, "sortType": "RECENT"}
        try:
            resp = session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            body = resp.json()
        except Exception as e:
            print(f"[!] API 요청 실패 (page={page}): {e}")
            break

        if body.get("code") != 200:
            print(f"[!] API 오류: {body.get('message', '')}")
            break

        data = body["data"]

        if total is None:
            total = data.get("totalElements", 0)
            total_pages = data.get("totalPages", 1)
            print(f"[*] 총 리뷰: {total}개 ({total_pages}페이지) | 최대 {min(total, max_reviews)}개 수집")

        items = data.get("content", [])
        if not items:
            break

        for item in items:
            all_reviews.append(_parse_review(item))

        collected = len(all_reviews)
        print(f"    page {page}/{data.get('totalPages', '?')} → {len(items)}개 | 누적 {collected}개")

        if collected >= max_reviews or data.get("last"):
            break

        page += 1
        time.sleep(0.3)

    return all_reviews[:max_reviews]


def _parse_review(item: dict) -> dict:
    """API 응답 아이템 → 딕셔너리"""
    # 날짜 정규화 (YYYY-MM-DD HH:MM:SS → YYYY-MM-DD)
    reg_date = str(item.get("regYmdt", ""))[:10]

    # 미디어 타입
    images = item.get("imageInfos") or []
    has_video = bool(item.get("videoUrl"))
    media_type = "영상" if has_video else ("사진" if images else "텍스트")

    # 옵션 (unitNm 정제)
    option = (item.get("unitNm") or "").replace("  /  ", " / ").strip()

    return {
        "리뷰ID":   item.get("gdsEvalNo", ""),
        "별점":     item.get("avgScore", ""),
        "품질점수": item.get("qualityScore", ""),
        "디자인점수": item.get("designScore", ""),
        "배송점수": item.get("deliveryScore", ""),
        "가격점수": item.get("priceScore", ""),
        "리뷰내용": (item.get("gdsEvalConts") or "").strip(),
        "작성자":   item.get("custId", ""),
        "작성일":   reg_date,
        "구매옵션": option,
        "미디어타입": media_type,
        "도움수":   item.get("likeCount", 0),
        "판매자답변": (item.get("replyGdsEvalConts") or "").strip(),
    }


def crawl_hanssem_reviews(url: str, max_reviews: int = 500) -> list[dict]:
    """한샘몰 URL로 리뷰 수집 (analyze.py에서 호출)"""
    goods_no = extract_goods_no(url)
    if not goods_no:
        print(f"[!] 한샘몰 상품 번호를 URL에서 추출할 수 없습니다: {url}")
        return []

    print(f"[*] 한샘몰 상품 번호: {goods_no}")

    product_name = fetch_product_name(goods_no)
    print(f"[*] 상품명: {product_name}")

    reviews = fetch_all_reviews(goods_no, max_reviews=max_reviews)

    # 상품명 각 리뷰에 삽입
    for r in reviews:
        r["상품명"] = product_name
        r["상품번호"] = goods_no

    return reviews

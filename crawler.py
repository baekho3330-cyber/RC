"""
현대리바트몰 리뷰 크롤러
- Playwright로 상품 페이지에서 vreview ID 추출
- requests로 vreview.tv API 직접 호출 (페이지네이션 처리)
"""
import re
import time
import requests
from playwright.sync_api import sync_playwright


VREVIEW_API = "https://one.vreview.tv/api/embed/v2/{vrid}/reviews/"
VREVIEW_PARAMS = {
    "ordering": "-created_at",
    "annotate_topic_slug": "true",
    "expand": "comments,created_at,helpful_count,media_contents,product,questions,rating,upload_from,user_nickname",
    "is_using_review_rating": "true",
}


def crawl_livart_reviews(product_url: str, max_reviews: int = 500) -> list[dict]:
    """
    현대리바트몰 상품 리뷰를 크롤링합니다.

    Args:
        product_url: 리바트몰 상품 URL
        max_reviews: 최대 수집 리뷰 수

    Returns:
        리뷰 데이터 딕셔너리 리스트
    """
    # 1. 상품 URL에서 product_remote_id 추출
    product_id = _extract_product_id(product_url)
    if not product_id:
        print(f"[!] 상품 ID를 URL에서 추출하지 못했습니다: {product_url}")
        return []

    print(f"[*] 상품 ID: {product_id}")

    # 2. 페이지에서 vreview ID 추출
    vrid = _extract_vrid(product_url)
    if not vrid:
        print("[!] vreview ID를 찾지 못했습니다.")
        return []

    print(f"[*] vreview ID: {vrid}")

    # 3. API로 리뷰 수집
    reviews = _fetch_all_reviews(vrid, product_id, max_reviews)
    return reviews


def _extract_product_id(url: str) -> str | None:
    """URL에서 상품 ID 추출 (예: /p/P200015474)"""
    match = re.search(r"/p/([A-Z0-9]+)", url)
    if match:
        return match.group(1)
    # 쿼리스트링 fallback
    match = re.search(r"product[_\-]?(?:id|no|num)[=:]([A-Z0-9]+)", url, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_vrid(product_url: str) -> str | None:
    """상품 페이지 HTML에서 vreview UUID 추출"""
    print("[*] 페이지 로딩 중 (vreview ID 추출)...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="ko-KR",
        )
        page = context.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        vrid = None

        def on_response(response):
            nonlocal vrid
            url = response.url
            m = re.search(
                r"vreview\.tv/[^/]+/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
                url,
            )
            if m and not vrid:
                vrid = m.group(1)

        page.on("response", on_response)

        try:
            page.goto(product_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            if not vrid:
                html = page.content()
                uuid_pattern = r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"
                # vreview 관련 UUID만
                matches = re.findall(
                    rf"(?:vrid|vreview)[^a-f0-9]*({uuid_pattern})", html, re.IGNORECASE
                )
                if matches:
                    vrid = matches[0]
                else:
                    # 전체 UUID 중 vreview 스크립트 근처 것
                    all_uuids = re.findall(uuid_pattern, html)
                    if all_uuids:
                        vrid = all_uuids[0]
        finally:
            browser.close()

    return vrid


def _fetch_all_reviews(vrid: str, product_id: str, max_reviews: int) -> list[dict]:
    """vreview API를 페이지네이션으로 호출해 전체 리뷰 수집"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.hyundailivart.co.kr/",
        "Origin": "https://www.hyundailivart.co.kr",
    })

    url = VREVIEW_API.format(vrid=vrid)
    limit = min(50, max_reviews)
    offset = 0
    all_reviews = []
    total = None

    while True:
        params = {
            **VREVIEW_PARAMS,
            "product_remote_id": product_id,
            "limit": limit,
            "offset": offset,
        }

        try:
            resp = session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[!] API 요청 실패 (offset={offset}): {e}")
            break

        if total is None:
            total = data.get("count", 0)
            print(f"[*] 총 리뷰 수: {total}개 (최대 {max_reviews}개 수집)")

        results = data.get("results", [])
        if not results:
            break

        for item in results:
            review = _parse_review(item)
            all_reviews.append(review)

        offset += limit
        collected = len(all_reviews)
        print(f"    {collected}/{min(total, max_reviews)}개 수집됨")

        if collected >= max_reviews or not data.get("next"):
            break

        time.sleep(0.5)  # API 부하 방지

    return all_reviews


def _parse_review(item: dict) -> dict:
    """API 응답 아이템을 딕셔너리로 파싱"""
    product = item.get("product") or {}
    options = item.get("selected_options") or []
    option_text = ", ".join(
        f"{o.get('name', '')}: {o.get('value', '')}" for o in options
    ).strip(", ")

    topics = item.get("topics") or []
    topic_slugs = list({t.get("slug", "") for t in topics if t.get("slug")})

    media = item.get("media_contents") or []
    has_photo = any(m.get("type") == "image" for m in media)
    has_video = any(m.get("type") == "video" for m in media)
    media_type = "영상" if has_video else ("사진" if has_photo else "텍스트")

    created_at = item.get("created_at", "")
    if created_at:
        created_at = created_at[:10]  # YYYY-MM-DD

    return {
        "리뷰ID": item.get("id", ""),
        "상품명": product.get("name", ""),
        "상품ID": product.get("remote_id", ""),
        "별점": item.get("rating", ""),
        "제목": item.get("title", ""),
        "리뷰내용": item.get("text", ""),
        "작성자": item.get("user_nickname", ""),
        "작성일": created_at,
        "구매옵션": option_text,
        "미디어타입": media_type,
        "도움수": item.get("helpful_count", 0),
        "토픽": ", ".join(topic_slugs),
    }

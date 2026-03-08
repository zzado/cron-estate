"""
동/호수 기반 매물 그룹핑
같은 물건에 대해 여러 중개사가 올린 매물을 그룹으로 묶기
"""

from dataclasses import dataclass, field

from scraper.parser import format_price


@dataclass
class ArticleGroup:
    """동일 물건 그룹"""

    group_key: str
    complex_name: str
    dong: str
    ho: str
    exclusive_area: float
    min_price: int = 0
    max_price: int = 0
    articles: list[dict] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.articles)

    @property
    def price_display(self) -> str:
        if self.min_price == self.max_price:
            return format_price(self.min_price)
        return f"{format_price(self.min_price)} ~ {format_price(self.max_price)}"

    @property
    def location_display(self) -> str:
        parts = []
        if self.dong:
            parts.append(f"{self.dong}")
        if self.ho:
            parts.append(f"{self.ho}호")
        if not parts:
            return "동/호수 미상"
        return " ".join(parts)


def group_articles(articles: list[dict], complex_name: str = "") -> list[ArticleGroup]:
    """매물 목록을 그룹별로 묶기"""
    groups: dict[str, ArticleGroup] = {}

    for article in articles:
        key = article.get("group_key", "")
        if not key:
            # 그룹 키가 없으면 매물번호로 단독 그룹
            key = f"single_{article.get('article_no', '')}"

        if key not in groups:
            groups[key] = ArticleGroup(
                group_key=key,
                complex_name=complex_name or article.get("complex_name", ""),
                dong=article.get("dong", ""),
                ho=article.get("ho", ""),
                exclusive_area=article.get("exclusive_area", 0),
                min_price=article.get("deal_price", 0),
                max_price=article.get("deal_price", 0),
                articles=[],
            )

        group = groups[key]
        group.articles.append(article)

        price = article.get("deal_price", 0)
        if price > 0:
            if group.min_price == 0 or price < group.min_price:
                group.min_price = price
            if price > group.max_price:
                group.max_price = price

    # 동, 호수 순 정렬
    sorted_groups = sorted(groups.values(), key=lambda g: (g.dong, g.ho))
    return sorted_groups

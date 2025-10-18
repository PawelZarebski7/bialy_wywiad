import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import List, Optional
import re


@dataclass
class NewsArticle:
    title: str
    url: str
    snippet: Optional[str] = None
    source: Optional[str] = None
    date: Optional[str] = None


@dataclass
class NewsData:
    company_name: str
    articles: List[NewsArticle] = field(default_factory=list)
    total_found: int = 0


class NewsCollector:
    def __init__(self, company_name: str, nip: str = None):
        self.company_name = company_name
        self.nip = nip
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

    def collect(self) -> NewsData:
        """Zbiera wiadomości o firmie"""
        try:
            articles = []

            # Wyszukaj przez DuckDuckGo News
            duckduckgo_results = self._search_duckduckgo()
            articles.extend(duckduckgo_results)

            # Usuń duplikaty po URL
            seen_urls = set()
            unique_articles = []
            for article in articles:
                if article.url not in seen_urls:
                    seen_urls.add(article.url)
                    unique_articles.append(article)

            data = NewsData(
                company_name=self.company_name,
                articles=unique_articles[:10],  # Max 10 artykułów
                total_found=len(unique_articles),
            )

            return data

        except Exception as e:
            print(f"Błąd podczas zbierania newsów: {str(e)}")
            return NewsData(company_name=self.company_name)

    def _search_duckduckgo(self) -> List[NewsArticle]:
        """Wyszukuje newsy przez DuckDuckGo"""
        try:
            articles = []

            # Zapytanie - szukamy wiadomości o firmie
            query = f'"{self.company_name}"'
            if self.nip:
                query += f" {self.nip}"
            query += " news wiadomości"

            url = "https://html.duckduckgo.com/html/"
            response = self.session.post(url, data={"q": query}, timeout=10)

            if response.status_code != 200:
                return articles

            soup = BeautifulSoup(response.text, "html.parser")
            results = soup.find_all("div", class_="result")

            # Domeny do pominięcia (katalogi firmowe, nie newsy)
            skip_domains = [
                "biznesfinder.pl",
                "panoramafirm.pl",
                "gowork.pl",
                "firmeo.pl",
                "ceidg.gov.pl",
                "facebook.com",
                "linkedin.com",
                "owg.pl",
                "infoveriti.pl",
            ]

            for result in results[:15]:
                try:
                    # Tytuł i link
                    link_tag = result.find("a", class_="result__a")
                    if not link_tag:
                        continue

                    title = link_tag.get_text(strip=True)
                    article_url = link_tag.get("href", "")

                    # Pomiń katalogi firmowe
                    if any(domain in article_url.lower() for domain in skip_domains):
                        continue

                    # Snippet
                    snippet_tag = result.find("a", class_="result__snippet")
                    snippet = snippet_tag.get_text(strip=True) if snippet_tag else None

                    # Źródło (domena)
                    source = self._extract_domain(article_url)

                    # Sprawdź czy w tytule lub snippecie jest nazwa firmy
                    text_to_check = f"{title} {snippet or ''}".lower()
                    if self.company_name.lower() in text_to_check:
                        article = NewsArticle(
                            title=title,
                            url=article_url,
                            snippet=snippet[:200] if snippet else None,
                            source=source,
                        )
                        articles.append(article)

                except Exception:
                    continue

            return articles

        except Exception as e:
            print(f"Błąd DuckDuckGo: {str(e)}")
            return []

    def _extract_domain(self, url: str) -> str:
        """Wyciąga domenę z URL"""
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            domain = parsed.netloc
            # Usuń www.
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except:
            return "Unknown"

    def _extract_date(self, text: str) -> Optional[str]:
        """Próbuje wyciągnąć datę z tekstu"""
        # Wzorce dat
        date_patterns = [
            r"\d{1,2}\.\d{1,2}\.\d{4}",  # 01.01.2024
            r"\d{4}-\d{2}-\d{2}",  # 2024-01-01
            r"\d{1,2}\s+\w+\s+\d{4}",  # 1 stycznia 2024
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)

        return None

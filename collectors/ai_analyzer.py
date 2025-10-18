import os
import json
import requests
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from bs4 import BeautifulSoup


@dataclass
class CompetitorInfo:
    name: str
    website: Optional[str] = None
    description: Optional[str] = None


@dataclass
class FinancialData:
    revenue: Optional[float] = None
    profit: Optional[float] = None
    debt: Optional[float] = None
    equity: Optional[float] = None
    financial_health: str = "unknown"  # good/warning/poor/unknown


@dataclass
class IndustryTrends:
    industry: str
    growth_rate: Optional[float] = None
    trends: List[str] = None
    opportunities: List[str] = None
    threats: List[str] = None


@dataclass
class BenchmarkResult:
    ranking: int
    total_competitors: int
    strengths_vs_competitors: List[str]
    weaknesses_vs_competitors: List[str]
    overall_score: int  # 0-100


@dataclass
class AIAnalysisResult:
    risk_score: int  # 0-100 (0 = wysokie ryzyko, 100 = niskie ryzyko)
    risk_level: str  # "NISKIE", "ŚREDNIE", "WYSOKIE"
    strengths: List[str]
    red_flags: List[str]
    competitors: List[CompetitorInfo]
    recommendation: str
    detailed_analysis: str
    analysis_date: str
    financial_data: Optional[FinancialData] = None
    industry_trends: Optional[IndustryTrends] = None
    benchmark: Optional[BenchmarkResult] = None


class AIAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.model = "gpt-4o"
        self.max_tokens = 3500
        self.usage_file = ".ai_usage.json"

    def analyze(
        self, company_name: str, nip: str, collected_data: Dict[str, Any]
    ) -> AIAnalysisResult:
        """
        Główna metoda analizy AI
        """
        # Sprawdź limit zapytań
        if not self._check_daily_limit():
            raise Exception(
                "❌ Przekroczono dzienny limit 50 zapytań AI. Spróbuj ponownie jutro."
            )

        # 1. Przygotuj dane do analizy
        analysis_prompt = self._prepare_analysis_prompt(
            company_name, nip, collected_data
        )

        # 2. Wyślij do GPT-4o
        gpt_response = self._call_openai(analysis_prompt)

        # 3. Parsuj odpowiedź
        result = self._parse_gpt_response(gpt_response, company_name)

        # 4. Wyszukaj konkurencję
        competitors = self._search_competitors(company_name, nip, collected_data)
        result.competitors = competitors

        # 5. Analiza finansowa (symulacja - w przyszłości można dodać API)
        result.financial_data = self._fetch_financial_data(nip)

        # 6. Trendy branżowe
        industry = self._extract_industry(company_name, collected_data)
        result.industry_trends = self._analyze_industry_trends(company_name, industry)

        # 7. Benchmark z konkurencją
        result.benchmark = self._benchmark_against_competitors(
            collected_data, competitors, result.risk_score
        )

        # 8. Zapisz użycie
        self._log_usage()

        return result

    def _prepare_analysis_prompt(
        self, company_name: str, nip: str, data: Dict[str, Any]
    ) -> str:
        """
        Przygotowuje prompt dla GPT-4o z wszystkimi zebranymi danymi
        """

        # Ekstrakcja danych z collectorów
        regon_data = data.get("regon")
        website_data = data.get("website")
        news_data = data.get("news")
        security_data = data.get("security")

        prompt = f"""Jesteś ekspertem od analizy ryzyka biznesowego i białego wywiadu gospodarczego.
Przeanalizuj poniższe dane o firmie i przygotuj szczegółową ocenę ryzyka współpracy.

# DANE FIRMY

## Podstawowe informacje
- Nazwa: {company_name}
- NIP: {nip}
"""

        # Dane z Białej Listy VAT
        if regon_data:
            prompt += f"""
## Dane rejestrowe (Biała Lista VAT)
- Status VAT: {regon_data.vat_status or "Brak danych"}
- REGON: {regon_data.regon or "Brak danych"}
- KRS: {regon_data.krs or "Brak danych"}
- Adres: {regon_data.address or "Brak danych"}
- Data rejestracji: {regon_data.registration_date or "Brak danych"}
- Rachunki bankowe: {len(regon_data.bank_accounts) if regon_data.bank_accounts else 0} rachunków na białej liście
"""

        # Dane ze strony WWW
        if website_data:
            prompt += f"""
## Strona internetowa
- URL: {website_data.url}
- Tytuł: {website_data.title or "Brak"}
- Opis: {website_data.description or "Brak"}
- Email: {", ".join(website_data.emails[:3]) if website_data.emails else "Nie znaleziono"}
- Telefon: {", ".join(website_data.phones[:2]) if website_data.phones else "Nie znaleziono"}
- Social media: {", ".join(website_data.social_media.keys()) if website_data.social_media else "Brak"}
- CMS: {website_data.cms or "Nieznany"}
- Technologie: {", ".join(website_data.technologies) if website_data.technologies else "Brak danych"}
- O firmie: {website_data.about[:300] if website_data.about else "Brak informacji"}
- Usługi ({len(website_data.services)}): {", ".join(website_data.services[:5]) if website_data.services else "Brak danych"}
"""
        else:
            prompt += "\n## Strona internetowa\n- ⚠️ NIE ZNALEZIONO STRONY WWW\n"

        # Bezpieczeństwo
        if security_data:
            prompt += f"""
## Bezpieczeństwo strony WWW
- Ocena bezpieczeństwa: {security_data.security_score}/100
- SSL/HTTPS: {"Aktywny" if security_data.ssl_info.has_ssl else "❌ BRAK"}
- Wydawca SSL: {security_data.ssl_info.issuer or "Brak"}
- Wygasa za: {security_data.ssl_info.days_to_expire or "Brak danych"} dni
- Nagłówki bezpieczeństwa:
  * HSTS: {"✅" if security_data.security_headers.strict_transport_security else "❌"}
  * CSP: {"✅" if security_data.security_headers.content_security_policy else "❌"}
  * X-Frame-Options: {"✅" if security_data.security_headers.x_frame_options else "❌"}
- Podatności: {len(security_data.vulnerabilities) if security_data.vulnerabilities else 0}
{("- Wykryte podatności: " + ", ".join(security_data.vulnerabilities[:3])) if security_data.vulnerabilities else ""}
"""

        # Wiadomości
        if news_data and news_data.articles:
            prompt += f"""
## Wiadomości i media
- Znaleziono artykułów: {news_data.total_found}
- Ostatnie wiadomości:
"""
            for article in news_data.articles[:5]:
                prompt += f"  * {article.title} ({article.source})\n"
                if article.snippet:
                    prompt += f"    {article.snippet[:150]}\n"
        else:
            prompt += "\n## Wiadomości i media\n- Nie znaleziono wiadomości o firmie\n"

        # Instrukcje analizy
        prompt += """

# ZADANIE

Przeanalizuj powyższe dane i dostarcz szczegółową ocenę ryzyka biznesowego w formacie JSON:

{
  "risk_score": <liczba 0-100, gdzie 100 = najniższe ryzyko, 0 = najwyższe>,
  "risk_level": "<NISKIE|ŚREDNIE|WYSOKIE>",
  "strengths": [
    "Lista mocnych stron firmy (3-8 punktów)",
    "Pozytywne aspekty świadczące o wiarygodności"
  ],
  "red_flags": [
    "Lista ostrzeżeń i potencjalnych problemów (0-10 punktów)",
    "Każda niepokojąca obserwacja"
  ],
  "recommendation": "Krótkie podsumowanie (2-4 zdania) - czy warto współpracować i dlaczego",
  "detailed_analysis": "Szczegółowa analiza (5-10 zdań) obejmująca: obecność online, bezpieczeństwo, reputację, widoczność w mediach, ogólną ocenę wiarygodności"
}

# KRYTERIA OCENY

**Pozytywne sygnały (+):**
- Aktywny status VAT i rachunki na białej liście
- Profesjonalna strona WWW z pełnymi danymi kontaktowymi
- Wysokie bezpieczeństwo strony (HTTPS, nagłówki)
- Obecność w social media
- Pozytywne wiadomości w mediach
- Długi okres działalności (stara data rejestracji)
- Pełne informacje o usługach/produktach

**Red flags (-):**
- Brak strony WWW lub bardzo podstawowa strona
- Nieczynny VAT lub brak na białej liście
- Brak HTTPS/SSL
- Niski wynik bezpieczeństwa (<60/100)
- Podatności bezpieczeństwa
- Brak danych kontaktowych
- Negatywne wiadomości
- Brak obecności w internecie
- Bardzo młoda firma (rejestracja <6 miesięcy temu)

Odpowiedz TYLKO kodem JSON, bez dodatkowych komentarzy.
"""

        return prompt

    def _call_openai(self, prompt: str) -> str:
        """
        Wysyła zapytanie do OpenAI API
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Jesteś ekspertem od analizy ryzyka biznesowego. Odpowiadasz TYLKO w formacie JSON, po polsku.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": self.max_tokens,
            }

            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )

            response.raise_for_status()
            result = response.json()

            return result["choices"][0]["message"]["content"]

        except requests.exceptions.RequestException as e:
            raise Exception(f"Błąd komunikacji z OpenAI: {str(e)}")
        except KeyError as e:
            raise Exception(f"Nieprawidłowa odpowiedź z OpenAI: {str(e)}")

    def _parse_gpt_response(
        self, gpt_response: str, company_name: str
    ) -> AIAnalysisResult:
        """
        Parsuje odpowiedź JSON z GPT-4o
        """
        try:
            # Usuń markdown formatting jeśli istnieje
            gpt_response = gpt_response.strip()
            if gpt_response.startswith("```json"):
                gpt_response = gpt_response[7:]
            if gpt_response.startswith("```"):
                gpt_response = gpt_response[3:]
            if gpt_response.endswith("```"):
                gpt_response = gpt_response[:-3]

            data = json.loads(gpt_response.strip())

            # Walidacja risk_level
            risk_level = data.get("risk_level", "ŚREDNIE").upper()
            if risk_level not in ["NISKIE", "ŚREDNIE", "WYSOKIE"]:
                risk_level = "ŚREDNIE"

            return AIAnalysisResult(
                risk_score=int(data.get("risk_score", 50)),
                risk_level=risk_level,
                strengths=data.get("strengths", []),
                red_flags=data.get("red_flags", []),
                competitors=[],  # Wypełnione później
                recommendation=data.get("recommendation", "Brak rekomendacji"),
                detailed_analysis=data.get(
                    "detailed_analysis", "Brak szczegółowej analizy"
                ),
                analysis_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )

        except json.JSONDecodeError as e:
            raise Exception(
                f"Błąd parsowania odpowiedzi AI: {str(e)}\nOdpowiedź: {gpt_response[:200]}"
            )
        except Exception as e:
            raise Exception(f"Błąd przetwarzania odpowiedzi AI: {str(e)}")

    def _search_competitors(self, company_name: str, nip: str, collected_data: Dict[str, Any]) -> List[CompetitorInfo]:
        """
        Wyszukuje konkurencję firmy przez DuckDuckGo z lepszym filtrowaniem
        """
        try:
            competitors = []

            # Wyciągnij branżę/keywords z nazwy firmy
            clean_name = company_name.lower()
            remove_words = [
                "sp. z o.o.",
                "sp. z o. o.",
                "spółka z ograniczoną odpowiedzialnością",
                "s.a.",
                "spółka",
                "firma",
                "przedsiębiorstwo",
                "polska",
                "polish",
            ]
            for word in remove_words:
                clean_name = clean_name.replace(word, "")
            clean_name = clean_name.strip()

            # Normalizuj nazwę firmy do porównania (bez znaków specjalnych)
            normalized_company_name = "".join(
                e.lower() for e in company_name if e.isalnum() or e.isspace()
            ).strip()

            # Wyciągnij główne słowa kluczowe (nie stop words)
            stop_words = {"sp", "z", "o", "o", "s", "a", "i", "w", "na", "do", "dla", "bis"}
            company_key_words = [
                w
                for w in normalized_company_name.split()
                if w not in stop_words and len(w) > 3
            ]

            # INTELIGENTNE ZAPYTANIE - sprawdź branżę
            website_data = collected_data.get("website")
            services_text = ""
            if website_data and website_data.services:
                services_text = " ".join(website_data.services).lower()
            
            # Określ query na podstawie branży
            if any(word in clean_name for word in ["oze", "wiatr", "solar", "fotowolta", "energia"]) or \
               any(word in services_text for word in ["fotowoltaika", "panele słoneczne", "pompa ciepła", "oze"]):
                query = "firmy fotowoltaika instalacje OZE Polska"
            elif any(word in clean_name for word in ["wywiad", "informacja", "data"]) or \
                 any(word in services_text for word in ["wywiad", "informacja biznesowa", "due diligence"]):
                query = "firmy wywiad gospodarczy informacja biznesowa Polska"
            elif any(word in clean_name for word in ["tech", "it", "soft"]) or \
                 any(word in services_text for word in ["software", "it", "technolog"]):
                query = "firmy IT software development Polska"
            else:
                query = f"konkurenci {clean_name} Polska"

            session = requests.Session()
            session.headers.update(
                {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )

            url = "https://html.duckduckgo.com/html/"
            response = session.post(url, data={"q": query}, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                results = soup.find_all("a", class_="result__a", limit=20)

                skip_domains = [
                    "facebook.com",
                    "linkedin.com",
                    "wikipedia.org",
                    "biznesfinder.pl",
                    "panoramafirm.pl",
                    "gowork.pl",
                    "rejestr.io",
                    "krs-online.com.pl",
                    "krs.ms.gov.pl",
                    "ceidg.gov.pl",
                ]

                for result in results:
                    href = result.get("href", "")
                    title = result.get_text(strip=True)

                    # Pomiń katalogi
                    if any(domain in href.lower() for domain in skip_domains):
                        continue

                    # Normalizuj tytuł
                    normalized_title = "".join(
                        e.lower() for e in title if e.isalnum() or e.isspace()
                    ).strip()

                    # SUPER FILTR 1: Pomiń jeśli pełna nazwa firmy jest w tytule
                    if normalized_company_name in normalized_title:
                        continue

                    # SUPER FILTR 2: Sprawdź czy więcej niż 60% głównych słów kluczowych pasuje
                    if company_key_words:
                        title_words = set(normalized_title.split())
                        matching_words = [
                            w for w in company_key_words if w in title_words
                        ]
                        similarity = len(matching_words) / len(company_key_words) if company_key_words else 0

                        if similarity > 0.6:  # Jeśli > 60% słów pasuje, to pewnie ta sama firma
                            continue

                    # SUPER FILTR 3: Sprawdź czy URL zawiera nazwę firmy
                    if any(
                        word in href.lower()
                        for word in company_key_words
                        if len(word) > 4
                    ):
                        continue

                    snippet_tag = result.find_next("a", class_="result__snippet")
                    description = (
                        snippet_tag.get_text(strip=True)[:200] if snippet_tag else None
                    )

                    competitor = CompetitorInfo(
                        name=title, website=href, description=description
                    )
                    competitors.append(competitor)

                    if len(competitors) >= 5:
                        break

            return competitors

        except Exception as e:
            print(f"Błąd wyszukiwania konkurencji: {str(e)}")
            return []

    def _fetch_financial_data(self, nip: str) -> FinancialData:
        """
        Pobiera dane finansowe firmy (symulacja - w przyszłości można dodać API do KRS/Emis)
        """
        return FinancialData(
            revenue=None,
            profit=None,
            debt=None,
            equity=None,
            financial_health="unknown",
        )

    def _extract_industry(self, company_name: str, data: Dict[str, Any]) -> str:
        """
        Wyciąga branżę firmy z nazwy i danych - ULEPSZONA WERSJA
        """
        website_data = data.get("website")

        # Sprawdź usługi ze strony WWW
        if website_data and website_data.services:
            services_text = " ".join(website_data.services).lower()

            # OZE i energia odnawialna
            if any(
                word in services_text
                for word in [
                    "fotowoltaika", "fotowoltaik", "oze", "fotowolta", 
                    "panele słoneczne", "panel słoneczny", "pompa ciepła", 
                    "pompy ciepła", "energia odnawialna", "solarne", "solar",
                    "instalacje elektryczne", "montaż paneli"
                ]
            ):
                return "OZE i energia odnawialna"
            
            # IT i technologie
            if any(
                word in services_text
                for word in [
                    "it", "software", "technolog", "digital", "wywiad",
                    "data", "informacja", "programowanie", "aplikacje"
                ]
            ):
                return "IT i technologie"
            
            # Budownictwo
            elif any(
                word in services_text for word in ["budow", "remont", "konstrukc"]
            ):
                return "Budownictwo"
            
            # Handel
            elif any(
                word in services_text for word in ["handel", "sprzedaż", "dystrybucja"]
            ):
                return "Handel"
            
            # Consulting
            elif any(
                word in services_text
                for word in ["konsult", "doradztwo", "audyt", "wywiad gospodarczy"]
            ):
                return "Consulting i doradztwo"
            
            # Produkcja
            elif any(word in services_text for word in ["produkcja", "wytwarzanie"]):
                return "Produkcja"

        # Sprawdź nazwę firmy
        name_lower = company_name.lower()
        
        # OZE
        if any(
            word in name_lower 
            for word in ["eko-wiatr", "eko wiatr", "oze", "fotowolta", "solar", 
                        "energia", "wiatr", "sun", "eco"]
        ):
            return "OZE i energia odnawialna"
        
        # IT
        if any(
            word in name_lower 
            for word in ["tech", "soft", "digital", "it", "data", "info"]
        ):
            return "IT i technologie"
        
        # Budownictwo
        elif any(word in name_lower for word in ["bud", "construction", "dom"]):
            return "Budownictwo"
        
        # Wywiad
        elif any(word in name_lower for word in ["wywiad", "intelligence"]):
            return "Wywiad gospodarczy i informacja biznesowa"

        return "Usługi biznesowe"

    def _analyze_industry_trends(
        self, company_name: str, industry: str
    ) -> IndustryTrends:
        """
        Analizuje trendy w branży firmy używając GPT-4o
        """
        try:
            prompt = f"""Jesteś ekspertem branżowym. Przeanalizuj aktualne trendy w branży: {industry} w Polsce w 2025 roku.

Zwróć odpowiedź w formacie JSON:
{{
  "growth_rate": <szacowany wzrost % rocznie lub null>,
  "trends": ["Lista 3-5 kluczowych trendów"],
  "opportunities": ["Lista 2-3 szans dla firm"],
  "threats": ["Lista 2-3 zagrożeń"]
}}

Odpowiedz TYLKO kodem JSON."""

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }

            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Jesteś ekspertem od trendów branżowych. Odpowiadasz w JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 1000,
            }

            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()

                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]

                data = json.loads(content.strip())

                return IndustryTrends(
                    industry=industry,
                    growth_rate=data.get("growth_rate"),
                    trends=data.get("trends", []),
                    opportunities=data.get("opportunities", []),
                    threats=data.get("threats", []),
                )

        except Exception as e:
            print(f"Błąd analizy trendów: {str(e)}")

        return IndustryTrends(
            industry=industry, trends=[], opportunities=[], threats=[]
        )

    def _benchmark_against_competitors(
        self,
        company_data: Dict[str, Any],
        competitors: List[CompetitorInfo],
        risk_score: int,
    ) -> BenchmarkResult:
        """
        Porównuje firmę z konkurencją
        """
        try:
            strengths = []
            weaknesses = []

            website_data = company_data.get("website")
            if website_data:
                if website_data.social_media and len(website_data.social_media) >= 2:
                    strengths.append("Dobra obecność w social media")
                elif not website_data.social_media:
                    weaknesses.append("Brak obecności w social media")

                if website_data.emails and website_data.phones:
                    strengths.append("Pełne dane kontaktowe")
                else:
                    weaknesses.append("Niekompletne dane kontaktowe")

            security_data = company_data.get("security")
            if security_data:
                if security_data.security_score >= 70:
                    strengths.append("Dobre zabezpieczenie strony")
                elif security_data.security_score < 50:
                    weaknesses.append("Słabe zabezpieczenie strony")

            total = len(competitors) + 1
            if risk_score >= 75:
                ranking = 1
            elif risk_score >= 60:
                ranking = min(2, total)
            elif risk_score >= 40:
                ranking = min(total // 2, total)
            else:
                ranking = total

            overall_score = risk_score

            return BenchmarkResult(
                ranking=ranking,
                total_competitors=total,
                strengths_vs_competitors=strengths
                if strengths
                else ["Brak wystarczających danych do porównania"],
                weaknesses_vs_competitors=weaknesses
                if weaknesses
                else ["Brak wystarczających danych do porównania"],
                overall_score=overall_score,
            )

        except Exception as e:
            print(f"Błąd benchmarku: {str(e)}")
            return BenchmarkResult(
                ranking=1,
                total_competitors=len(competitors) + 1,
                strengths_vs_competitors=["Brak danych"],
                weaknesses_vs_competitors=["Brak danych"],
                overall_score=50,
            )

    def _check_daily_limit(self) -> bool:
        """
        Sprawdza czy nie przekroczono dziennego limitu 20 zapytań
        """
        try:
            if not os.path.exists(self.usage_file):
                return True

            with open(self.usage_file, "r") as f:
                usage_data = json.load(f)

            today = datetime.now().strftime("%Y-%m-%d")

            if today not in usage_data:
                return True

            return usage_data[today] < 50

        except Exception as e:
            print(f"Błąd sprawdzania limitu: {str(e)}")
            return True

    def _log_usage(self):
        """
        Zapisuje użycie API (limit 50/dzień)
        """
        try:
            usage_data = {}

            if os.path.exists(self.usage_file):
                with open(self.usage_file, "r") as f:
                    usage_data = json.load(f)

            today = datetime.now().strftime("%Y-%m-%d")

            if today in usage_data:
                usage_data[today] += 1
            else:
                usage_data[today] = 1

            cutoff_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            usage_data = {k: v for k, v in usage_data.items() if k >= cutoff_date}

            with open(self.usage_file, "w") as f:
                json.dump(usage_data, f, indent=2)

        except Exception as e:
            print(f"Błąd zapisu użycia: {str(e)}")

    def get_remaining_queries(self) -> int:
        """
        Zwraca liczbę pozostałych zapytań na dziś
        """
        try:
            if not os.path.exists(self.usage_file):
                return 50

            with open(self.usage_file, "r") as f:
                usage_data = json.load(f)

            today = datetime.now().strftime("%Y-%m-%d")
            used = usage_data.get(today, 0)

            return max(0, 50 - used)

        except:
            return 50
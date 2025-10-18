import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import re


@dataclass
class Review:
    author: str
    rating: float
    text: Optional[str] = None
    date: Optional[str] = None


@dataclass
class GoogleMapsData:
    company_name: str
    found: bool = False
    rating: Optional[float] = None
    total_reviews: int = 0
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    opening_hours: Dict[str, str] = field(default_factory=dict)
    categories: List[str] = field(default_factory=list)
    reviews: List[Review] = field(default_factory=list)
    place_id: Optional[str] = None
    maps_url: Optional[str] = None


class GoogleMapsCollector:
    def __init__(self, company_name: str, address: str = None):
        self.company_name = company_name
        self.address = address
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )

    def collect(self) -> GoogleMapsData:
        """Zbiera dane z Google Maps"""
        try:
            data = GoogleMapsData(company_name=self.company_name)

            # Wyszukaj firmę w Google Maps
            search_query = self.company_name
            if self.address:
                # Wyciągnij miasto z adresu
                city = self._extract_city(self.address)
                if city:
                    search_query += f" {city}"

            # Używamy wyszukiwania do znalezienia miejsca
            maps_url = self._search_google_maps(search_query)

            if not maps_url:
                return data

            data.found = True
            data.maps_url = maps_url

            # Uwaga: Google Maps blokuje scraping, więc zwracamy tylko link
            # Użytkownik może kliknąć i zobaczyć szczegóły
            # W przyszłości można dodać Google Places API z kluczem

            return data

        except Exception as e:
            print(f"Błąd Google Maps: {str(e)}")
            return GoogleMapsData(company_name=self.company_name)

    def _extract_city(self, address: str) -> Optional[str]:
        """Wyciąga miasto z adresu"""
        try:
            # Format: "ULICA NR, KOD MIASTO"
            parts = address.split(",")
            if len(parts) >= 2:
                # Ostatnia część zawiera kod i miasto
                last_part = parts[-1].strip()
                # Usuń kod pocztowy
                city = re.sub(r"\d{2}-\d{3}", "", last_part).strip()
                return city
        except:
            pass
        return None

    def _search_google_maps(self, query: str) -> Optional[str]:
        """Wyszukuje firmę w Google Maps przez DuckDuckGo"""
        try:
            # Wyszukaj przez DuckDuckGo
            search_url = "https://html.duckduckgo.com/html/"
            search_query = f"{query} google maps miejsce"

            response = self.session.post(
                search_url, data={"q": search_query}, timeout=10
            )

            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # Szukaj linków do Google Maps
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")

                # Sprawdź czy to link do Google Maps
                if "google.com/maps" in href or "maps.google.com" in href:
                    # Usuń parametry DuckDuckGo
                    if "/url?q=" in href:
                        clean_url = href.split("/url?q=")[1].split("&")[0]
                        return clean_url
                    return href

                # Czasem DuckDuckGo zwraca bezpośredni link
                if "maps" in href and "place" in href:
                    return href

            # Próba 2: Wyszukaj bezpośrednio przez Google (alternatywny sposób)
            google_search = (
                f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
            )
            return google_search

        except Exception as e:
            print(f"Błąd wyszukiwania Maps: {str(e)}")
            # Fallback - zwróć generyczny link wyszukiwania
            return f"https://www.google.com/maps/search/{query.replace(' ', '+')}"

    def _extract_place_details(self, url: str, data: GoogleMapsData):
        """Wyciąga szczegóły miejsca z Google Maps"""
        try:
            response = self.session.get(url, timeout=15)

            if response.status_code != 200:
                return

            soup = BeautifulSoup(response.text, "html.parser")
            text = response.text

            # Ocena - szukaj wzorców typu "4.5" lub "4,5"
            rating_pattern = r'"aggregateRating".*?"ratingValue":"?(\d+\.?\d*)"?'
            rating_match = re.search(rating_pattern, text)
            if rating_match:
                try:
                    data.rating = float(rating_match.group(1))
                except:
                    pass

            # Liczba opinii
            reviews_pattern = r'"ratingCount":"?(\d+)"?'
            reviews_match = re.search(reviews_pattern, text)
            if reviews_match:
                try:
                    data.total_reviews = int(reviews_match.group(1))
                except:
                    pass

            # Adres
            address_pattern = r'"streetAddress":"([^"]+)"'
            address_match = re.search(address_pattern, text)
            if address_match:
                data.address = address_match.group(1)

            # Telefon
            phone_pattern = r'"telephone":"([^"]+)"'
            phone_match = re.search(phone_pattern, text)
            if phone_match:
                data.phone = phone_match.group(1)

            # Strona WWW
            website_pattern = r'"url":"(https?://[^"]+)"'
            website_matches = re.findall(website_pattern, text)
            for url_match in website_matches:
                if "google.com" not in url_match and "maps" not in url_match:
                    data.website = url_match
                    break

            # Kategorie
            category_pattern = (
                r"\"@type\":\"LocalBusiness\".*?\"additionalType\":\"([^\"]+)\""
            )
            category_matches = re.findall(category_pattern, text)
            if category_matches:
                data.categories = category_matches[:5]

            # Godziny otwarcia - podstawowa próba wyciągnięcia
            hours_patterns = [
                r"\"openingHours\":\"([^\"]+)\"",
                r"(poniedziałek|wtorek|środa|czwartek|piątek|sobota|niedziela)[:\s]*(\d{1,2}:\d{2}[\s-]*\d{1,2}:\d{2})",
            ]

            for pattern in hours_patterns:
                hours_matches = re.findall(pattern, text, re.IGNORECASE)
                if hours_matches:
                    for match in hours_matches[:7]:
                        if isinstance(match, tuple):
                            day, hours = match
                            data.opening_hours[day.capitalize()] = hours
                        else:
                            # Format z JSON
                            try:
                                days = [
                                    "Poniedziałek",
                                    "Wtorek",
                                    "Środa",
                                    "Czwartek",
                                    "Piątek",
                                    "Sobota",
                                    "Niedziela",
                                ]
                                hours_list = match.split(",")
                                for i, hours in enumerate(hours_list[:7]):
                                    if i < len(days):
                                        data.opening_hours[days[i]] = hours.strip()
                            except:
                                pass
                    break

            # Opinie - podstawowe wyciąganie z treści
            review_pattern = r"\"author\":\"([^\"]+)\".*?\"ratingValue\":\"?(\d+\.?\d*)\"?.*?\"reviewBody\":\"([^\"]+)\""
            review_matches = re.findall(review_pattern, text)

            for match in review_matches[:5]:  # Max 5 opinii
                try:
                    author, rating, review_text = match
                    review = Review(
                        author=author,
                        rating=float(rating),
                        text=review_text[:200],  # Max 200 znaków
                    )
                    data.reviews.append(review)
                except:
                    continue

        except Exception as e:
            print(f"Błąd wyciągania szczegółów: {str(e)}")

    def _parse_opening_hours(self, hours_text: str) -> Dict[str, str]:
        """Parsuje godziny otwarcia"""
        hours_dict = {}

        try:
            # Różne formaty godzin
            patterns = [
                r"(pn|wt|śr|cz|pt|sb|nd)[:\s]*(\d{1,2}:\d{2}[\s-]*\d{1,2}:\d{2})",
                r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)[:\s]*(\d{1,2}:\d{2}[\s-]*\d{1,2}:\d{2})",
            ]

            for pattern in patterns:
                matches = re.findall(pattern, hours_text.lower())
                for day, hours in matches:
                    hours_dict[day] = hours

        except Exception as e:
            print(f"Błąd parsowania godzin: {str(e)}")

        return hours_dict

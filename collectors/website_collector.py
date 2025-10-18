import requests
import re
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import List, Optional, Dict


@dataclass
class WebsiteData:
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    addresses: List[str] = field(default_factory=list)
    social_media: Dict[str, str] = field(default_factory=dict)
    services: List[str] = field(default_factory=list)
    about: Optional[str] = None
    cms: Optional[str] = None
    technologies: List[str] = field(default_factory=list)


class WebsiteCollector:
    def __init__(self, url: str):
        self.url = url if url.startswith("http") else f"https://{url}"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    def collect(self) -> WebsiteData:
        try:
            response = self.session.get(self.url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            text_content = soup.get_text(separator=" ", strip=True)

            data = WebsiteData(url=self.url)

            # Podstawowe info
            data.title = self._extract_title(soup)
            data.description = self._extract_description(soup)

            # Kontakt
            data.emails = self._extract_emails(text_content)
            data.phones = self._extract_phones(text_content)
            data.addresses = self._extract_addresses(text_content)

            # Social media
            data.social_media = self._extract_social_media(soup)

            # Opis firmy
            data.about = self._extract_about(soup, text_content)

            # Usługi
            data.services = self._extract_services(soup, text_content)

            # Info techniczne
            data.cms = self._detect_cms(soup, response)
            data.technologies = self._detect_technologies(soup)

            return data

        except Exception as e:
            print(f"Błąd podczas pobierania strony: {str(e)}")
            return WebsiteData(url=self.url)

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        if soup.title:
            return soup.title.string.strip() if soup.title.string else None
        return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            return meta_desc.get("content", "").strip()
        return None

    def _extract_emails(self, text: str) -> List[str]:
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        emails = re.findall(email_pattern, text)

        # Filtruj przykładowe emaile
        filtered = [
            e
            for e in emails
            if not any(
                skip in e.lower() for skip in ["example.com", "test.com", "domain.com"]
            )
        ]
        return list(set(filtered))[:10]

    def _extract_phones(self, text: str) -> List[str]:
        phone_patterns = [
            r"\+48\s?\d{3}\s?\d{3}\s?\d{3}",
            r"\d{3}[-\s]?\d{3}[-\s]?\d{3}",
            r"\d{2}[-\s]?\d{3}[-\s]?\d{2}[-\s]?\d{2}",
        ]
        phones = []
        for pattern in phone_patterns:
            found = re.findall(pattern, text)
            phones.extend(found)

        # Filtruj numery które wyglądają jak NIP/REGON (9-10 cyfr bez formatowania)
        filtered_phones = []
        for phone in phones:
            digits_only = re.sub(r"[^\d]", "", phone)
            # Pomiń jeśli to wygląda jak NIP (10 cyfr) lub REGON (9 lub 14 cyfr)
            if len(digits_only) in [9, 10, 14]:
                # Sprawdź czy jest formatowany (spacje/myślniki) - wtedy prawdopodobnie telefon
                if "-" in phone or " " in phone:
                    filtered_phones.append(phone)
                # Jeśli brak formatowania, pomiń (to pewnie NIP/REGON)
            else:
                filtered_phones.append(phone)

        # Zwróć tylko pierwszy znaleziony telefon
        return list(set(filtered_phones))[:1]

    def _extract_addresses(self, text: str) -> List[str]:
        address_patterns = [
            r"ul\.\s+[A-ZŁŚŹĆĄĘÓ][a-złśźćąęó]+\s+\d+[a-z]?\s*,?\s*\d{2}-\d{3}\s+[A-ZŁŚŹĆĄĘÓ][a-złśźćąęó]+",
            r"[A-ZŁŚŹĆĄĘÓ][a-złśźćąęó]+\s+\d+[a-z]?\s*,?\s*\d{2}-\d{3}\s+[A-ZŁŚŹĆĄĘÓ][a-złśźćąęó]+",
        ]
        addresses = []
        for pattern in address_patterns:
            addresses.extend(re.findall(pattern, text))
        return list(set(addresses))[:5]

    def _extract_social_media(self, soup: BeautifulSoup) -> Dict[str, str]:
        social = {}
        platforms = {
            "facebook": "facebook.com",
            "linkedin": "linkedin.com",
            "twitter": "twitter.com",
            "instagram": "instagram.com",
            "youtube": "youtube.com",
        }

        links = soup.find_all("a", href=True)
        for link in links:
            href = link["href"].lower()
            for platform, domain in platforms.items():
                if domain in href and platform not in social:
                    social[platform] = link["href"]

        return social

    def _extract_about(self, soup: BeautifulSoup, text: str) -> Optional[str]:
        about_keywords = ["o nas", "o firmie", "kim jesteśmy", "about us"]

        # Szukaj w nagłówkach
        headers = soup.find_all(["h1", "h2", "h3", "h4"])
        for header in headers:
            if any(keyword in header.get_text().lower() for keyword in about_keywords):
                next_elements = header.find_next_siblings(["p", "div"], limit=2)
                desc = " ".join([elem.get_text(strip=True) for elem in next_elements])
                if len(desc) > 50:
                    return desc[:500]

        # Fallback - meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            return meta_desc["content"]

        return None

    def _extract_services(self, soup: BeautifulSoup, text: str) -> List[str]:
        services = []
        service_keywords = [
            "usługi",
            "oferta",
            "nasze usługi",
            "co oferujemy",
            "zakres",
            "specjalizujemy",
        ]

        # Szukaj w nagłówkach
        headers = soup.find_all(["h2", "h3", "h4"])
        for header in headers:
            header_text = header.get_text().lower()
            if any(keyword in header_text for keyword in service_keywords):
                # Pobierz listę
                next_list = header.find_next(["ul", "ol"])
                if next_list:
                    items = next_list.find_all("li")
                    for item in items[:15]:
                        service_text = item.get_text(strip=True)
                        # Pomiń nawigację (krókie teksty do 20 znaków)
                        if len(service_text) > 20:
                            services.append(service_text)
                    if services:
                        break

                # Jeśli nie ma listy, pobierz paragrafy
                if not services:
                    next_paragraphs = header.find_next_siblings(["p", "div"], limit=5)
                    for para in next_paragraphs:
                        para_text = para.get_text(strip=True)
                        if len(para_text) > 30 and len(para_text) < 300:
                            services.append(para_text)

        # Jeśli nic nie znaleziono w nagłówkach, szukaj w całym tekście
        if not services:
            for keyword in service_keywords:
                if keyword in text.lower():
                    idx = text.lower().find(keyword)
                    # Pobierz fragment tekstu po słowie kluczowym
                    snippet = text[idx : idx + 500]
                    # Podziel na zdania
                    sentences = snippet.split(".")
                    for sentence in sentences[
                        1:4
                    ]:  # Pomiń pierwsze zdanie (zawiera keyword)
                        sentence = sentence.strip()
                        if len(sentence) > 30:
                            services.append(sentence)
                    if services:
                        break

        return services[:10]  # Max 10 usług

    def _detect_cms(self, soup: BeautifulSoup, response) -> Optional[str]:
        html_text = str(soup).lower()

        cms_signatures = {
            "WordPress": ["wp-content", "wp-includes"],
            "Joomla": ["joomla", "com_content"],
            "Drupal": ["drupal", "sites/all"],
            "PrestaShop": ["prestashop", "ps_"],
        }

        for cms, signatures in cms_signatures.items():
            if any(sig in html_text for sig in signatures):
                return cms

        return None

    def _detect_technologies(self, soup: BeautifulSoup) -> List[str]:
        technologies = []

        script_tags = soup.find_all("script", src=True)
        tech_signatures = {
            "jQuery": "jquery",
            "React": "react",
            "Vue": "vue",
            "Bootstrap": "bootstrap",
        }

        for script in script_tags:
            src = script["src"].lower()
            for tech_name, signature in tech_signatures.items():
                if signature in src and tech_name not in technologies:
                    technologies.append(tech_name)

        return technologies

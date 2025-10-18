import subprocess
import re
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
from urllib.parse import urlparse


@dataclass
class DomainData:
    domain: str
    found: bool = False
    registrar: Optional[str] = None
    creation_date: Optional[str] = None
    expiration_date: Optional[str] = None
    updated_date: Optional[str] = None
    age_days: Optional[int] = None
    age_years: Optional[float] = None
    owner: Optional[str] = None
    status: List[str] = None
    name_servers: List[str] = None

    def __post_init__(self):
        if self.status is None:
            self.status = []
        if self.name_servers is None:
            self.name_servers = []


class DomainCollector:
    def __init__(self, url: str):
        self.url = url
        self.domain = self._extract_domain(url)

    def collect(self) -> DomainData:
        """Zbiera informacje WHOIS o domenie"""
        try:
            data = DomainData(domain=self.domain)

            if not self.domain:
                return data

            # Próba 1: Użyj biblioteki whois
            try:
                import whois

                w = whois.whois(self.domain)
                return self._parse_whois_library(w, data)
            except ImportError:
                # Próba 2: Użyj systemowego whois
                return self._parse_whois_subprocess(data)
            except Exception as e:
                print(f"Błąd biblioteki whois: {str(e)}")
                # Próba 2: Użyj systemowego whois
                return self._parse_whois_subprocess(data)

        except Exception as e:
            print(f"Błąd Domain Collector: {str(e)}")
            return DomainData(domain=self.domain)

    def _parse_whois_library(self, w, data: DomainData) -> DomainData:
        """Parsuje dane z biblioteki whois"""
        data.found = True

        # Rejestrator
        if hasattr(w, "registrar") and w.registrar:
            data.registrar = (
                w.registrar if isinstance(w.registrar, str) else w.registrar[0]
            )

        # Daty
        if hasattr(w, "creation_date") and w.creation_date:
            creation = w.creation_date
            if isinstance(creation, list):
                creation = creation[0]
            if isinstance(creation, datetime):
                data.creation_date = creation.strftime("%Y-%m-%d")
                age = datetime.now() - creation
                data.age_days = age.days
                data.age_years = round(age.days / 365.25, 1)

        if hasattr(w, "expiration_date") and w.expiration_date:
            expiration = w.expiration_date
            if isinstance(expiration, list):
                expiration = expiration[0]
            if isinstance(expiration, datetime):
                data.expiration_date = expiration.strftime("%Y-%m-%d")

        # Właściciel
        if hasattr(w, "org") and w.org:
            data.owner = w.org if isinstance(w.org, str) else w.org[0]

        # Status
        if hasattr(w, "status") and w.status:
            if isinstance(w.status, list):
                data.status = w.status[:3]
            else:
                data.status = [w.status]

        # Name servers
        if hasattr(w, "name_servers") and w.name_servers:
            if isinstance(w.name_servers, list):
                data.name_servers = [ns.lower() for ns in w.name_servers[:3]]
            else:
                data.name_servers = [w.name_servers.lower()]

        return data

    def _parse_whois_subprocess(self, data: DomainData) -> DomainData:
        """Parsuje dane używając systemowego whois"""
        try:
            # Wykonaj polecenie whois
            result = subprocess.run(
                ["whois", self.domain], capture_output=True, text=True, timeout=10
            )

            if result.returncode != 0:
                return data

            whois_text = result.stdout.lower()

            if not whois_text or "no match" in whois_text:
                return data

            data.found = True

            # Parsuj daty
            creation_patterns = [
                r"creation date:\s*(\d{4}-\d{2}-\d{2})",
                r"created:\s*(\d{4}-\d{2}-\d{2})",
                r"registered on:\s*(\d{4}-\d{2}-\d{2})",
            ]

            for pattern in creation_patterns:
                match = re.search(pattern, whois_text)
                if match:
                    data.creation_date = match.group(1)
                    try:
                        creation = datetime.strptime(data.creation_date, "%Y-%m-%d")
                        age = datetime.now() - creation
                        data.age_days = age.days
                        data.age_years = round(age.days / 365.25, 1)
                    except:
                        pass
                    break

            # Rejestrator
            registrar_match = re.search(r"registrar:\s*(.+)", whois_text)
            if registrar_match:
                data.registrar = registrar_match.group(1).strip()

            return data

        except Exception as e:
            print(f"Błąd subprocess whois: {str(e)}")
            return data

    def _extract_domain(self, url: str) -> Optional[str]:
        """Wyciąga domenę z URL"""
        try:
            if not url.startswith("http"):
                url = f"https://{url}"

            parsed = urlparse(url)
            domain = parsed.netloc

            # Usuń www.
            if domain.startswith("www."):
                domain = domain[4:]

            return domain
        except:
            return None

import requests
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class RegonData:
    nip: str
    name: Optional[str] = None
    regon: Optional[str] = None
    krs: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    vat_status: Optional[str] = None
    bank_accounts: List[str] = field(default_factory=list)
    registration_date: Optional[str] = None


class RegonCollector:
    """Collector do pobierania danych z API Białej Listy VAT"""

    BASE_URL = "https://wl-api.mf.gov.pl"

    def __init__(self, nip: str):
        self.nip = nip.replace("-", "").replace(" ", "")
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "BusinessIntelDemo/1.0", "Accept": "application/json"}
        )

    def collect(self) -> RegonData:
        """Zbiera dane z API Białej Listy VAT"""
        try:
            date = datetime.now().strftime("%Y-%m-%d")
            url = f"{self.BASE_URL}/api/search/nip/{self.nip}"

            response = self.session.get(url, params={"date": date}, timeout=10)

            response.raise_for_status()
            result = response.json()

            # Sprawdź czy znaleziono podmiot
            if result.get("result", {}).get("subject") is None:
                print(f"Nie znaleziono podmiotu w bazie VAT dla NIP: {self.nip}")
                return RegonData(nip=self.nip)

            # Przetwórz dane
            return self._parse_vat_data(result["result"])

        except Exception as e:
            print(f"Błąd podczas pobierania danych VAT: {str(e)}")
            return RegonData(nip=self.nip)

    def _parse_vat_data(self, result: dict) -> RegonData:
        """Przetwarza dane z API VAT"""
        subject = result.get("subject", {})

        # Wyciągnij adres
        address_full = subject.get("residenceAddress", "") or subject.get(
            "workingAddress", ""
        )

        # Próba parsowania adresu
        city = None
        postal_code = None
        if address_full:
            parts = address_full.split(", ")
            if len(parts) >= 2:
                city = parts[-2] if len(parts) >= 2 else None
                postal_code = parts[-1] if len(parts) >= 3 else None

        # Wyciągnij rachunki bankowe
        accounts = subject.get("accountNumbers", [])
        formatted_accounts = [acc.replace(" ", "") for acc in accounts]

        # Status VAT
        status_vat = subject.get("statusVat", "Nieznany")
        if status_vat == "Czynny":
            vat_status = "🟢 Czynny podatnik VAT"
        elif status_vat == "Zwolniony":
            vat_status = "🟡 Zwolniony z VAT"
        elif status_vat == "Nieczynny":
            vat_status = "🔴 Nieczynny podatnik VAT"
        else:
            vat_status = f"Status: {status_vat}"

        data = RegonData(
            nip=self.nip,
            name=subject.get("name", None),
            regon=subject.get("regon", None),
            krs=subject.get("krs", None),
            address=address_full,
            city=city,
            postal_code=postal_code,
            vat_status=vat_status,
            bank_accounts=formatted_accounts,
            registration_date=subject.get("registrationLegalDate", None),
        )

        return data

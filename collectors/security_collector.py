import requests
import ssl
import socket
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
from urllib.parse import urlparse


@dataclass
class SSLInfo:
    has_ssl: bool = False
    issuer: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    days_to_expire: Optional[int] = None
    version: Optional[str] = None
    is_valid: bool = False


@dataclass
class SecurityHeaders:
    strict_transport_security: Optional[str] = None
    content_security_policy: Optional[str] = None
    x_frame_options: Optional[str] = None
    x_content_type_options: Optional[str] = None
    x_xss_protection: Optional[str] = None
    referrer_policy: Optional[str] = None
    permissions_policy: Optional[str] = None


@dataclass
class SecurityData:
    url: str
    ssl_info: SSLInfo = field(default_factory=SSLInfo)
    security_headers: SecurityHeaders = field(default_factory=SecurityHeaders)
    security_score: int = 0
    recommendations: List[str] = field(default_factory=list)
    vulnerabilities: List[str] = field(default_factory=list)


class SecurityCollector:
    def __init__(self, url: str):
        self.url = url if url.startswith("http") else f"https://{url}"
        self.domain = urlparse(self.url).netloc

    def collect(self) -> SecurityData:
        """Zbiera informacje o bezpieczeństwie strony"""
        try:
            data = SecurityData(url=self.url)

            # Sprawdź SSL/TLS
            data.ssl_info = self._check_ssl()

            # Sprawdź nagłówki bezpieczeństwa
            data.security_headers = self._check_security_headers()

            # Oblicz wynik bezpieczeństwa
            data.security_score = self._calculate_security_score(data)

            # Generuj rekomendacje
            data.recommendations = self._generate_recommendations(data)

            # Wykryj potencjalne podatności
            data.vulnerabilities = self._detect_vulnerabilities(data)

            return data

        except Exception as e:
            print(f"Błąd podczas sprawdzania bezpieczeństwa: {str(e)}")
            return SecurityData(url=self.url)

    def _check_ssl(self) -> SSLInfo:
        """Sprawdza certyfikat SSL/TLS"""
        ssl_info = SSLInfo()

        try:
            # Sprawdź czy strona ma HTTPS
            if not self.url.startswith("https://"):
                ssl_info.has_ssl = False
                return ssl_info

            ssl_info.has_ssl = True

            # Pobierz certyfikat
            context = ssl.create_default_context()

            with socket.create_connection((self.domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=self.domain) as ssock:
                    cert = ssock.getpeercert()

                    # Wyciągnij informacje
                    ssl_info.issuer = dict(x[0] for x in cert["issuer"])[
                        "organizationName"
                    ]
                    ssl_info.version = ssock.version()

                    # Daty ważności
                    not_before = cert["notBefore"]
                    not_after = cert["notAfter"]

                    ssl_info.valid_from = not_before
                    ssl_info.valid_to = not_after

                    # Oblicz dni do wygaśnięcia
                    expire_date = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                    days_left = (expire_date - datetime.now()).days
                    ssl_info.days_to_expire = days_left

                    # Sprawdź czy certyfikat jest ważny
                    ssl_info.is_valid = days_left > 0

        except Exception as e:
            print(f"Błąd sprawdzania SSL: {str(e)}")

        return ssl_info

    def _check_security_headers(self) -> SecurityHeaders:
        """Sprawdza nagłówki bezpieczeństwa HTTP"""
        headers_info = SecurityHeaders()

        try:
            response = requests.get(self.url, timeout=10, allow_redirects=True)
            headers = response.headers

            # Sprawdź najważniejsze nagłówki bezpieczeństwa
            headers_info.strict_transport_security = headers.get(
                "Strict-Transport-Security"
            )
            headers_info.content_security_policy = headers.get(
                "Content-Security-Policy"
            )
            headers_info.x_frame_options = headers.get("X-Frame-Options")
            headers_info.x_content_type_options = headers.get("X-Content-Type-Options")
            headers_info.x_xss_protection = headers.get("X-XSS-Protection")
            headers_info.referrer_policy = headers.get("Referrer-Policy")
            headers_info.permissions_policy = headers.get("Permissions-Policy")

        except Exception as e:
            print(f"Błąd sprawdzania nagłówków: {str(e)}")

        return headers_info

    def _calculate_security_score(self, data: SecurityData) -> int:
        """Oblicza wynik bezpieczeństwa (0-100)"""
        score = 0

        # SSL/TLS (40 punktów)
        if data.ssl_info.has_ssl:
            score += 20
            if data.ssl_info.is_valid:
                score += 10
            if data.ssl_info.days_to_expire and data.ssl_info.days_to_expire > 30:
                score += 10

        # Nagłówki bezpieczeństwa (60 punktów)
        headers = data.security_headers

        if headers.strict_transport_security:
            score += 15
        if headers.content_security_policy:
            score += 15
        if headers.x_frame_options:
            score += 10
        if headers.x_content_type_options:
            score += 10
        if headers.x_xss_protection:
            score += 5
        if headers.referrer_policy:
            score += 5

        return min(score, 100)

    def _generate_recommendations(self, data: SecurityData) -> List[str]:
        """Generuje rekomendacje bezpieczeństwa"""
        recommendations = []

        # SSL/TLS
        if not data.ssl_info.has_ssl:
            recommendations.append(
                "🔴 KRYTYCZNE: Brak certyfikatu SSL/HTTPS - strona nie jest bezpieczna"
            )
        elif not data.ssl_info.is_valid:
            recommendations.append(
                "🔴 KRYTYCZNE: Certyfikat SSL wygasł - wymaga natychmiastowej odnowy"
            )
        elif data.ssl_info.days_to_expire and data.ssl_info.days_to_expire < 30:
            recommendations.append(
                f"🟡 UWAGA: Certyfikat SSL wygasa za {data.ssl_info.days_to_expire} dni"
            )

        # Nagłówki bezpieczeństwa
        headers = data.security_headers

        if not headers.strict_transport_security:
            recommendations.append("🟡 Dodaj nagłówek Strict-Transport-Security (HSTS)")

        if not headers.content_security_policy:
            recommendations.append("🟡 Dodaj nagłówek Content-Security-Policy (CSP)")

        if not headers.x_frame_options:
            recommendations.append(
                "🟡 Dodaj nagłówek X-Frame-Options (ochrona przed clickjacking)"
            )

        if not headers.x_content_type_options:
            recommendations.append("🟡 Dodaj nagłówek X-Content-Type-Options: nosniff")

        if not headers.x_xss_protection:
            recommendations.append("⚪ Rozważ dodanie nagłówka X-XSS-Protection")

        if not recommendations:
            recommendations.append(
                "🟢 Świetnie! Strona ma wszystkie kluczowe zabezpieczenia"
            )

        return recommendations

    def _detect_vulnerabilities(self, data: SecurityData) -> List[str]:
        """Wykrywa potencjalne podatności"""
        vulnerabilities = []

        # Brak HTTPS
        if not data.ssl_info.has_ssl:
            vulnerabilities.append("Man-in-the-middle attack (brak szyfrowania)")
            vulnerabilities.append("Przechwytywanie danych użytkowników")

        # Brak nagłówków
        headers = data.security_headers

        if not headers.x_frame_options:
            vulnerabilities.append("Clickjacking (możliwość osadzenia w iframe)")

        if not headers.content_security_policy:
            vulnerabilities.append("XSS (Cross-Site Scripting) - brak CSP")

        if not headers.x_content_type_options:
            vulnerabilities.append("MIME type sniffing")

        return vulnerabilities

import streamlit as st
import os
from datetime import datetime
from dotenv import load_dotenv
from collectors.website_collector import WebsiteCollector
from collectors.regon_collector import RegonCollector
from collectors.news_collector import NewsCollector
from collectors.security_collector import SecurityCollector
from collectors.ai_analyzer import AIAnalyzer

# Wczytaj zmienne środowiskowe
load_dotenv()

def generate_pdf_report(company_name, nip, regon_data, results, website_url):
    """Generuje raport PDF"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from io import BytesIO
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    
    # Rejestracja czcionki obsługującej polskie znaki
    try:
        pdfmetrics.registerFont(TTFont('DejaVu', 'DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVu-Bold', 'DejaVuSans-Bold.ttf'))
        font_name = 'DejaVu'
        font_bold = 'DejaVu-Bold'
    except:
        font_name = 'Helvetica'
        font_bold = 'Helvetica-Bold'
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    
    story = []
    styles = getSampleStyleSheet()
    
    # Tytuł
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=30,
        fontName=font_bold,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        fontName=font_bold,
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        fontName=font_name,
    )
    
    def safe_text(text):
        if text is None:
            return 'Brak danych'
        try:
            return str(text).encode('utf-8').decode('utf-8')
        except:
            return str(text)
    
    story.append(Paragraph(safe_text("RAPORT BIALEGO WYWIADU"), title_style))
    story.append(Paragraph(safe_text(f"Firma: {company_name}"), heading_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Dane podstawowe
    story.append(Paragraph(safe_text("Dane z Bialej Listy VAT"), heading_style))
    
    vat_data = [
        ['NIP:', safe_text(nip)],
        ['Nazwa:', safe_text(regon_data.name or 'Brak danych')],
        ['REGON:', safe_text(regon_data.regon or 'Brak danych')],
        ['Status VAT:', safe_text(regon_data.vat_status or 'Brak danych').replace('🟢', '').replace('🔴', '').replace('🟡', '')],
        ['Adres:', safe_text(regon_data.address or 'Brak danych')],
    ]
    
    if regon_data.registration_date:
        vat_data.append(['Data rejestracji:', safe_text(regon_data.registration_date)])
    
    t = Table(vat_data, colWidths=[5*cm, 12*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    story.append(t)
    story.append(Spacer(1, 0.5*cm))
    
    if regon_data.bank_accounts:
        story.append(Paragraph(safe_text("Rachunki bankowe (Biala lista)"), heading_style))
        for acc in regon_data.bank_accounts[:3]:
            formatted = ' '.join([acc[i:i+4] for i in range(0, len(acc), 4)])
            story.append(Paragraph(safe_text(formatted), normal_style))
        story.append(Spacer(1, 0.5*cm))
    
    if website_url and 'website' in results:
        story.append(Paragraph(safe_text("Dane ze strony WWW"), heading_style))
        web_data = results['website']
        www_info = [['URL:', safe_text(website_url)]]
        if web_data.title:
            www_info.append(['Tytul:', safe_text(web_data.title)])
        if web_data.emails:
            www_info.append(['Email:', safe_text(', '.join(web_data.emails[:3]))])
        if web_data.phones:
            www_info.append(['Telefon:', safe_text(', '.join(web_data.phones[:2]))])
        
        t2 = Table(www_info, colWidths=[5*cm, 12*cm])
        t2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t2)
        story.append(Spacer(1, 0.5*cm))
    
    if 'security' in results:
        story.append(Paragraph(safe_text("Bezpieczenstwo strony"), heading_style))
        sec_data = results['security']
        security_info = [['Ocena bezpieczenstwa:', f"{sec_data.security_score}/100"]]
        if sec_data.ssl_info.has_ssl:
            security_info.append(['HTTPS:', 'Aktywny'])
            if sec_data.ssl_info.issuer:
                security_info.append(['Wydawca SSL:', safe_text(sec_data.ssl_info.issuer)])
        else:
            security_info.append(['HTTPS:', 'BRAK'])
        
        t3 = Table(security_info, colWidths=[5*cm, 12*cm])
        t3.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
        ]))
        story.append(t3)
        story.append(Spacer(1, 0.5*cm))
    
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(safe_text(f"Data raportu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"), normal_style))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def search_company_website(company_name: str, nip: str) -> str:
    """Wyszukiwanie prawdziwej strony firmowej"""
    try:
        import requests
        from bs4 import BeautifulSoup
        from urllib.parse import urlparse
        
        query = f"{company_name} NIP {nip} strona www"
        url = "https://html.duckduckgo.com/html/"
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        response = session.post(url, data={'q': query}, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            results = soup.find_all('a', class_='result__a')
            
            skip_domains = [
                'facebook.com', 'linkedin.com', 'twitter.com', 'instagram.com',
                'olx.pl', 'allegro.pl', 'wikipedia.org',
                'ceidg.gov.pl', 'gov.pl', 'stat.gov.pl',
                'panoramafirm.pl', 'biznesfinder.pl', 'infoveriti.pl',
                'europages.pl', 'kompass.com', 'golden-line.pl',
                'pkt.pl', 'biznes.nf.pl', 'yasni.pl', 'owg.pl',
                'firmeo.pl', 'katalog-firm.pl', 'polskiefirmy.pl',
                'katalogfirm.pl', 'firmy.net', 'cylex.pl', 'gowork.pl',
                'zumi.pl', 'poradnikprzedsiebiorcy.pl', 'regon.pl',
                'rejestr.io', 'krs-online.com.pl', 'krs.ms.gov.pl'
            ]
            
            for result in results[:10]:
                href = result.get('href', '')
                if not href:
                    continue
                
                if any(domain in href.lower() for domain in skip_domains):
                    continue
                
                try:
                    parsed = urlparse(href)
                    domain = parsed.netloc.lower()
                    if len(domain.split('.')[0]) > 20:
                        continue
                    return href
                except:
                    continue
        
        return None
        
    except Exception as e:
        print(f"Błąd wyszukiwania: {e}")
        return None

def display_ai_analysis(ai_result):
    """Wyświetla wyniki analizy AI"""
    st.markdown("---")
    st.markdown("---")
    st.header("🤖 Analiza AI - Ocena Ryzyka Biznesowego")
    
    # Karta ryzyka z kolorem
    risk_colors = {
        "NISKIE": "#d4edda",
        "ŚREDNIE": "#fff3cd", 
        "WYSOKIE": "#f8d7da"
    }
    risk_text_colors = {
        "NISKIE": "#155724",
        "ŚREDNIE": "#856404",
        "WYSOKIE": "#721c24"
    }
    
    bg_color = risk_colors.get(ai_result.risk_level, "#fff3cd")
    text_color = risk_text_colors.get(ai_result.risk_level, "#856404")
    
    st.markdown(f"""
    <div style="background-color: {bg_color}; color: {text_color}; padding: 1.5rem; border-radius: 10px; border-left: 5px solid {text_color};">
        <h2>Poziom Ryzyka: {ai_result.risk_level}</h2>
        <h3>Ocena: {ai_result.risk_score}/100</h3>
        <p><strong>Data analizy:</strong> {ai_result.analysis_date}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("")
    
    # Rekomendacja
    st.markdown("### 💡 Rekomendacja")
    st.info(ai_result.recommendation)
    
    # Szczegółowa analiza
    st.markdown("### 📊 Szczegółowa Analiza")
    st.write(ai_result.detailed_analysis)
    
    # Mocne strony vs Red Flags
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### ✅ Mocne Strony")
        if ai_result.strengths:
            for strength in ai_result.strengths:
                st.success(f"• {strength}")
        else:
            st.warning("Brak zidentyfikowanych mocnych stron")
    
    with col2:
        st.markdown("### ⚠️ Red Flags")
        if ai_result.red_flags:
            for flag in ai_result.red_flags:
                st.error(f"• {flag}")
        else:
            st.success("Nie wykryto istotnych ostrzeżeń")
    
    # Konkurencja
    if ai_result.competitors:
        st.markdown("### 🏢 Konkurencja")
        for i, comp in enumerate(ai_result.competitors, 1):
            with st.expander(f"{i}. {comp.name}"):
                if comp.website:
                    st.write(f"🌐 **Strona:** {comp.website}")
                if comp.description:
                    st.write(f"📝 **Opis:** {comp.description}")
    
    # Trendy branżowe
    if ai_result.industry_trends:
        st.markdown("### 📈 Trendy Branżowe")
        trends = ai_result.industry_trends
        
        st.write(f"**Branża:** {trends.industry}")
        if trends.growth_rate:
            st.metric("Prognozowany wzrost", f"{trends.growth_rate}%")
        
        if trends.trends:
            st.markdown("**Kluczowe trendy:**")
            for trend in trends.trends:
                st.write(f"• {trend}")
        
        col1, col2 = st.columns(2)
        with col1:
            if trends.opportunities:
                st.markdown("**Szanse:**")
                for opp in trends.opportunities:
                    st.write(f"✓ {opp}")
        
        with col2:
            if trends.threats:
                st.markdown("**Zagrożenia:**")
                for threat in trends.threats:
                    st.write(f"✗ {threat}")
    
    # Benchmark
    if ai_result.benchmark:
        st.markdown("### 🎯 Benchmark z Konkurencją")
        bench = ai_result.benchmark
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Ranking", f"{bench.ranking}/{bench.total_competitors}")
        with col2:
            st.metric("Wynik Ogólny", f"{bench.overall_score}/100")
        with col3:
            percentile = ((bench.total_competitors - bench.ranking) / bench.total_competitors) * 100
            st.metric("Percentyl", f"{percentile:.0f}%")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Przewagi:**")
            for strength in bench.strengths_vs_competitors:
                st.write(f"✓ {strength}")
        
        with col2:
            st.markdown("**Słabości:**")
            for weakness in bench.weaknesses_vs_competitors:
                st.write(f"✗ {weakness}")

def main():
    st.title("🔍 DEMO | Aplikacja Białego Wywiadu")
    st.markdown("---")
    
    # Formularz wejściowy
    col1, col2 = st.columns(2)
    
    with col1:
        company_name = st.text_input("Nazwa firmy (opcjonalnie)", placeholder="Przykładowa Sp. z o.o.")
    
    with col2:
        nip = st.text_input("NIP firmy", placeholder="1234567890")
    
    if st.button("🚀 Uruchom analizę", type="primary"):
        if not nip:
            st.warning("⚠️ Podaj NIP firmy")
            return
        
        results = {}
        
        # Collector 1: Dane z Białej Listy VAT
        with st.spinner("Pobieranie danych z Białej Listy VAT..."):
            regon_collector = RegonCollector(nip)
            results['regon'] = regon_collector.collect()
        
        regon_data = results['regon']
        
        # Jeśli nie podano nazwy, użyj z VAT
        if not company_name and regon_data.name:
            company_name = regon_data.name
        
        # Wyświetlanie wyników z VAT
        st.success("✅ Dane z Białej Listy VAT pobrane")
        st.markdown("---")
        
        # Dane z Białej Listy VAT
        st.subheader("📋 Dane z Białej Listy VAT")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if regon_data.name:
                st.write(f"**Nazwa:** {regon_data.name}")
            st.write(f"**NIP:** {regon_data.nip}")
            if regon_data.regon:
                st.write(f"**REGON:** {regon_data.regon}")
            if regon_data.krs:
                st.write(f"**KRS:** {regon_data.krs}")
        
        with col2:
            if regon_data.vat_status:
                st.write(f"**Status VAT:** {regon_data.vat_status}")
            if regon_data.registration_date:
                st.write(f"**Data rejestracji:** {regon_data.registration_date}")
        
        if regon_data.address:
            st.write(f"**📍 Adres:** {regon_data.address}")
        
        if regon_data.bank_accounts:
            st.markdown("**🏦 Rachunki bankowe (Biała lista):**")
            for acc in regon_data.bank_accounts:
                formatted = ' '.join([acc[i:i+4] for i in range(0, len(acc), 4)])
                st.code(formatted, language=None)
        
        # Collector 2: Szukanie strony WWW
        website_url = None
        
        if company_name:
            with st.spinner("Wyszukiwanie strony WWW..."):
                website_url = search_company_website(company_name, nip)
            
            if not website_url:
                st.warning("⚠️ Nie znaleziono dedykowanej strony WWW firmy")
        
        # Collector 3: Analiza strony WWW
        if website_url:
            st.markdown("---")
            with st.spinner(f"Analizuję stronę {website_url}..."):
                website_collector = WebsiteCollector(website_url)
                results['website'] = website_collector.collect()
            
            data = results['website']
            
            st.subheader("🌐 Dane ze strony WWW")
            st.write(f"**URL:** {data.url}")
            
            if data.title:
                st.write(f"**Tytuł:** {data.title}")
            
            if data.description:
                st.write(f"**Opis:** {data.description}")
            
            if data.about:
                st.markdown("**📋 O firmie:**")
                st.info(data.about)
            
            col1, col2 = st.columns(2)
            
            with col1:
                if data.emails:
                    st.markdown("**📧 Emaile:**")
                    for email in data.emails:
                        st.write(f"- {email}")
                
                if data.phones:
                    st.markdown("**📞 Telefony:**")
                    for phone in data.phones:
                        st.write(f"- {phone}")
            
            with col2:
                if data.addresses:
                    st.markdown("**📍 Adresy:**")
                    for addr in data.addresses:
                        st.write(f"- {addr}")
            
            if data.social_media:
                st.markdown("**📱 Social Media:**")
                cols = st.columns(len(data.social_media))
                for idx, (platform, url) in enumerate(data.social_media.items()):
                    with cols[idx]:
                        st.markdown(f"[{platform.capitalize()}]({url})")
            
            if data.services:
                st.markdown("**💼 Usługi/Oferta:**")
                for service in data.services[:10]:
                    st.write(f"- {service}")
            
            if data.cms or data.technologies:
                st.markdown("**🛠️ Informacje techniczne:**")
                if data.cms:
                    st.write(f"- CMS: {data.cms}")
                if data.technologies:
                    st.write(f"- Technologie: {', '.join(data.technologies)}")
        
        # Collector 4: Wiadomości
        if company_name:
            st.markdown("---")
            with st.spinner("Szukam wiadomości o firmie..."):
                news_collector = NewsCollector(company_name, nip)
                results['news'] = news_collector.collect()
            
            news_data = results['news']
            
            if news_data.articles:
                st.subheader(f"📰 Wiadomości o firmie ({news_data.total_found} znalezionych)")
                
                for article in news_data.articles:
                    with st.container():
                        st.markdown(f"**[{article.title}]({article.url})**")
                        if article.source:
                            st.caption(f"📍 Źródło: {article.source}")
                        if article.snippet:
                            st.text(article.snippet)
                        st.markdown("---")
        
        # Collector 5: Security Check
        if website_url:
            st.markdown("---")
            with st.spinner("Sprawdzam bezpieczeństwo strony..."):
                security_collector = SecurityCollector(website_url)
                results['security'] = security_collector.collect()
            
            security_data = results['security']
            
            st.subheader(f"🔒 Bezpieczeństwo strony")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.progress(security_data.security_score / 100)
            with col2:
                st.metric("Wynik", f"{security_data.security_score}/100")
            
            if security_data.security_score >= 80:
                st.success(f"✅ Bardzo dobry poziom bezpieczeństwa")
            elif security_data.security_score >= 60:
                st.warning(f"⚠️ Średni poziom bezpieczeństwa")
            else:
                st.error(f"❌ Niski poziom bezpieczeństwa")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**🔐 Certyfikat SSL/TLS:**")
                if security_data.ssl_info.has_ssl:
                    st.write(f"✅ HTTPS aktywny")
                    if security_data.ssl_info.issuer:
                        st.write(f"- Wydawca: {security_data.ssl_info.issuer}")
                    if security_data.ssl_info.days_to_expire:
                        if security_data.ssl_info.days_to_expire > 30:
                            st.write(f"- ✅ Wygasa za: {security_data.ssl_info.days_to_expire} dni")
                        else:
                            st.write(f"- ⚠️ Wygasa za: {security_data.ssl_info.days_to_expire} dni")
                else:
                    st.write(f"❌ Brak HTTPS")
            
            with col2:
                st.markdown("**🛡️ Nagłówki bezpieczeństwa:**")
                headers = security_data.security_headers
                st.write(f"{'✅' if headers.strict_transport_security else '❌'} HSTS")
                st.write(f"{'✅' if headers.content_security_policy else '❌'} CSP")
                st.write(f"{'✅' if headers.x_frame_options else '❌'} X-Frame-Options")
            
            if security_data.vulnerabilities:
                st.markdown("**⚠️ Wykryte podatności:**")
                for vuln in security_data.vulnerabilities:
                    st.write(f"- 🔴 {vuln}")
        
        # Zapisz dane do session_state dla AI
        st.session_state.analysis_data = {
            'company_name': company_name,
            'nip': nip,
            'collected_data': results
        }
        
        # SEKCJA PODSUMOWANIE
        st.markdown("---")
        st.markdown("---")
        st.header("📊 Podsumowanie analizy")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Collectory użyte", len([k for k in results.keys()]))
        
        with col2:
            if 'website' in results and results['website'].emails:
                st.metric("Znalezione emaile", len(results['website'].emails))
            else:
                st.metric("Znalezione emaile", 0)
        
        with col3:
            if 'news' in results:
                st.metric("Wiadomości", results['news'].total_found)
            else:
                st.metric("Wiadomości", 0)
        
        with col4:
            if 'security' in results:
                score = results['security'].security_score
                st.metric("Bezpieczeństwo", f"{score}/100")
            else:
                st.metric("Bezpieczeństwo", "N/A")
        
        st.markdown("### 🎯 Kluczowe informacje:")
        
        summary_points = []
        
        if regon_data.vat_status:
            summary_points.append(f"**Status VAT:** {regon_data.vat_status}")
        
        if website_url:
            summary_points.append(f"**Strona WWW:** {website_url}")
        else:
            summary_points.append("**Strona WWW:** ❌ Nie znaleziono")
        
        if 'security' in results:
            score = results['security'].security_score
            if score >= 80:
                summary_points.append(f"**Bezpieczeństwo:** ✅ Bardzo dobre ({score}/100)")
            elif score >= 60:
                summary_points.append(f"**Bezpieczeństwo:** ⚠️ Średnie ({score}/100)")
            else:
                summary_points.append(f"**Bezpieczeństwo:** ❌ Słabe ({score}/100)")
        
        if 'website' in results:
            if results['website'].emails:
                summary_points.append(f"**Email:** {results['website'].emails[0]}")
            if results['website'].phones:
                summary_points.append(f"**Telefon:** {results['website'].phones[0]}")
        
        for point in summary_points:
            st.markdown(f"- {point}")
        
        # Przycisk PDF
        st.markdown("---")
        st.markdown("### 📄 Pobierz raport")
        
        try:
            pdf_data = generate_pdf_report(company_name, nip, regon_data, results, website_url)
            st.download_button(
                label="📥 Pobierz raport PDF",
                data=pdf_data,
                file_name=f"raport_{nip}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"❌ Błąd generowania PDF: {str(e)}")
    
    # SEKCJA AI - pojawia się po analizie podstawowej
    if 'analysis_data' in st.session_state and st.session_state.analysis_data.get('collected_data'):
        st.markdown("---")
        st.markdown("---")
        
        # Sekcja AI z fioletowym tłem
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 2rem; border-radius: 10px; margin: 2rem 0;">
            <h2>🤖 Zaawansowana Analiza AI</h2>
            <p>Wykorzystaj GPT-4 do głębokiej analizy ryzyka biznesowego, automatycznego wyszukiwania konkurencji i identyfikacji trendów branżowych.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Sprawdź klucz API
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            st.error("⚠️ Brak klucza OpenAI API. Dodaj `OPENAI_API_KEY` do pliku `.env`")
        else:
            # Pokaż pozostałe zapytania
            try:
                analyzer = AIAnalyzer(api_key)
                remaining = analyzer.get_remaining_queries()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📊 Pozostało zapytań", f"{remaining}/20")
                with col2:
                    st.metric("🎯 Model AI", "GPT-4o")
                with col3:
                    st.metric("⏱️ Czas", "~30-60s")
            except:
                remaining = 20
            
            st.markdown("")
            
            if st.button("🚀 Uruchom Analizę AI", type="primary", use_container_width=True, disabled=(remaining <= 0)):
                with st.spinner("🤖 AI analizuje dane... To może potrwać 30-60 sekund..."):
                    try:
                        analyzer = AIAnalyzer(api_key)
                        ai_result = analyzer.analyze(
                            st.session_state.analysis_data['company_name'],
                            st.session_state.analysis_data['nip'],
                            st.session_state.analysis_data['collected_data']
                        )
                        
                        st.session_state.ai_analysis = ai_result
                        st.success("✅ Analiza AI zakończona!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Błąd analizy AI: {str(e)}")
        
        # Wyświetl wyniki AI
        if 'ai_analysis' in st.session_state:
            display_ai_analysis(st.session_state.ai_analysis)

if __name__ == "__main__":
    main()
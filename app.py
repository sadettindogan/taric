import streamlit as st
from playwright.sync_api import sync_playwright
import json
import os
import time

# ─── ÜLKE LİSTESİ YÜKLE ───────────────────────────────────────────────────────
@st.cache_data
def ulke_listesi_yukle():
    json_yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ulkeler.json")
    if os.path.exists(json_yol):
        with open(json_yol, encoding="utf-8") as f:
            return json.load(f)
    return {}

ULKELER = ulke_listesi_yukle()

def gtip_cevir(girdi):
    """
    GTİP kodunu TARIC formatına çevirir.
    72.07.11.14.00.00 → 72071114000 (noktasız, 11 hane)
    Zaten noktalı veya 12 haneli olsa da doğru sonuç verir.
    """
    temiz = str(girdi).replace(".", "").replace(" ", "").strip()
    if len(temiz) == 12:
        temiz = temiz[:-1]   # son haneyi sil → 11 hane
    return temiz

def ulke_cevir(girdi):
    girdi = girdi.strip()
    if not girdi:
        return ""
    if len(girdi) <= 3 and girdi.isalpha():
        return girdi.upper()
    anahtar = girdi.upper()
    if anahtar in ULKELER:
        return ULKELER[anahtar]
    for k, v in ULKELER.items():
        if k.startswith(anahtar):
            return v
    return girdi.upper()

st.set_page_config(
    page_title="TARIC Sorgu",
    page_icon="🛃",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@400;600;700;800&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background: #f5f3ef;
    font-family: 'Syne', sans-serif;
    color: #1a1a1a;
}
section[data-testid="stSidebar"] { display: none; }
header { display: none !important; }
.block-container { padding: 12px 16px !important; max-width: 100% !important; }

[data-testid="stTextInput"] input {
    background: white !important;
    border: 1px solid #d4c97a !important;
    border-radius: 4px !important;
    color: #1a1a1a !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 8px 10px !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #c8b560 !important;
    box-shadow: 0 0 0 2px rgba(200,181,96,0.2) !important;
}
[data-testid="stTextInput"] label {
    color: #888 !important;
    font-size: 10px !important;
    font-weight: 700 !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
}

.stButton > button {
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: 12px !important;
    letter-spacing: 1px !important;
    text-transform: uppercase !important;
    border-radius: 4px !important;
    padding: 10px 0 !important;
    width: 100% !important;
    transition: all 0.2s !important;
    border: none !important;
}

div[data-testid="column"]:nth-child(1) .stButton > button {
    background: #c8b560 !important;
    color: #1a1a1a !important;
}
div[data-testid="column"]:nth-child(1) .stButton > button:hover {
    background: #d4c97a !important;
}

.durum-ok   { background:#e6f4ea; color:#2e7d32; border:1px solid #66bb6a; border-radius:6px; padding:8px 12px; font-weight:700; font-size:12px; margin:6px 0; }
.durum-hata { background:#fdecea; color:#c62828; border:1px solid #ef9a9a; border-radius:6px; padding:8px 12px; font-weight:700; font-size:12px; margin:6px 0; }

hr { border-color: #e0ddd5 !important; margin: 12px 0 !important; }
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ─────────────────────────────────────────────────────────────
for k, v in {
    "page_html": None,
    "pdf_bytes": None,
    "durum": "",
    "sorgulandı": False,
    "gtip_son": "",
    "ulke_son": "",
    "base_url": "https://ec.europa.eu",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── TARIC SORGU ───────────────────────────────────────────────────────────────
def taric_sorgula(gtip, ulke, tarih):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path="/usr/bin/chromium",
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            context = browser.new_context(
                viewport={"width": 1400, "height": 900},
            )
            page = context.new_page()

            url = "https://ec.europa.eu/taxation_customs/dds2/taric/taric_consultation.jsp?Lang=en"
            page.goto(url, wait_until="networkidle", timeout=30000)

            page.fill("#taricCode", gtip.strip())

            ulke_temiz = ulke.strip()
            if ulke_temiz:
                try:
                    page.select_option("#taricArea", ulke_temiz)
                except:
                    pass

            tarih_temiz = tarih.strip()
            if tarih_temiz:
                page.evaluate(f"document.querySelector('#SimDatePic').value = '{tarih_temiz}'")

            page.click("button[value='Retrieve Measures']")
            page.wait_for_load_state("networkidle", timeout=20000)
            time.sleep(1.5)

            # Sayfanın tam HTML'ini al
            html_content = page.content()
            current_url  = page.url

            # PDF
            pdf_bytes = page.pdf(format="A4", print_background=True)

            browser.close()
            return html_content, pdf_bytes, current_url, None

    except Exception as e:
        return None, None, None, str(e)


def html_temizle(html, base_url):
    """
    Ham HTML'i iframe içinde düzgün görüntülenecek hale getirir:
    - Relative URL'leri absolute yapar
    - Gereksiz script/form bloklarını kaldırır
    - Font boyutunu büyütür
    """
    import re

    # Base tag ekle → relative linkler çalışsın
    base_tag = f'<base href="{base_url}" target="_blank">'

    # <head> içine base tag ekle
    if "<head>" in html:
        html = html.replace("<head>", f"<head>{base_tag}", 1)
    elif "<HEAD>" in html:
        html = html.replace("<HEAD>", f"<HEAD>{base_tag}", 1)
    else:
        html = base_tag + html

    # Okunabilirlik için body'e font büyütme stili ekle
    okunabilirlik_stili = """
    <style>
        body {
            font-size: 15px !important;
            line-height: 1.7 !important;
            font-family: Arial, sans-serif !important;
        }
        table { font-size: 14px !important; }
        td, th { padding: 6px 10px !important; }
        a { font-size: 14px !important; }
        /* Ok işaretleri tıklanabilir görünsün */
        a[href*="javascript"], a[onclick] {
            cursor: pointer !important;
            color: #1a73e8 !important;
            text-decoration: underline !important;
        }
    </style>
    """

    if "</head>" in html:
        html = html.replace("</head>", okunabilirlik_stili + "</head>", 1)
    elif "</HEAD>" in html:
        html = html.replace("</HEAD>", okunabilirlik_stili + "</HEAD>", 1)
    else:
        html = okunabilirlik_stili + html

    return html


# ─── LAYOUT ───────────────────────────────────────────────────────────────────
sol, sag = st.columns([0.5, 2.5], gap="medium")

# ══════════════════════════════════════════════════════════════════════════════
# SOL PANEL
# ══════════════════════════════════════════════════════════════════════════════
with sol:
    st.markdown("""
    <div style='padding-bottom:14px;border-bottom:2px solid #c8b560;margin-bottom:16px;'>
        <div style='font-size:22px;font-weight:800;color:#1a1a1a;'>🛃 TARIC</div>
        <div style='font-size:10px;color:#999;letter-spacing:2px;text-transform:uppercase;'>
            Gümrük Tarife Sorgulama
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── YAPISTIR KUTUSU ──────────────────────────────────────────────
    yapistir = st.text_area(
        "Excel'den Yapıştır",
        placeholder="72.07.11.14.00.00	RUSYA FEDERASYONU	06.12.2024",
        height=68,
        help="Excel'den 3 hücreyi (GTİP, Ülke, Tarih) kopyalayıp yapıştırın"
    )

    # Otomatik dönüşüm
    gtip = st.session_state.get("_gtip", "")
    ulke = st.session_state.get("_ulke", "")
    tarih = st.session_state.get("_tarih", "")

    if yapistir.strip():
        parcalar = yapistir.strip().split("\t")
        if len(parcalar) >= 3:
            gtip_ham  = parcalar[0].strip()
            ulke_ham  = parcalar[1].strip()
            tarih_ham = parcalar[2].strip()

            gtip  = gtip_cevir(gtip_ham)
            ulke  = ulke_cevir(ulke_ham)
            # Tarih: 06.12.2024 → 06-12-2024
            tarih = tarih_ham.replace(".", "-").replace("/", "-")

            # Dönüşüm önizleme
            st.markdown(f"""
            <div style='background:#f0fdf4;border:1px solid #86efac;border-radius:6px;
                        padding:10px 14px;font-family:JetBrains Mono,monospace;font-size:12px;
                        line-height:2;margin:4px 0 8px;'>
                <span style='color:#4b5563;'>GTİP :</span> <b style='color:#166534;'>{gtip}</b><br>
                <span style='color:#4b5563;'>Ülke :</span> <b style='color:#166534;'>{ulke}</b>
                <span style='color:#9ca3af;font-size:11px;'> ({ulke_ham})</span><br>
                <span style='color:#4b5563;'>Tarih:</span> <b style='color:#166534;'>{tarih}</b>
            </div>
            """, unsafe_allow_html=True)
        elif len(parcalar) == 1 and parcalar[0]:
            st.warning("3 hücreyi birlikte seçip kopyalayın (GTİP + Ülke + Tarih)")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    sorgula = st.button("🔍  Sorgula", use_container_width=True)

    if st.session_state.pdf_bytes:
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        st.download_button(
            label="📄  PDF İndir",
            data=st.session_state.pdf_bytes,
            file_name=f"TARIC_{st.session_state.gtip_son}_{st.session_state.ulke_son}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    if st.button("✕  Temizle", use_container_width=True):
        st.session_state.page_html  = None
        st.session_state.pdf_bytes  = None
        st.session_state.durum      = ""
        st.session_state.sorgulandı = False
        st.rerun()

    if st.session_state.durum:
        st.markdown(f"<div class='durum-ok'>{st.session_state.durum}</div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size:11px;color:#888;line-height:2;'>
        <b style='color:#555;font-size:10px;letter-spacing:1px;'>KULLANIM</b><br>
        1 → GTİP, ülke, tarih gir<br>
        2 → Sorgula'ya bas<br>
        3 → Sağda sonucu incele<br>
        4 → Mavi linklere tıkla<br>
        5 → Uygunsa PDF İndir
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SORGU
# ══════════════════════════════════════════════════════════════════════════════
if sorgula:
    if not gtip.strip():
        with sol:
            st.error("GTİP kodu giriniz!")
    else:
        with sag:
            with st.spinner("⏳ TARIC sorgulanıyor..."):
                ulke_sembol = ulke_cevir(ulke)
                gtip_sorgu  = gtip_cevir(gtip)
                html_content, pdf_bytes, current_url, hata = taric_sorgula(gtip_sorgu, ulke_sembol, tarih)

            if hata:
                st.markdown(f"<div class='durum-hata'>❌ Hata: {hata}</div>", unsafe_allow_html=True)
            else:
                st.session_state.page_html  = html_temizle(html_content, "https://ec.europa.eu")
                st.session_state.pdf_bytes  = pdf_bytes
                st.session_state.sorgulandı = True
                st.session_state.gtip_son   = gtip
                st.session_state.ulke_son   = ulke
                st.session_state.durum      = f"✅ {gtip_sorgu} / {ulke_sembol}"
                st.session_state.gtip_son   = gtip_sorgu
                st.session_state.ulke_son   = ulke_sembol
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# SAĞ PANEL — CANLI HTML
# ══════════════════════════════════════════════════════════════════════════════
with sag:
    if st.session_state.page_html:
        st.markdown(f"""
        <div style='display:flex;align-items:center;justify-content:space-between;
                    padding:10px 16px;background:#1a1a1a;border-radius:6px 6px 0 0;'>
            <div style='font-family:JetBrains Mono,monospace;font-size:12px;color:#c8b560;font-weight:700;'>
                🛃 TARIC — {st.session_state.gtip_son} / {st.session_state.ulke_son}
            </div>
            <div style='font-size:11px;color:#666;'>Mavi linklere ve ok işaretlerine tıklayabilirsiniz</div>
        </div>
        """, unsafe_allow_html=True)

        # Canlı HTML iframe olarak render et — tıklanabilir!
        st.components.v1.html(
            st.session_state.page_html,
            height=820,
            scrolling=True,
        )

    else:
        st.markdown("""
        <div style='display:flex;flex-direction:column;align-items:center;
                    justify-content:center;min-height:75vh;text-align:center;
                    background:white;border-radius:8px;border:1px dashed #d0ccc4;'>
            <div style='font-size:64px;opacity:0.12;margin-bottom:20px;'>🛃</div>
            <div style='font-size:17px;font-weight:700;color:#bbb;margin-bottom:8px;'>
                Sorgu Bekleniyor
            </div>
            <div style='font-size:13px;color:#ccc;line-height:1.8;'>
                Sol panelden GTİP, ülke ve tarihi girin<br>
                Sorgula'ya basın — TARIC sonucu burada görünür<br>
                Mavi linklere ve ▶ ok işaretlerine tıklayabilirsiniz
            </div>
        </div>
        """, unsafe_allow_html=True)

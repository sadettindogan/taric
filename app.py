import streamlit as st
from playwright.sync_api import sync_playwright
from pypdf import PdfWriter
import io
import base64
import time

# ─── SAYFA AYARI ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TARIC Sorgu",
    page_icon="🛃",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@400;600;700;800&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background: #f5f3ef;
    font-family: 'Syne', sans-serif;
    color: #1a1a1a;
}
[data-testid="stAppViewContainer"] > .main > div { padding-top: 0 !important; }
section[data-testid="stSidebar"] { display: none; }
header { display: none !important; }

/* Sol panel */
.sol-panel {
    background: #1a1a1a;
    min-height: 100vh;
    padding: 32px 24px;
    border-right: 3px solid #c8b560;
}

/* Input alanları */
[data-testid="stTextInput"] input {
    background: #f5f3ef !important;
    border: 2px solid #d4c97a !important;
    border-radius: 4px !important;
    color: #1a1a1a !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    padding: 10px 14px !important;
    transition: border-color 0.2s !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #c8b560 !important;
    box-shadow: 0 0 0 3px rgba(200,181,96,0.2) !important;
}
[data-testid="stTextInput"] label {
    color: #a0a0a0 !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: 2px !important;
    text-transform: uppercase !important;
    font-family: 'Syne', sans-serif !important;
}

/* Butonlar */
.stButton > button {
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: 13px !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    border-radius: 4px !important;
    padding: 12px 0 !important;
    width: 100% !important;
    transition: all 0.2s !important;
    border: 2px solid transparent !important;
}

/* Sorgula butonu — altın */
div[data-testid="column"]:nth-child(1) .stButton > button,
.btn-sorgula .stButton > button {
    background: #c8b560 !important;
    color: #1a1a1a !important;
    border-color: #c8b560 !important;
}
div[data-testid="column"]:nth-child(1) .stButton > button:hover {
    background: #d4c97a !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(200,181,96,0.4) !important;
}

/* PDF butonu — kırmızı */
.btn-pdf .stButton > button {
    background: #c0392b !important;
    color: white !important;
    border-color: #c0392b !important;
}
.btn-pdf .stButton > button:hover {
    background: #e74c3c !important;
    transform: translateY(-1px) !important;
}

/* Temizle butonu — şeffaf */
.btn-temizle .stButton > button {
    background: transparent !important;
    color: #666 !important;
    border-color: #444 !important;
    font-size: 11px !important;
}
.btn-temizle .stButton > button:hover {
    border-color: #c8b560 !important;
    color: #c8b560 !important;
}

/* Screenshot container */
.screenshot-box {
    background: white;
    border: 2px solid #e0ddd5;
    border-radius: 8px;
    overflow: hidden;
    margin-top: 16px;
}
.screenshot-box img {
    width: 100%;
    display: block;
}

/* Durum badge */
.durum-ok      { background:#e6f4ea; color:#2e7d32; border:2px solid #66bb6a; border-radius:6px; padding:10px 16px; font-weight:700; font-size:13px; margin:8px 0; }
.durum-hata    { background:#fdecea; color:#c62828; border:2px solid #ef9a9a; border-radius:6px; padding:10px 16px; font-weight:700; font-size:13px; margin:8px 0; }
.durum-bekle   { background:#fff8e1; color:#f57f17; border:2px solid #ffe082; border-radius:6px; padding:10px 16px; font-weight:700; font-size:13px; margin:8px 0; }

/* Divider */
hr { border-color: #333 !important; margin: 20px 0 !important; }

/* Scrollable screenshot */
.img-scroll {
    max-height: 75vh;
    overflow-y: auto;
    border: 2px solid #e0ddd5;
    border-radius: 8px;
    background: white;
}
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ─────────────────────────────────────────────────────────────
for k, v in {
    "screenshot": None,
    "pdf_bytes": None,
    "durum": "",
    "sorgulandı": False,
    "sorgu_url": "",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── TARIC SORGU FONKSİYONU ───────────────────────────────────────────────────
def taric_sorgula(gtip, ulke, tarih):
    """
    Headless Chromium ile TARIC'i sorgular.
    Sayfanın tam screenshot'ını ve PDF'ini döner.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path="/usr/bin/chromium",
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            context = browser.new_context(
                viewport={"width": 1400, "height": 900}
            )
            page = context.new_page()

            url = "https://ec.europa.eu/taxation_customs/dds2/taric/taric_consultation.jsp?Lang=en"
            page.goto(url, wait_until="networkidle", timeout=30000)

            # GTİP kodunu doldur
            page.fill("#taricCode", gtip.strip())

            # Ülke seç
            ulke_temiz = ulke.strip()
            if ulke_temiz:
                try:
                    page.select_option("#taricArea", ulke_temiz)
                except:
                    pass

            # Tarihi doldur
            tarih_temiz = tarih.strip()
            if tarih_temiz:
                page.evaluate(f"document.querySelector('#SimDatePic').value = '{tarih_temiz}'")

            # Sorgula
            page.click("button[value='Retrieve Measures']")
            page.wait_for_load_state("networkidle", timeout=20000)

            # Zoom %75
            page.evaluate("document.body.style.zoom = '0.8'")
            time.sleep(1)

            # Screenshot — tam sayfa
            screenshot = page.screenshot(full_page=True)

            # PDF
            pdf_bytes = page.pdf(format="A4", print_background=True, scale=0.8)

            # URL kaydet
            st.session_state.sorgu_url = page.url

            browser.close()
            return screenshot, pdf_bytes, None

    except Exception as e:
        return None, None, str(e)

# ─── LAYOUT ───────────────────────────────────────────────────────────────────
sol, sag = st.columns([1, 2.5], gap="small")

# ══════════════════════════════════════════════════════════════════════════════
# SOL PANEL
# ══════════════════════════════════════════════════════════════════════════════
with sol:
    st.markdown("""
    <div style='padding-bottom:20px;border-bottom:1px solid #333;margin-bottom:24px;'>
        <div style='font-family:Syne,sans-serif;font-size:28px;font-weight:800;
                    color:#c8b560;letter-spacing:-0.5px;'>🛃 TARIC</div>
        <div style='font-size:11px;color:#666;letter-spacing:2px;text-transform:uppercase;margin-top:2px;'>
            Gümrük Tarife Sorgulama
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='color:#888;font-size:11px;letter-spacing:2px;margin-bottom:16px;'>GİRİŞ PARAMETRELERİ</div>", unsafe_allow_html=True)

    gtip  = st.text_input("GTİP Kodu", placeholder="7207121000", help="TARIC sorgu kodu (10 hane)")
    ulke  = st.text_input("Ülke Kodu", placeholder="RU", help="2 harfli ülke kodu (RU, DE, CN...)")
    tarih = st.text_input("Tarih", placeholder="06-12-2024", help="DD-MM-YYYY formatında")

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # Sorgula butonu
    sorgula = st.button("🔍  Sorgula", use_container_width=True)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # PDF Al butonu
    if st.session_state.pdf_bytes:
        st.markdown("<div class='btn-pdf'>", unsafe_allow_html=True)
        st.download_button(
            label="📄  PDF İndir",
            data=st.session_state.pdf_bytes,
            file_name=f"TARIC_{gtip}_{ulke}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # Temizle
    st.markdown("<div class='btn-temizle'>", unsafe_allow_html=True)
    if st.button("✕  Temizle", use_container_width=True):
        st.session_state.screenshot  = None
        st.session_state.pdf_bytes   = None
        st.session_state.durum       = ""
        st.session_state.sorgulandı  = False
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # Durum
    if st.session_state.durum:
        st.markdown(f"<div class='durum-ok'>{st.session_state.durum}</div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # Bilgi kutusu
    st.markdown("""
    <div style='font-size:11px;color:#555;line-height:2;'>
        <div style='color:#888;letter-spacing:2px;font-size:10px;margin-bottom:8px;'>KULLANIM</div>
        1 → GTİP, ülke, tarihi girin<br>
        2 → <b style='color:#c8b560;'>Sorgula</b>'ya basın<br>
        3 → Sonucu sağda inceleyin<br>
        4 → Uygunsa <b style='color:#c0392b;'>PDF İndir</b>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SORGU İŞLEMİ
# ══════════════════════════════════════════════════════════════════════════════
if sorgula:
    if not gtip.strip():
        st.error("GTİP kodu giriniz!")
    else:
        with sag:
            with st.spinner("⏳ TARIC sorgulanıyor..."):
                screenshot, pdf_bytes, hata = taric_sorgula(gtip, ulke, tarih)

            if hata:
                st.markdown(f"<div class='durum-hata'>❌ Hata: {hata}</div>", unsafe_allow_html=True)
                st.session_state.durum = ""
            else:
                st.session_state.screenshot = screenshot
                st.session_state.pdf_bytes  = pdf_bytes
                st.session_state.sorgulandı = True
                st.session_state.durum      = f"✅ Sorgu tamamlandı — {gtip} / {ulke}"
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# SAĞ PANEL — SCREENSHOT
# ══════════════════════════════════════════════════════════════════════════════
with sag:
    if st.session_state.screenshot:
        # Başlık bar
        st.markdown(f"""
        <div style='display:flex;align-items:center;justify-content:space-between;
                    padding:12px 16px;background:#1a1a1a;border-radius:8px 8px 0 0;
                    margin-bottom:0;'>
            <div style='font-family:JetBrains Mono,monospace;font-size:12px;color:#c8b560;'>
                🛃 TARIC Measures — {gtip or st.session_state.durum.split("/")[0].replace("✅ Sorgu tamamlandı — ","")}
            </div>
            <div style='font-size:11px;color:#555;'>
                Sayfayı aşağı kaydırarak inceleyin
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Screenshot göster — base64
        img_b64 = base64.b64encode(st.session_state.screenshot).decode()
        st.markdown(f"""
        <div class='img-scroll'>
            <img src='data:image/png;base64,{img_b64}' style='width:100%;display:block;'/>
        </div>
        """, unsafe_allow_html=True)

    elif not st.session_state.sorgulandı:
        # Boş durum
        st.markdown("""
        <div style='display:flex;flex-direction:column;align-items:center;justify-content:center;
                    min-height:60vh;text-align:center;'>
            <div style='font-size:72px;margin-bottom:24px;opacity:0.15;'>🛃</div>
            <div style='font-size:18px;font-weight:700;color:#ccc;margin-bottom:8px;'>
                Sorgu Bekleniyor
            </div>
            <div style='font-size:13px;color:#666;line-height:1.8;'>
                Sol panelden GTİP, ülke ve tarihi girin<br>
                Sorgula'ya basın — TARIC sonucu burada görünür
            </div>
        </div>
        """, unsafe_allow_html=True)

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
[data-testid="stAppViewContainer"] > .main > div {
    padding-top: 0 !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    max-width: 100% !important;
}
section[data-testid="stSidebar"] { display: none; }
header { display: none !important; }
.block-container { padding: 12px 16px !important; max-width: 100% !important; }

/* Input alanları */
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

/* Butonlar */
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

/* Sorgula — altın */
div[data-testid="column"]:nth-child(1) .stButton > button {
    background: #c8b560 !important;
    color: #1a1a1a !important;
}
div[data-testid="column"]:nth-child(1) .stButton > button:hover {
    background: #d4c97a !important;
    box-shadow: 0 4px 12px rgba(200,181,96,0.4) !important;
}

/* Durum */
.durum-ok   { background:#e6f4ea; color:#2e7d32; border:1px solid #66bb6a; border-radius:6px; padding:8px 12px; font-weight:700; font-size:12px; margin:6px 0; }
.durum-hata { background:#fdecea; color:#c62828; border:1px solid #ef9a9a; border-radius:6px; padding:8px 12px; font-weight:700; font-size:12px; margin:6px 0; }

/* Scrollable screenshot */
.img-scroll {
    max-height: 88vh;
    overflow-y: auto;
    overflow-x: hidden;
    border: 1px solid #d0ccc4;
    border-radius: 6px;
    background: white;
    box-shadow: 0 2px 16px rgba(0,0,0,0.08);
}
.img-scroll img {
    width: 100%;
    display: block;
    image-rendering: -webkit-optimize-contrast;
}

hr { border-color: #e0ddd5 !important; margin: 12px 0 !important; }
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ─────────────────────────────────────────────────────────────
for k, v in {
    "screenshot": None,
    "pdf_bytes": None,
    "durum": "",
    "sorgulandı": False,
    "gtip_son": "",
    "ulke_son": "",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── TARIC SORGU FONKSİYONU ───────────────────────────────────────────────────
def taric_sorgula(gtip, ulke, tarih):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path="/usr/bin/chromium",
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            # Geniş viewport + yüksek DPI → yazılar net ve okunabilir
            context = browser.new_context(
                viewport={"width": 1600, "height": 1000},
                device_scale_factor=1.5,
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

            # Tam sayfa yüksek kalite screenshot
            screenshot = page.screenshot(full_page=True, type="png")

            # PDF — orijinal boyut
            pdf_bytes = page.pdf(format="A4", print_background=True)

            browser.close()
            return screenshot, pdf_bytes, None

    except Exception as e:
        return None, None, str(e)

# ─── LAYOUT: Sol dar (0.55), Sağ çok geniş (2.45) ────────────────────────────
sol, sag = st.columns([0.55, 2.45], gap="medium")

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

    gtip  = st.text_input("GTİP Kodu", placeholder="7207121000")
    ulke  = st.text_input("Ülke Kodu", placeholder="RU")
    tarih = st.text_input("Tarih", placeholder="06-12-2024")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    sorgula = st.button("🔍  Sorgula", use_container_width=True)

    # PDF butonu
    if st.session_state.pdf_bytes:
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        st.download_button(
            label="📄  PDF İndir",
            data=st.session_state.pdf_bytes,
            file_name=f"TARIC_{st.session_state.gtip_son}_{st.session_state.ulke_son}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    # Temizle
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    if st.button("✕  Temizle", use_container_width=True):
        st.session_state.screenshot = None
        st.session_state.pdf_bytes  = None
        st.session_state.durum      = ""
        st.session_state.sorgulandı = False
        st.rerun()

    # Durum mesajı
    if st.session_state.durum:
        st.markdown(f"<div class='durum-ok'>{st.session_state.durum}</div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown("""
    <div style='font-size:11px;color:#888;line-height:2;'>
        <b style='color:#555;font-size:10px;letter-spacing:1px;'>KULLANIM</b><br>
        1 → GTİP, ülke, tarih gir<br>
        2 → Sorgula'ya bas<br>
        3 → Sağda sonucu incele<br>
        4 → Uygunsa PDF İndir
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SORGU İŞLEMİ
# ══════════════════════════════════════════════════════════════════════════════
if sorgula:
    if not gtip.strip():
        with sol:
            st.error("GTİP kodu giriniz!")
    else:
        with sag:
            with st.spinner("⏳ TARIC sorgulanıyor, lütfen bekleyin..."):
                screenshot, pdf_bytes, hata = taric_sorgula(gtip, ulke, tarih)

            if hata:
                st.markdown(f"<div class='durum-hata'>❌ Hata: {hata}</div>", unsafe_allow_html=True)
            else:
                st.session_state.screenshot = screenshot
                st.session_state.pdf_bytes  = pdf_bytes
                st.session_state.sorgulandı = True
                st.session_state.gtip_son   = gtip
                st.session_state.ulke_son   = ulke
                st.session_state.durum      = f"✅ {gtip} / {ulke}"
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# SAĞ PANEL — SCREENSHOT
# ══════════════════════════════════════════════════════════════════════════════
with sag:
    if st.session_state.screenshot:
        # Başlık
        st.markdown(f"""
        <div style='display:flex;align-items:center;justify-content:space-between;
                    padding:10px 16px;background:#1a1a1a;border-radius:6px 6px 0 0;'>
            <div style='font-family:JetBrains Mono,monospace;font-size:12px;color:#c8b560;font-weight:700;'>
                🛃 TARIC — {st.session_state.gtip_son} / {st.session_state.ulke_son}
            </div>
            <div style='font-size:11px;color:#666;'>↕ Kaydırarak inceleyin</div>
        </div>
        """, unsafe_allow_html=True)

        img_b64 = base64.b64encode(st.session_state.screenshot).decode()
        st.markdown(f"""
        <div class='img-scroll'>
            <img src='data:image/png;base64,{img_b64}'/>
        </div>
        """, unsafe_allow_html=True)

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
                Sorgula'ya basın — TARIC sonucu burada görünür
            </div>
        </div>
        """, unsafe_allow_html=True)

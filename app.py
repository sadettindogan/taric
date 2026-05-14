import streamlit as st
from playwright.sync_api import sync_playwright
import json, os, time

# ─── ÜLKE + GTİP DÖNÜŞÜM ─────────────────────────────────────────────────────
@st.cache_data
def ulke_listesi_yukle():
    json_yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ulkeler.json")
    if os.path.exists(json_yol):
        with open(json_yol, encoding="utf-8") as f:
            return json.load(f)
    return {}

ULKELER = ulke_listesi_yukle()

def ulke_cevir(girdi):
    girdi = girdi.strip()
    if not girdi: return ""
    if len(girdi) <= 3 and girdi.isalpha(): return girdi.upper()
    anahtar = girdi.upper()
    if anahtar in ULKELER: return ULKELER[anahtar]
    for k, v in ULKELER.items():
        if k.startswith(anahtar): return v
    return girdi.upper()

def gtip_cevir(girdi):
    temiz = str(girdi).replace(".", "").replace(" ", "").strip()
    if len(temiz) == 12:
        temiz = temiz[:-1]
    return temiz

def parse_yapistir(ham):
    """Tab veya satır satır yapıştırılan 3 veriyi parse eder."""
    ham = ham.strip()
    if "\t" in ham:
        parcalar = [p.strip() for p in ham.split("\t") if p.strip()]
    else:
        parcalar = [p.strip() for p in ham.splitlines() if p.strip()]
    return parcalar

# ─── SAYFA AYARI ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="TARIC Sorgu", page_icon="🛃", layout="wide",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@400;600;700;800&display=swap');
html, body, [data-testid="stAppViewContainer"] { background:#f5f3ef; font-family:'Syne',sans-serif; color:#1a1a1a; }
section[data-testid="stSidebar"] { display:none; }
header { display:none !important; }
.block-container { padding:12px 16px !important; max-width:100% !important; }
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea {
    background:white !important; border:1px solid #d4c97a !important; border-radius:4px !important;
    color:#1a1a1a !important; font-family:'JetBrains Mono',monospace !important;
    font-size:13px !important; font-weight:600 !important; padding:8px 10px !important;
}
[data-testid="stTextInput"] input:focus,[data-testid="stTextArea"] textarea:focus {
    border-color:#c8b560 !important; box-shadow:0 0 0 2px rgba(200,181,96,0.2) !important;
}
[data-testid="stTextInput"] label,[data-testid="stTextArea"] label {
    color:#888 !important; font-size:10px !important; font-weight:700 !important;
    letter-spacing:1.5px !important; text-transform:uppercase !important;
}
.stButton > button {
    font-family:'Syne',sans-serif !important; font-weight:700 !important;
    font-size:12px !important; letter-spacing:1px !important; text-transform:uppercase !important;
    border-radius:4px !important; padding:10px 0 !important; width:100% !important;
    transition:all 0.2s !important; border:none !important; color:white !important;
}
.durum-ok   { background:#e6f4ea; color:#2e7d32; border:1px solid #66bb6a; border-radius:6px; padding:8px 12px; font-weight:700; font-size:12px; margin:6px 0; }
.durum-hata { background:#fdecea; color:#c62828; border:1px solid #ef9a9a; border-radius:6px; padding:8px 12px; font-weight:700; font-size:12px; margin:6px 0; }
.onizleme   { background:#f0fdf4; border:1px solid #86efac; border-radius:6px; padding:10px 14px;
              font-family:'JetBrains Mono',monospace; font-size:12px; line-height:2; margin:4px 0 8px; }
hr { border-color:#e0ddd5 !important; margin:12px 0 !important; }
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ─────────────────────────────────────────────────────────────
for k, v in {
    "page_html":  None,
    "pdf_bytes":  None,
    "durum":      "",
    "sorgulandı": False,
    "gtip_son":   "",
    "ulke_son":   "",
    "tarih_son":  "",
    "gtip_kirp":  "",
    # Parse edilen değerler — buton basılınca bunlar kullanılır
    "p_gtip":     "",
    "p_ulke":     "",
    "p_tarih":    "",
    "p_ulke_ham": "",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── TARIC SORGU ──────────────────────────────────────────────────────────────
def taric_sorgula(gtip, ulke, tarih):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path="/usr/bin/chromium",
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            context = browser.new_context(viewport={"width": 1400, "height": 900})
            page = context.new_page()

            url = "https://ec.europa.eu/taxation_customs/dds2/taric/taric_consultation.jsp?Lang=en"
            page.goto(url, wait_until="networkidle", timeout=30000)

            page.fill("#taricCode", gtip.strip())

            if ulke.strip():
                try:
                    page.select_option("#taricArea", ulke.strip())
                except:
                    pass

            if tarih.strip():
                page.evaluate(
                    "(t) => { document.querySelector('#SimDatePic').value = t; }",
                    tarih.strip()
                )

            page.click("button[value='Retrieve Measures']")
            page.wait_for_load_state("networkidle", timeout=20000)
            time.sleep(1.5)

            html_content = page.content()
            pdf_bytes    = page.pdf(format="A4", print_background=True)
            browser.close()
            return html_content, pdf_bytes, None

    except Exception as e:
        return None, None, str(e)

def html_temizle(html):
    base_tag = '<base href="https://ec.europa.eu" target="_blank">'
    stil = """<style>
        body { font-size:15px !important; line-height:1.7 !important; font-family:Arial,sans-serif !important; }
        table { font-size:14px !important; }
        td,th { padding:6px 10px !important; }
        a { font-size:14px !important; }
    </style>"""
    if "<head>" in html:
        html = html.replace("<head>", f"<head>{base_tag}{stil}", 1)
    else:
        html = base_tag + stil + html
    return html

# ─── LAYOUT ───────────────────────────────────────────────────────────────────
sol, sag = st.columns([0.5, 2.5], gap="medium")

with sol:
    st.markdown("""
    <div style='padding-bottom:14px;border-bottom:2px solid #c8b560;margin-bottom:16px;'>
        <div style='font-size:22px;font-weight:800;color:#1a1a1a;'>🛃 TARIC</div>
        <div style='font-size:10px;color:#999;letter-spacing:2px;text-transform:uppercase;'>Gümrük Tarife Sorgulama</div>
    </div>
    """, unsafe_allow_html=True)

    # ── YAPISTIR KUTUSU ──────────────────────────────────────────────────────
    yapistir = st.text_area(
        "Excel'den Yapıştır",
        placeholder="72.07.11.14.00.00\tPAKİSTAN\t11.12.2024\n(veya alt alta 3 satır)",
        height=90,
    )

    # Parse — her rerun'da yapistir doluysa session'a kaydet
    if yapistir.strip():
        parcalar = parse_yapistir(yapistir)
        if len(parcalar) >= 3:
            gtip_ham  = parcalar[0]
            ulke_ham  = parcalar[1]
            tarih_ham = parcalar[2]

            # Kırpma modundaysa kırpılmış kodu kullan, değilse dönüştür
            p_gtip  = st.session_state.gtip_kirp if st.session_state.gtip_kirp else gtip_cevir(gtip_ham)
            p_ulke  = ulke_cevir(ulke_ham)
            p_tarih = tarih_ham.replace(".", "-").replace("/", "-")

            # Session'a kaydet — buton basıldığında buradan okunur
            st.session_state.p_gtip    = p_gtip
            st.session_state.p_ulke    = p_ulke
            st.session_state.p_tarih   = p_tarih
            st.session_state.p_ulke_ham = ulke_ham

            kirp_notu = " ✂️" if st.session_state.gtip_kirp else ""
            st.markdown(f"""
            <div class='onizleme'>
                <span style='color:#4b5563;'>GTİP :</span> <b style='color:#166534;'>{p_gtip}</b>{kirp_notu}<br>
                <span style='color:#4b5563;'>Ülke :</span> <b style='color:#166534;'>{p_ulke}</b>
                <span style='color:#9ca3af;font-size:11px;'> ({ulke_ham})</span><br>
                <span style='color:#4b5563;'>Tarih:</span> <b style='color:#166534;'>{p_tarih}</b>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.warning("3 veri giriniz: GTİP, Ülke, Tarih")

    # ── SORGULA ──────────────────────────────────────────────────────────────
    if st.button("🔍  Sorgula", use_container_width=True,
                 disabled=not bool(st.session_state.p_gtip)):
        gtip  = st.session_state.p_gtip
        ulke  = st.session_state.p_ulke
        tarih = st.session_state.p_tarih

        with sag:
            with st.spinner(f"⏳ Sorgulanıyor: {gtip} / {ulke}"):
                html_content, pdf_bytes, hata = taric_sorgula(gtip, ulke, tarih)

            if hata:
                st.markdown(f"<div class='durum-hata'>❌ {hata}</div>", unsafe_allow_html=True)
            else:
                st.session_state.page_html  = html_temizle(html_content)
                st.session_state.pdf_bytes  = pdf_bytes
                st.session_state.sorgulandı = True
                st.session_state.gtip_son   = gtip
                st.session_state.ulke_son   = ulke
                st.session_state.tarih_son  = tarih
                st.session_state.durum      = f"✅ {gtip} / {ulke}"
                st.rerun()

    # ── PDF İNDİR ────────────────────────────────────────────────────────────
    if st.session_state.pdf_bytes:
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        st.download_button(
            label="📄  PDF İndir",
            data=st.session_state.pdf_bytes,
            file_name=f"TARIC_{st.session_state.gtip_son}_{st.session_state.ulke_son}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    # ── SONDAN 1 RAKAM SİL ───────────────────────────────────────────────────
    if st.session_state.sorgulandı:
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        if st.button("✂️  Sondan 1 Rakam Sil", use_container_width=True):
            mevcut = st.session_state.gtip_son
            if len(mevcut) > 4:
                yeni_gtip = mevcut[:-1]
                st.session_state.gtip_kirp = yeni_gtip
                st.session_state.p_gtip    = yeni_gtip

                with sag:
                    with st.spinner(f"⏳ Sorgulanıyor: {yeni_gtip}"):
                        html_content, pdf_bytes, hata = taric_sorgula(
                            yeni_gtip,
                            st.session_state.ulke_son,
                            st.session_state.tarih_son
                        )
                    if not hata:
                        st.session_state.page_html = html_temizle(html_content)
                        st.session_state.pdf_bytes = pdf_bytes
                        st.session_state.gtip_son  = yeni_gtip
                        st.session_state.durum     = f"✅ {yeni_gtip} / {st.session_state.ulke_son} ✂️"
                    else:
                        st.error(f"Hata: {hata}")
                st.rerun()

    # ── TEMİZLE ──────────────────────────────────────────────────────────────
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    if st.button("✕  Temizle", use_container_width=True):
        for k in ["page_html","pdf_bytes","durum","sorgulandı",
                  "gtip_son","ulke_son","tarih_son","gtip_kirp",
                  "p_gtip","p_ulke","p_tarih","p_ulke_ham"]:
            st.session_state[k] = None if k in ["page_html","pdf_bytes"] else ""
        st.session_state.sorgulandı = False
        st.rerun()

    if st.session_state.durum:
        st.markdown(f"<div class='durum-ok'>{st.session_state.durum}</div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size:11px;color:#888;line-height:2;'>
        <b style='color:#555;font-size:10px;letter-spacing:1px;'>KULLANIM</b><br>
        1 → Excel'den 3 hücreyi yapıştır<br>
        2 → Önizlemeyi kontrol et<br>
        3 → Sorgula'ya bas<br>
        4 → Sağda incele, linklere tıkla<br>
        5 → PDF İndir veya ✂️ Kırp
    </div>
    """, unsafe_allow_html=True)

# ─── SAĞ PANEL ────────────────────────────────────────────────────────────────
with sag:
    if st.session_state.page_html:
        st.markdown(f"""
        <div style='display:flex;align-items:center;justify-content:space-between;
                    padding:10px 16px;background:#1a1a1a;border-radius:6px 6px 0 0;'>
            <div style='font-family:JetBrains Mono,monospace;font-size:12px;color:#c8b560;font-weight:700;'>
                🛃 {st.session_state.gtip_son} / {st.session_state.ulke_son}
            </div>
            <div style='font-size:11px;color:#666;'>Mavi linklere ve ▶ ok işaretlerine tıklayabilirsiniz</div>
        </div>
        """, unsafe_allow_html=True)
        st.components.v1.html(st.session_state.page_html, height=820, scrolling=True)
    else:
        st.markdown("""
        <div style='display:flex;flex-direction:column;align-items:center;justify-content:center;
                    min-height:75vh;text-align:center;background:white;
                    border-radius:8px;border:1px dashed #d0ccc4;'>
            <div style='font-size:64px;opacity:0.12;margin-bottom:20px;'>🛃</div>
            <div style='font-size:17px;font-weight:700;color:#bbb;margin-bottom:8px;'>Sorgu Bekleniyor</div>
            <div style='font-size:13px;color:#ccc;line-height:1.8;'>
                Excel'den GTİP, Ülke ve Tarihi kopyalayıp yapıştırın<br>
                Sorgula'ya basın — TARIC sonucu burada görünür
            </div>
        </div>
        """, unsafe_allow_html=True)

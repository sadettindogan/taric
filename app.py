import streamlit as st
from playwright.sync_api import sync_playwright
import json, os, time

# ─── YARDIMCI FONKSİYONLAR ───────────────────────────────────────────────────
@st.cache_data
def ulke_listesi_yukle():
    json_yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ulkeler.json")
    if os.path.exists(json_yol):
        with open(json_yol, encoding="utf-8") as f:
            return json.load(f)
    return {}

ULKELER = ulke_listesi_yukle()

def ulke_cevir(girdi):
    """Türkçe ülke adı veya sembol → 2 harfli sembol"""
    girdi = girdi.strip()
    if not girdi: return ""
    if len(girdi) <= 3 and girdi.isalpha(): return girdi.upper()
    anahtar = girdi.upper()
    if anahtar in ULKELER: return ULKELER[anahtar]
    for k, v in ULKELER.items():
        if k.startswith(anahtar): return v
    return girdi.upper()

def gtip_cevir(girdi):
    """
    72.07.11.14.00.00 → 72071114000 (noktasız, 11 hane)
    12 haneli gelirse son haneyi sil → 11 hane
    """
    temiz = str(girdi).replace(".", "").replace(" ", "").strip()
    if len(temiz) == 12:
        temiz = temiz[:-1]
    return temiz

def parse_yapistir(ham):
    """
    Excel'den kopyalanan 3 veriyi parse et.
    Desteklenen formatlar:
      - Tab ile ayrılmış tek satır: GTİP\tÜLKE\tTARİH
      - Her biri ayrı satırda: GTİP\nÜLKE\nTARİH
      - 2. satırda ülke+tarih boşlukla: GTİP\nÜLKE  TARİH
    """
    ham = ham.strip()

    # Tab varsa direkt split
    if "\t" in ham:
        return [p.strip() for p in ham.split("\t") if p.strip()]

    satirlar = [s.strip() for s in ham.splitlines() if s.strip()]

    # 3 ayrı satır
    if len(satirlar) >= 3:
        return satirlar[:3]

    # 2 satır — ikincisinde ülke + tarih boşlukla ayrılmış olabilir
    if len(satirlar) == 2:
        gtip = satirlar[0]
        kalan = satirlar[1].split()
        # Tarih genellikle son parça (dd.mm.yyyy veya dd-mm-yyyy)
        import re
        tarih_pattern = re.compile(r'\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}')
        tarih = ""
        ulke_parcalar = []
        for p in kalan:
            if tarih_pattern.match(p):
                tarih = p
            else:
                ulke_parcalar.append(p)
        ulke = " ".join(ulke_parcalar)
        if gtip and ulke and tarih:
            return [gtip, ulke, tarih]

    return satirlar

def tarih_url_formatla(tarih):
    """DD-MM-YYYY → YYYYMMDD"""
    from datetime import datetime
    for fmt in ("%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(tarih.strip(), fmt).strftime("%Y%m%d")
        except:
            continue
    return tarih.strip().replace("-", "").replace(".", "")

def taric_sorgula(gtip, ulke, tarih):
    try:
        tarih_fmt = tarih_url_formatla(tarih)
        # Direkt sonuç URL — form submit yok, hata yok
        url = (
            f"https://ec.europa.eu/taxation_customs/dds2/taric/measures.jsp"
            f"?Lang=en"
            f"&SimDate={tarih_fmt}"
            f"&Area={ulke.strip()}"
            f"&MeasType=&StartPub=&EndPub=&MeasText=&GoodsText=&op="
            f"&Taric={gtip.strip()}"
            f"&AdditionalCode=&search_text=goods&textSearch=&LangDescr=en&OrderNum="
        )

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path="/usr/bin/chromium",
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            )
            context = browser.new_context(viewport={"width": 1400, "height": 900})
            page = context.new_page()

            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(1.5)

            html_content = page.content()
            pdf_bytes = page.pdf(format="A4", print_background=True)
            browser.close()
            return html_content, pdf_bytes, None
    except Exception as e:
        return None, None, str(e)

def html_temizle(html):
    ek = '<base href="https://ec.europa.eu" target="_blank"><style>body{font-size:15px!important;line-height:1.7!important;font-family:Arial,sans-serif!important}table{font-size:14px!important}td,th{padding:6px 10px!important}</style>'
    if "<head>" in html:
        return html.replace("<head>", "<head>" + ek, 1)
    return ek + html

# ─── SAYFA AYARI ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="TARIC Sorgu", page_icon="🛃",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@400;600;700;800&display=swap');
html,body,[data-testid="stAppViewContainer"]{background:#f5f3ef;font-family:'Syne',sans-serif;color:#1a1a1a;}
section[data-testid="stSidebar"]{display:none;}
header{display:none!important;}
.block-container{padding:12px 16px!important;max-width:100%!important;}
[data-testid="stTextArea"] textarea{
    background:white!important;border:1px solid #d4c97a!important;border-radius:4px!important;
    color:#1a1a1a!important;font-family:'JetBrains Mono',monospace!important;
    font-size:13px!important;font-weight:600!important;padding:8px 10px!important;
}
[data-testid="stTextArea"] textarea:focus{border-color:#c8b560!important;box-shadow:0 0 0 2px rgba(200,181,96,0.2)!important;}
[data-testid="stTextArea"] label{color:#888!important;font-size:10px!important;font-weight:700!important;letter-spacing:1.5px!important;text-transform:uppercase!important;}
.stButton>button{
    font-family:'Syne',sans-serif!important;font-weight:700!important;font-size:12px!important;
    letter-spacing:1px!important;text-transform:uppercase!important;border-radius:4px!important;
    padding:10px 0!important;width:100%!important;transition:all 0.2s!important;border:none!important;
}
.btn-sorgula .stButton>button{background:#c8b560!important;color:#1a1a1a!important;}
.btn-sorgula .stButton>button:hover{background:#d4c97a!important;}
.btn-kirp .stButton>button{background:#d97706!important;color:white!important;}
.btn-kirp .stButton>button:hover{background:#b45309!important;}
.btn-temizle .stButton>button{background:#6b7280!important;color:white!important;}
.onizleme{background:#f0fdf4;border:1px solid #86efac;border-radius:6px;padding:10px 14px;font-family:'JetBrains Mono',monospace;font-size:12px;line-height:2;margin:4px 0 8px;}
.durum-ok{background:#e6f4ea;color:#2e7d32;border:1px solid #66bb6a;border-radius:6px;padding:8px 12px;font-weight:700;font-size:12px;margin:6px 0;}
.durum-hata{background:#fdecea;color:#c62828;border:1px solid #ef9a9a;border-radius:6px;padding:8px 12px;font-weight:700;font-size:12px;margin:6px 0;}
hr{border-color:#e0ddd5!important;margin:12px 0!important;}
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
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── LAYOUT ───────────────────────────────────────────────────────────────────
sol, sag = st.columns([0.5, 2.5], gap="medium")

with sol:
    st.markdown("""
    <div style='padding-bottom:14px;border-bottom:2px solid #c8b560;margin-bottom:16px;'>
        <div style='font-size:22px;font-weight:800;'>🛃 TARIC</div>
        <div style='font-size:10px;color:#999;letter-spacing:2px;text-transform:uppercase;'>Gümrük Tarife Sorgulama</div>
    </div>
    """, unsafe_allow_html=True)

    yapistir = st.text_area(
        "Excel'den Yapıştır",
        placeholder="72.07.11.14.00.00\tPAKİSTAN\t11.12.2024\n(veya 3 satır alt alta)",
        height=90,
        key="yapistir_kutu"
    )

    # Parse ve önizleme
    gtip_hazir = ulke_hazir = tarih_hazir = ""
    ulke_ham_goster = ""

    if yapistir.strip():
        parcalar = parse_yapistir(yapistir)
        if len(parcalar) >= 3:
            gtip_ham  = parcalar[0]
            ulke_ham  = parcalar[1]
            tarih_ham = parcalar[2]
            ulke_ham_goster = ulke_ham

            # Kırpma modundaysa kırpılmış kodu kullan
            gtip_hazir  = st.session_state.gtip_kirp if st.session_state.gtip_kirp else gtip_cevir(gtip_ham)
            ulke_hazir  = ulke_cevir(ulke_ham)
            tarih_hazir = tarih_ham.replace(".", "-").replace("/", "-")

            kirp_notu = " <span style='color:#d97706;'>✂️ kırpıldı</span>" if st.session_state.gtip_kirp else ""
            st.markdown(f"""
            <div class='onizleme'>
                <span style='color:#4b5563;'>GTİP :</span> <b style='color:#166534;'>{gtip_hazir}</b>{kirp_notu}<br>
                <span style='color:#4b5563;'>Ülke :</span> <b style='color:#166534;'>{ulke_hazir}</b>
                <span style='color:#9ca3af;font-size:11px;'> ({ulke_ham_goster})</span><br>
                <span style='color:#4b5563;'>Tarih:</span> <b style='color:#166534;'>{tarih_hazir}</b>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.warning("3 veri giriniz: GTİP · Ülke · Tarih")

    # Sorgula
    st.markdown("<div class='btn-sorgula'>", unsafe_allow_html=True)
    sorgula = st.button("🔍  Sorgula", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # PDF İndir
    if st.session_state.pdf_bytes:
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        st.download_button(
            label="📄  PDF İndir",
            data=st.session_state.pdf_bytes,
            file_name=f"TARIC_{st.session_state.gtip_son}_{st.session_state.ulke_son}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    # Sondan 1 Rakam Sil
    if st.session_state.sorgulandı:
        st.markdown("<div style='height:4px'></div><div class='btn-kirp'>", unsafe_allow_html=True)
        kirp = st.button("✂️  Sondan 1 Rakam Sil", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        kirp = False

    # Temizle
    st.markdown("<div style='height:4px'></div><div class='btn-temizle'>", unsafe_allow_html=True)
    temizle = st.button("✕  Temizle", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

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

# ─── BUTON İŞLEMLERİ ─────────────────────────────────────────────────────────
if sorgula:
    if not gtip_hazir:
        with sol:
            st.error("Önce veri yapıştırın!")
    else:
        with sag:
            with st.spinner(f"⏳ Sorgulanıyor: {gtip_hazir} / {ulke_hazir}"):
                html_content, pdf_bytes, hata = taric_sorgula(gtip_hazir, ulke_hazir, tarih_hazir)
            if hata:
                st.markdown(f"<div class='durum-hata'>❌ {hata}</div>", unsafe_allow_html=True)
            else:
                st.session_state.page_html  = html_temizle(html_content)
                st.session_state.pdf_bytes  = pdf_bytes
                st.session_state.sorgulandı = True
                st.session_state.gtip_son   = gtip_hazir
                st.session_state.ulke_son   = ulke_hazir
                st.session_state.tarih_son  = tarih_hazir
                st.session_state.gtip_kirp  = ""
                st.session_state.durum      = f"✅ {gtip_hazir} / {ulke_hazir}"
                st.rerun()

if kirp:
    mevcut = st.session_state.gtip_son
    if len(mevcut) > 4:
        yeni = mevcut[:-1]
        st.session_state.gtip_kirp = yeni
        with sag:
            with st.spinner(f"⏳ Sorgulanıyor: {yeni}"):
                html_content, pdf_bytes, hata = taric_sorgula(
                    yeni, st.session_state.ulke_son, st.session_state.tarih_son)
            if not hata:
                st.session_state.page_html = html_temizle(html_content)
                st.session_state.pdf_bytes = pdf_bytes
                st.session_state.gtip_son  = yeni
                st.session_state.durum     = f"✅ {yeni} / {st.session_state.ulke_son} ✂️"
            else:
                st.error(f"Hata: {hata}")
        st.rerun()

if temizle:
    for k in ["page_html","pdf_bytes","durum","sorgulandı",
              "gtip_son","ulke_son","tarih_son","gtip_kirp"]:
        st.session_state[k] = False if k == "sorgulandı" else (None if k in ["page_html","pdf_bytes"] else "")
    st.rerun()

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

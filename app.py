import streamlit as st
from playwright.sync_api import sync_playwright
import json, os, time, re

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

def tarih_cevir(girdi):
    girdi = girdi.strip()
    parcalar = re.split(r'[.\-/]', girdi)
    if len(parcalar) == 3:
        g, m, y = parcalar
        return f"{g.zfill(2)}-{m.zfill(2)}-{y}"
    return girdi

def satirlari_parse_et(ham):
    ham = ham.strip()
    satirlar = []
    if "\t" in ham:
        for satir in ham.splitlines():
            satir = satir.strip()
            if not satir: continue
            p = [x.strip() for x in satir.split("\t") if x.strip()]
            if len(p) >= 3:
                satirlar.append(p[:3])
    else:
        tum = [s.strip() for s in ham.splitlines() if s.strip()]
        i = 0
        while i < len(tum):
            if i + 2 < len(tum):
                satirlar.append([tum[i], tum[i+1], tum[i+2]])
                i += 3
            elif i + 1 < len(tum):
                # ülke+tarih aynı satırda olabilir
                sonraki = tum[i+1]
                m = re.search(r'(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})', sonraki)
                if m:
                    tarih_str = m.group(1)
                    ulke_str  = sonraki[:m.start()].strip()
                    satirlar.append([tum[i], ulke_str, tarih_str])
                i += 2
            else:
                break

    sonuc = []
    for p in satirlar:
        sonuc.append({
            "gtip_ham":  p[0],
            "ulke_ham":  p[1],
            "tarih_ham": p[2],
            "gtip":      gtip_cevir(p[0]),
            "ulke":      ulke_cevir(p[1]),
            "tarih":     tarih_cevir(p[2]),
        })
    return sonuc

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
            page.wait_for_selector("#taricCode", timeout=10000)
            page.fill("#taricCode", gtip.strip())
            if ulke.strip():
                try: page.select_option("#taricArea", ulke.strip())
                except: pass
            if tarih.strip():
                page.evaluate("(t) => { document.querySelector('#SimDatePic').value = t; }", tarih.strip())
            try:
                page.get_by_text("Retrieve Measures", exact=True).click()
            except:
                try: page.locator("button", has_text="Retrieve Measures").click()
                except: page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle", timeout=30000)
            time.sleep(2)
            html_content = page.content()
            pdf_bytes    = page.pdf(format="A4", print_background=True)
            browser.close()
            return html_content, pdf_bytes, None
    except Exception as e:
        return None, None, str(e)

def html_temizle(html):
    ek = '<base href="https://ec.europa.eu" target="_blank"><style>body{font-size:15px!important;line-height:1.7!important;font-family:Arial,sans-serif!important}table{font-size:14px!important}td,th{padding:6px 10px!important}</style>'
    return html.replace("<head>", "<head>" + ek, 1) if "<head>" in html else ek + html

# ─── SAYFA AYARI ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="TARIC Sorgu", page_icon="🛃",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@400;700;800&display=swap');
html,body,[data-testid="stAppViewContainer"]{background:#f5f3ef;font-family:'Syne',sans-serif;color:#1a1a1a;}
section[data-testid="stSidebar"]{display:none;}
header{display:none!important;}
.block-container{padding:12px 16px!important;max-width:100%!important;}
[data-testid="stTextArea"] textarea{
    background:white!important;border:1px solid #d4c97a!important;border-radius:4px!important;
    color:#1a1a1a!important;font-family:'JetBrains Mono',monospace!important;font-size:12px!important;padding:8px 10px!important;
}
[data-testid="stTextInput"] input{
    background:white!important;border:1px solid #d4c97a!important;border-radius:4px!important;
    color:#1a1a1a!important;font-family:'JetBrains Mono',monospace!important;
    font-size:14px!important;font-weight:700!important;padding:8px 10px!important;
}
[data-testid="stTextArea"] label,[data-testid="stTextInput"] label{
    color:#888!important;font-size:10px!important;font-weight:700!important;
    letter-spacing:1.5px!important;text-transform:uppercase!important;
}
.stButton>button{
    font-family:'Syne',sans-serif!important;font-weight:700!important;font-size:12px!important;
    letter-spacing:1px!important;text-transform:uppercase!important;border-radius:4px!important;
    padding:10px 0!important;width:100%!important;transition:all 0.2s!important;border:none!important;
}
.btn-sorgula .stButton>button{background:#1d4ed8!important;color:white!important;font-size:14px!important;padding:13px 0!important;}
.btn-sorgula .stButton>button:hover{background:#1e40af!important;}
.btn-pdf     .stButton>button{background:#16a34a!important;color:white!important;}
.btn-devam   .stButton>button{background:#d97706!important;color:white!important;}
.btn-kirp    .stButton>button{background:#7c3aed!important;color:white!important;}
.btn-reset   .stButton>button{background:#6b7280!important;color:white!important;}
.veri-kutu{background:white;border:2px solid #1d4ed8;border-radius:8px;padding:12px 16px;
           font-family:'JetBrains Mono',monospace;font-size:13px;line-height:2.2;margin:8px 0;}
.satir-kart{background:white;border:1px solid #e5e7eb;border-radius:6px;padding:6px 10px;
            margin-bottom:3px;font-family:'JetBrains Mono',monospace;font-size:11px;}
.satir-aktif{border-color:#1d4ed8!important;background:#eff6ff!important;font-weight:700;}
.satir-tamam{opacity:0.5;text-decoration:line-through;}
.prog{background:#e5e7eb;border-radius:8px;height:6px;overflow:hidden;margin:4px 0 12px;}
.prog-bar{background:linear-gradient(90deg,#1d4ed8,#7c3aed);height:100%;border-radius:8px;}
hr{border-color:#e0ddd5!important;margin:10px 0!important;}
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ─────────────────────────────────────────────────────────────
for k, v in {
    "kuyruk":      [],
    "aktif_idx":   0,
    "page_html":   None,
    "pdf_bytes":   None,
    "sorgulandı":  False,
    "pdf_sayisi":  0,
    "baslatildi":  False,
    # Düzenlenebilir aktif veri
    "akt_gtip":    "",
    "akt_ulke":    "",
    "akt_tarih":   "",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

def aktif_satiri_yukle():
    """Sıradaki satırı aktif kutulara yükle"""
    idx = st.session_state.aktif_idx
    if idx < len(st.session_state.kuyruk):
        s = st.session_state.kuyruk[idx]
        st.session_state.akt_gtip  = s["gtip"]
        st.session_state.akt_ulke  = s["ulke"]
        st.session_state.akt_tarih = s["tarih"]

def sonraki_satira_gec():
    st.session_state.aktif_idx  += 1
    st.session_state.sorgulandı  = False
    st.session_state.page_html   = None
    st.session_state.pdf_bytes   = None
    aktif_satiri_yukle()

# ─── LAYOUT ───────────────────────────────────────────────────────────────────
sol, sag = st.columns([0.5, 2.5], gap="medium")

with sol:
    st.markdown("""
    <div style='padding-bottom:12px;border-bottom:2px solid #c8b560;margin-bottom:14px;'>
        <div style='font-size:22px;font-weight:800;'>🛃 TARIC</div>
        <div style='font-size:10px;color:#999;letter-spacing:2px;'>GÜMRÜK TARİFE SORGULAMA</div>
    </div>
    """, unsafe_allow_html=True)

    # ── TOPLU VERİ YAPISTIRMA ────────────────────────────────────────────────
    with st.expander("📋 Toplu Veri Yapıştır" + (" ✅" if st.session_state.baslatildi else ""), expanded=not st.session_state.baslatildi):
        yapistir = st.text_area(
            "Excel'den Yapıştır (GTİP · Ülke · Tarih)",
            placeholder="72.07.11.14.00.00\tRusya\t1.01.2024\n72.07.12.10.00.00\tPakistan\t11.12.2024",
            height=120,
            key="yapistir_kutu"
        )
        satirlar = []
        if yapistir.strip():
            satirlar = satirlari_parse_et(yapistir)
            if satirlar:
                st.markdown(f"<div style='font-size:11px;color:#166534;font-weight:700;'>✅ {len(satirlar)} satır algılandı</div>", unsafe_allow_html=True)
            else:
                st.warning("Format tanınamadı")

        if st.button("📥  Kuyruğa Yükle", use_container_width=True, disabled=len(satirlar)==0):
            st.session_state.kuyruk     = satirlar
            st.session_state.aktif_idx  = 0
            st.session_state.baslatildi = True
            st.session_state.sorgulandı = False
            st.session_state.page_html  = None
            st.session_state.pdf_bytes  = None
            st.session_state.pdf_sayisi = 0
            aktif_satiri_yukle()
            st.rerun()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── İLERLEME ─────────────────────────────────────────────────────────────
    if st.session_state.kuyruk:
        toplam = len(st.session_state.kuyruk)
        idx    = st.session_state.aktif_idx
        pct    = int((idx / toplam) * 100)
        st.markdown(f"""
        <div style='font-size:11px;color:#4b5563;font-family:JetBrains Mono,monospace;'>
            {idx}/{toplam} · {pct}% · 📄{st.session_state.pdf_sayisi} PDF
        </div>
        <div class='prog'><div class='prog-bar' style='width:{pct}%'></div></div>
        """, unsafe_allow_html=True)

    # ── DÜZENLENEBİLİR AKTİF VERİ KUTULARI ──────────────────────────────────
    st.markdown("<div style='font-size:10px;color:#888;letter-spacing:1.5px;font-weight:700;margin-bottom:4px;'>SORGULANACAK VERİ</div>", unsafe_allow_html=True)

    akt_gtip  = st.text_input("GTİP", value=st.session_state.akt_gtip,  key="inp_gtip")
    akt_ulke  = st.text_input("Ülke", value=st.session_state.akt_ulke,  key="inp_ulke")
    akt_tarih = st.text_input("Tarih", value=st.session_state.akt_tarih, key="inp_tarih")

    # Kutulardaki değişiklikleri session'a yansıt
    st.session_state.akt_gtip  = akt_gtip
    st.session_state.akt_ulke  = akt_ulke
    st.session_state.akt_tarih = akt_tarih

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # ── SORGULA (HER ZAMAN GÖRÜNÜR) ──────────────────────────────────────────
    st.markdown("<div class='btn-sorgula'>", unsafe_allow_html=True)
    sorgula = st.button("🔍  Sorgula", use_container_width=True,
                        disabled=not bool(akt_gtip.strip()))
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # ── PDF AL ───────────────────────────────────────────────────────────────
    if st.session_state.pdf_bytes:
        st.markdown("<div class='btn-pdf'>", unsafe_allow_html=True)
        dosya = f"{idx+1 if st.session_state.kuyruk else 1}_{akt_gtip}_{akt_ulke}.pdf"
        if st.download_button("📄  PDF Al → Sonraki", data=st.session_state.pdf_bytes,
                              file_name=dosya, mime="application/pdf", use_container_width=True):
            st.session_state.pdf_sayisi += 1
            sonraki_satira_gec()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ── DEVAM ET (PDF almadan) ────────────────────────────────────────────────
    if st.session_state.sorgulandı and st.session_state.kuyruk:
        st.markdown("<div class='btn-devam'>", unsafe_allow_html=True)
        if st.button("⏭️  PDF Almadan Devam", use_container_width=True):
            sonraki_satira_gec()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ── SONDAN 1 RAKAM SİL ───────────────────────────────────────────────────
    if st.session_state.sorgulandı:
        st.markdown("<div style='height:4px'></div><div class='btn-kirp'>", unsafe_allow_html=True)
        if st.button("✂️  Sondan 1 Rakam Sil", use_container_width=True):
            if len(akt_gtip.strip()) > 4:
                st.session_state.akt_gtip = akt_gtip.strip()[:-1]
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ── KUYRUK LİSTESİ ───────────────────────────────────────────────────────
    if st.session_state.kuyruk:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:10px;color:#888;letter-spacing:1px;margin-bottom:4px;'>KUYRUK</div>", unsafe_allow_html=True)
        idx = st.session_state.aktif_idx
        for i, s in enumerate(st.session_state.kuyruk):
            if i < idx:
                cls, ikon = "satir-kart satir-tamam", "✅"
            elif i == idx:
                cls, ikon = "satir-kart satir-aktif", "▶"
            else:
                cls, ikon = "satir-kart", f"{i+1}."
            st.markdown(f"<div class='{cls}'>{ikon} {s['gtip']} / {s['ulke']}</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:6px'></div><div class='btn-reset'>", unsafe_allow_html=True)
        if st.button("↺  Sıfırla", use_container_width=True):
            for k in ["kuyruk","aktif_idx","page_html","pdf_bytes",
                      "sorgulandı","baslatildi","pdf_sayisi","akt_gtip","akt_ulke","akt_tarih"]:
                st.session_state[k] = ([] if k=="kuyruk" else 0 if k in ["aktif_idx","pdf_sayisi"]
                                       else False if k in ["sorgulandı","baslatildi"]
                                       else None if k in ["page_html","pdf_bytes"] else "")
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ─── SORGU İŞLEMİ ────────────────────────────────────────────────────────────
if sorgula:
    gtip  = st.session_state.akt_gtip.strip()
    ulke  = st.session_state.akt_ulke.strip()
    tarih = st.session_state.akt_tarih.strip()
    with sag:
        with st.spinner(f"⏳ {gtip} / {ulke} sorgulanıyor..."):
            html_content, pdf_bytes, hata = taric_sorgula(gtip, ulke, tarih)
        if hata:
            st.error(f"❌ {hata}")
        else:
            st.session_state.page_html  = html_temizle(html_content)
            st.session_state.pdf_bytes  = pdf_bytes
            st.session_state.sorgulandı = True
    st.rerun()

# ─── SAĞ PANEL ───────────────────────────────────────────────────────────────
with sag:
    if st.session_state.page_html:
        st.markdown(f"""
        <div style='display:flex;align-items:center;justify-content:space-between;
                    padding:10px 16px;background:#1a1a1a;border-radius:6px 6px 0 0;'>
            <div style='font-family:JetBrains Mono,monospace;font-size:12px;color:#c8b560;font-weight:700;'>
                🛃 {st.session_state.akt_gtip} / {st.session_state.akt_ulke}
            </div>
            <div style='font-size:11px;color:#666;'>▶ ok işaretlerine ve mavi linklere tıklayabilirsiniz</div>
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
                Sol panelden veri girin veya Excel'den yapıştırın<br>
                Sorgula'ya basın — sonuç burada görünür
            </div>
        </div>
        """, unsafe_allow_html=True)

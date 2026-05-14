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
    # dd.mm.yyyy veya d.m.yyyy → dd-mm-yyyy
    parcalar = re.split(r'[.\-/]', girdi)
    if len(parcalar) == 3:
        g, m, y = parcalar
        return f"{g.zfill(2)}-{m.zfill(2)}-{y}"
    return girdi

def satirlari_parse_et(ham):
    """
    Çok satırlı yapıştırma → liste of {gtip, ulke, tarih, gtip_ham, ulke_ham}
    Her satır: GTİP TAB Ülke TAB Tarih
    veya alt alta: GTİP / Ülke / Tarih (3'erli gruplar)
    """
    ham = ham.strip()
    satirlar = []

    if "\t" in ham:
        # Tab ayrımlı — her satır bir kayıt
        for satir in ham.splitlines():
            satir = satir.strip()
            if not satir: continue
            parcalar = [p.strip() for p in satir.split("\t") if p.strip()]
            if len(parcalar) >= 3:
                satirlar.append(parcalar)
    else:
        # Satır satır — her 3 satır bir kayıt
        tum = [s.strip() for s in ham.splitlines() if s.strip()]
        i = 0
        while i + 2 < len(tum):
            gtip_s = tum[i]
            # İkinci satırda ülke+tarih birlikte mi?
            sonraki = tum[i+1]
            tarih_p = re.compile(r'\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}')
            tarih_eslesen = tarih_p.search(sonraki)
            if tarih_eslesen and i + 2 == len(tum):
                # 2 satırlı format: GTİP / Ülke Tarih
                tarih_str = tarih_eslesen.group()
                ulke_str  = sonraki[:tarih_eslesen.start()].strip()
                satirlar.append([gtip_s, ulke_str, tarih_str])
                i += 2
            else:
                satirlar.append([tum[i], tum[i+1], tum[i+2]])
                i += 3

    sonuc = []
    for p in satirlar:
        gtip_ham = p[0]
        ulke_ham = p[1]
        tarih_ham = p[2]
        sonuc.append({
            "gtip_ham":  gtip_ham,
            "ulke_ham":  ulke_ham,
            "tarih_ham": tarih_ham,
            "gtip":      gtip_cevir(gtip_ham),
            "ulke":      ulke_cevir(ulke_ham),
            "tarih":     tarih_cevir(tarih_ham),
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
                try:
                    page.select_option("#taricArea", ulke.strip())
                except:
                    pass

            if tarih.strip():
                page.evaluate(
                    "(t) => { document.querySelector('#SimDatePic').value = t; }",
                    tarih.strip()
                )

            # Butonu tıkla
            try:
                page.get_by_text("Retrieve Measures", exact=True).click()
            except:
                try:
                    page.locator("button", has_text="Retrieve Measures").click()
                except:
                    page.keyboard.press("Enter")

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
    font-size:12px!important;padding:8px 10px!important;
}
[data-testid="stTextArea"] label{color:#888!important;font-size:10px!important;font-weight:700!important;letter-spacing:1.5px!important;text-transform:uppercase!important;}
.stButton>button{
    font-family:'Syne',sans-serif!important;font-weight:700!important;font-size:12px!important;
    letter-spacing:1px!important;text-transform:uppercase!important;border-radius:4px!important;
    padding:10px 0!important;width:100%!important;transition:all 0.2s!important;border:none!important;
}
.btn-basla  .stButton>button{background:#1d4ed8!important;color:white!important;}
.btn-pdf    .stButton>button{background:#16a34a!important;color:white!important;}
.btn-sirada .stButton>button{background:#d97706!important;color:white!important;}
.btn-kirp   .stButton>button{background:#7c3aed!important;color:white!important;}
.btn-reset  .stButton>button{background:#6b7280!important;color:white!important;}
.satir-kart{background:white;border:1px solid #e5e7eb;border-radius:6px;padding:8px 12px;
            margin-bottom:4px;font-family:'JetBrains Mono',monospace;font-size:11px;}
.satir-aktif{border-color:#1d4ed8!important;background:#eff6ff!important;}
.satir-tamam{border-color:#16a34a!important;background:#f0fdf4!important;color:#4b5563;}
.ilerleme{background:#f0fdf4;border:1px solid #86efac;border-radius:6px;
          padding:10px 14px;font-family:'JetBrains Mono',monospace;font-size:12px;line-height:2;margin:4px 0 8px;}
.durum-hata{background:#fdecea;color:#c62828;border:1px solid #ef9a9a;border-radius:6px;padding:8px 12px;font-weight:700;font-size:12px;margin:6px 0;}
hr{border-color:#e0ddd5!important;margin:10px 0!important;}
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ─────────────────────────────────────────────────────────────
for k, v in {
    "satirlar":    [],      # parse edilmiş tüm satırlar
    "aktif_idx":   0,       # şu an hangi satır işleniyor
    "page_html":   None,
    "pdf_bytes":   None,
    "durum":       "",
    "sorgulandı":  False,
    "baslatildi":  False,
    "gtip_kirp":   "",
    "pdf_listesi": [],      # indirilen PDF'lerin adları
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── LAYOUT ───────────────────────────────────────────────────────────────────
sol, sag = st.columns([0.5, 2.5], gap="medium")

def mevcut_satir():
    idx = st.session_state.aktif_idx
    if idx < len(st.session_state.satirlar):
        return st.session_state.satirlar[idx]
    return None

def sorgu_yap(gtip, ulke, tarih):
    html_content, pdf_bytes, hata = taric_sorgula(gtip, ulke, tarih)
    if not hata:
        st.session_state.page_html  = html_temizle(html_content)
        st.session_state.pdf_bytes  = pdf_bytes
        st.session_state.sorgulandı = True
        st.session_state.gtip_kirp  = ""
        st.session_state.durum      = f"✅ {gtip} / {ulke}"
    return hata

# ═══════════════════════════════════════════════════════════════════════════════
# SOL PANEL
# ═══════════════════════════════════════════════════════════════════════════════
with sol:
    st.markdown("""
    <div style='padding-bottom:12px;border-bottom:2px solid #c8b560;margin-bottom:14px;'>
        <div style='font-size:22px;font-weight:800;'>🛃 TARIC</div>
        <div style='font-size:10px;color:#999;letter-spacing:2px;'>GÜMRÜK TARİFE SORGULAMA</div>
    </div>
    """, unsafe_allow_html=True)

    # ── HENÜZ BAŞLATILMADI: veri giriş ekranı ────────────────────────────────
    if not st.session_state.baslatildi:
        yapistir = st.text_area(
            "Excel'den Yapıştır",
            placeholder="72.07.11.14.00.00\tRusya\t1.01.2024\n72.07.12.10.00.00\tPakistan\t11.12.2024\n...",
            height=160,
            key="yapistir_kutu"
        )

        satirlar = []
        if yapistir.strip():
            satirlar = satirlari_parse_et(yapistir)
            if satirlar:
                st.markdown(f"<div style='font-size:11px;color:#166534;font-weight:700;margin:4px 0;'>✅ {len(satirlar)} satır algılandı</div>", unsafe_allow_html=True)
                for i, s in enumerate(satirlar):
                    st.markdown(f"""
                    <div class='satir-kart'>
                        <b>{i+1}.</b> {s['gtip']} / <b>{s['ulke']}</b> / {s['tarih']}
                        <span style='color:#9ca3af;font-size:10px;'> ← {s['gtip_ham']}, {s['ulke_ham']}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.warning("Format: GTİP TAB Ülke TAB Tarih (her satıra bir kayıt)")

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='btn-basla'>", unsafe_allow_html=True)
        if st.button("🚀  Sorgulamaya Başla", use_container_width=True,
                     disabled=len(satirlar) == 0):
            st.session_state.satirlar   = satirlar
            st.session_state.aktif_idx  = 0
            st.session_state.baslatildi = True
            st.session_state.pdf_listesi = []
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ── BAŞLATILDI: sorgu ekranı ──────────────────────────────────────────────
    else:
        toplam  = len(st.session_state.satirlar)
        idx     = st.session_state.aktif_idx
        bitti   = idx >= toplam
        s       = mevcut_satir()

        # İlerleme
        pct = int((idx / toplam) * 100)
        st.markdown(f"""
        <div style='font-size:11px;color:#4b5563;font-family:JetBrains Mono,monospace;'>
            {idx} / {toplam} tamamlandı &nbsp;·&nbsp; %{pct} &nbsp;·&nbsp; 📄 {len(st.session_state.pdf_listesi)} PDF
        </div>
        <div style='background:#e5e7eb;border-radius:8px;height:6px;overflow:hidden;margin:4px 0 10px;'>
            <div style='background:linear-gradient(90deg,#1d4ed8,#7c3aed);height:100%;width:{pct}%;border-radius:8px;'></div>
        </div>
        """, unsafe_allow_html=True)

        if not bitti and s:
            # Aktif satır
            gtip_goster  = st.session_state.gtip_kirp if st.session_state.gtip_kirp else s["gtip"]
            kirp_notu    = " ✂️" if st.session_state.gtip_kirp else ""
            st.markdown(f"""
            <div class='ilerleme'>
                <span style='color:#4b5563;'>GTİP :</span> <b style='color:#1d4ed8;'>{gtip_goster}</b>{kirp_notu}<br>
                <span style='color:#4b5563;'>Ülke :</span> <b style='color:#1d4ed8;'>{s['ulke']}</b>
                <span style='color:#9ca3af;font-size:10px;'> ({s['ulke_ham']})</span><br>
                <span style='color:#4b5563;'>Tarih:</span> <b style='color:#1d4ed8;'>{s['tarih']}</b>
            </div>
            """, unsafe_allow_html=True)

            # Sorgula (ilk açılışta henüz sorgulanmamışsa)
            if not st.session_state.sorgulandı:
                st.markdown("<div class='btn-basla'>", unsafe_allow_html=True)
                if st.button("🔍  Sorgula", use_container_width=True):
                    with sag:
                        with st.spinner(f"⏳ {gtip_goster} / {s['ulke']} sorgulanıyor..."):
                            hata = sorgu_yap(gtip_goster, s["ulke"], s["tarih"])
                        if hata:
                            st.markdown(f"<div class='durum-hata'>❌ {hata}</div>", unsafe_allow_html=True)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            else:
                # PDF Al
                st.markdown("<div class='btn-pdf'>", unsafe_allow_html=True)
                if st.session_state.pdf_bytes:
                    dosya_adi = f"{idx+1}_{gtip_goster}_{s['ulke']}.pdf"
                    if st.download_button(
                        label="📄  PDF Al → Sonraki",
                        data=st.session_state.pdf_bytes,
                        file_name=dosya_adi,
                        mime="application/pdf",
                        use_container_width=True,
                    ):
                        st.session_state.pdf_listesi.append(dosya_adi)
                        st.session_state.aktif_idx += 1
                        st.session_state.sorgulandı = False
                        st.session_state.page_html  = None
                        st.session_state.pdf_bytes  = None
                        st.session_state.gtip_kirp  = ""
                        # Sonraki satırı otomatik sorgula
                        sonraki = mevcut_satir()
                        if sonraki:
                            hata = sorgu_yap(sonraki["gtip"], sonraki["ulke"], sonraki["tarih"])
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

                # Sıradakine Geç (PDF almadan)
                st.markdown("<div class='btn-sirada'>", unsafe_allow_html=True)
                if st.button("⏭️  PDF Almadan Geç", use_container_width=True):
                    st.session_state.aktif_idx += 1
                    st.session_state.sorgulandı = False
                    st.session_state.page_html  = None
                    st.session_state.pdf_bytes  = None
                    st.session_state.gtip_kirp  = ""
                    sonraki = mevcut_satir()
                    if sonraki:
                        with sag:
                            with st.spinner(f"⏳ {sonraki['gtip']} sorgulanıyor..."):
                                sorgu_yap(sonraki["gtip"], sonraki["ulke"], sonraki["tarih"])
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

                # Sondan 1 Rakam Sil
                st.markdown("<div class='btn-kirp'>", unsafe_allow_html=True)
                if st.button("✂️  Sondan 1 Rakam Sil", use_container_width=True):
                    mevcut_gtip = st.session_state.gtip_kirp if st.session_state.gtip_kirp else s["gtip"]
                    if len(mevcut_gtip) > 4:
                        yeni = mevcut_gtip[:-1]
                        st.session_state.gtip_kirp = yeni
                        with sag:
                            with st.spinner(f"⏳ {yeni} sorgulanıyor..."):
                                sorgu_yap(yeni, s["ulke"], s["tarih"])
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        else:
            # Tüm satırlar bitti
            st.markdown(f"""
            <div style='background:#f0fdf4;border:1px solid #86efac;border-radius:8px;
                        padding:20px;text-align:center;'>
                <div style='font-size:28px;'>🎉</div>
                <div style='font-weight:700;color:#166534;margin:8px 0;'>Tamamlandı!</div>
                <div style='font-size:12px;color:#4b5563;'>
                    {toplam} satır işlendi<br>
                    {len(st.session_state.pdf_listesi)} PDF alındı
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)

        # Satır listesi
        st.markdown("<div style='font-size:10px;color:#888;letter-spacing:1px;margin-bottom:6px;'>TÜM SATIRLAR</div>", unsafe_allow_html=True)
        for i, s in enumerate(st.session_state.satirlar):
            if i < idx:
                cls = "satir-tamam"
                ikon = "✅"
            elif i == idx:
                cls = "satir-aktif"
                ikon = "▶"
            else:
                cls = "satir-kart"
                ikon = f"{i+1}."
            st.markdown(f"""
            <div class='satir-kart {cls}'>
                {ikon} {s['gtip']} / {s['ulke']} / {s['tarih']}
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("<div class='btn-reset'>", unsafe_allow_html=True)
        if st.button("↺  Başa Dön", use_container_width=True):
            for k in ["satirlar","aktif_idx","page_html","pdf_bytes",
                      "durum","sorgulandı","baslatildi","gtip_kirp","pdf_listesi"]:
                st.session_state[k] = [] if k in ["satirlar","pdf_listesi"] else (
                    0 if k == "aktif_idx" else (False if k in ["sorgulandı","baslatildi"] else (None if k in ["page_html","pdf_bytes"] else "")))
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# SAĞ PANEL
# ═══════════════════════════════════════════════════════════════════════════════
with sag:
    if st.session_state.page_html:
        idx = st.session_state.aktif_idx
        s   = st.session_state.satirlar[idx] if idx < len(st.session_state.satirlar) else {}
        gtip_goster = st.session_state.gtip_kirp if st.session_state.gtip_kirp else s.get("gtip","")
        st.markdown(f"""
        <div style='display:flex;align-items:center;justify-content:space-between;
                    padding:10px 16px;background:#1a1a1a;border-radius:6px 6px 0 0;'>
            <div style='font-family:JetBrains Mono,monospace;font-size:12px;color:#c8b560;font-weight:700;'>
                🛃 {gtip_goster} / {s.get('ulke','')}
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
                Excel'den satırları yapıştırın<br>
                Sorgulamaya Başla'ya basın
            </div>
        </div>
        """, unsafe_allow_html=True)

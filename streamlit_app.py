import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import io
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Portefeuille BNC", layout="wide")

# --- CSS : Forcer les proportions sur mobile ---
st.markdown("""
    <style>
        div[data-testid="stHorizontalBlock"] { flex-direction: row !important; flex-wrap: nowrap !important; gap: 10px !important; }
        div[data-testid="stHorizontalBlock"] > div:nth-child(1) { width: 35% !important; min-width: 35% !important; flex: none !important; }
        div[data-testid="stHorizontalBlock"] > div:nth-child(2) { width: 65% !important; min-width: 65% !important; flex: none !important; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def heure_mise_a_jour():
    return datetime.now(ZoneInfo("America/Toronto")).strftime("%H:%M")

@st.cache_data(ttl=300)
def obtenir_taux_change():
    try:
        return yf.Ticker("CAD=X").history(period="1d")['Close'].iloc[-1]
    except:
        return 1.38

@st.cache_data(ttl=300)
def charger_donnees(nom_feuille):
    entetes = {'User-Agent': 'Mozilla/5.0'}
    url = "https://onedrive.live.com/:x:/g/personal/f3dc5429b587ae35/IQAm87v8ehTnQrt_lz2sW1Q5AUk-6g4cno5k6CgDX9V0qtU?download=1"
    reponse = requests.get(url, headers=entetes)
    return pd.read_excel(io.BytesIO(reponse.content), sheet_name=nom_feuille, engine='openpyxl')

def mise_a_jour_portefeuille(df, taux_change):
    df['Valeur CAD'], df['Gain CAD'] = 0.0, 0.0
    for index, row in df.iterrows():
        symbole = row.get('Symbole')
        if pd.notna(symbole):
            try:
                t = yf.Ticker(str(symbole).strip())
                h = t.history(period="5d")
                if not h.empty and len(h) >= 2:
                    cp, vp = h['Close'].iloc[-1], h['Close'].iloc[-2]
                    df.at[index, 'Prix $'], df.at[index, 'Var %'] = cp, (cp - vp) / vp
                    achat, qte = row['Achat $'], row['Qtée']
                    df.at[index, 'Gain %'], df.at[index, 'Gain $'] = (cp - achat) / achat, (cp - achat) * qte
                    
                    devise = t.info.get('currency', 'CAD')
                    if devise == 'USD':
                        df.at[index, 'Valeur CAD'] = (cp * qte) * taux_change
                        df.at[index, 'Gain CAD'] = ((cp - achat) * qte) * taux_change
                    else:
                        df.at[index, 'Valeur CAD'] = cp * qte
                        df.at[index, 'Gain CAD'] = (cp - achat) * qte
                df.at[index, 'Pré 1an $'] = t.info.get('targetMeanPrice')
            except: pass
    return df

def mise_a_jour_prospects(df):
    for index, row in df.iterrows():
        symbole = row.get('Symbole')
        if pd.notna(symbole):
            try:
                t = yf.Ticker(str(symbole).strip())
                h = t.history(period="5d")
                if not h.empty:
                    cp, vp = h['Close'].iloc[-1], h['Close'].iloc[-2]
                    df.at[index, 'Prix $'] = cp
                    df.at[index, 'Var %'] = (cp - vp) / vp
                    df.at[index, 'Pré 1an $'] = t.info.get('targetMeanPrice')
            except: pass
    return df

# --- INTERFACE ---
st.title("📈 BNC")
heure_actuelle = heure_mise_a_jour()
col_tri, col_btn = st.columns([1, 2.5])
with col_tri:
    colonne_tri = st.selectbox("Tri", ["Pré G %", "Gain %"], label_visibility="collapsed")
with col_btn:
    if st.button(f"🔄 Rafraîchir ({heure_actuelle})", use_container_width=True):
        st.cache_data.clear(); st.rerun()

# CRÉATION DES ONGLETS
tab1, tab2 = st.tabs(["💰 Portefeuille", "🎯 Prospects"])

try:
    with st.spinner("Mise à jour des prix..."):
        taux = obtenir_taux_change()

    # --- CONTENU ONGLET 1 : PORTEFEUILLE ---
    with tab1:
        df_p = charger_donnees('Portefeuille BNC')
        df_p = df_p[df_p['No.'] != 0].reset_index(drop=True)
        df_p = mise_a_jour_portefeuille(df_p, taux)
        
        for c in ["Pré G %", "Gain %", "Var %"]: 
            if c in df_p.columns: df_p[c] = df_p[c] * 100
        
        df_p = df_p.sort_values(by=colonne_tri, ascending=(colonne_tri == "Pré G %"))
        
        v_tot, g_tot = df_p['Valeur CAD'].sum(), df_p['Gain CAD'].sum()
        st.markdown(f"""
            <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
                <div style="flex: 1; text-align: left;"><p style="margin:0; font-size:14px; color:gray;">Gain total</p><p style="margin:0; font-size:22px; font-weight:bold;">{g_tot:,.2f} $</p></div>
                <div style="flex: 1; text-align: center;"><p style="margin:0; font-size:14px; color:gray;">Valeur totale</p><p style="margin:0; font-size:22px; font-weight:bold;">{v_tot:,.2f} $</p></div>
                <div style="flex: 1;"></div>
            </div>""", unsafe_allow_html=True)

        def style_p(v):
            if pd.isna(v): return ''
            return f'background-color: rgba(255,0,0,0.3)' if v <= 5 else (f'background-color: rgba(255,255,0,0.3)' if v < 15 else f'background-color: rgba(0,255,0,0.3)')

        h_p = (len(df_p) * 35) + 45
        st.dataframe(df_p.style.map(style_p, subset=['Pré G %']), use_container_width=True, hide_index=True, height=h_p,
                     column_config={"Pré G %": st.column_config.NumberColumn(format="%.0f %%"), "Prix $": "$ %.2f", "Pré 1an $": "$ %.2f", "Achat $": "$ %.2f", "Gain %": "%.0f %%", "Var %": "%.2f %%", "Gain $": "$ %.2f"})

    # --- CONTENU ONGLET 2 : PROSPECTS ---
    with tab2:
        df_pros = charger_donnees('Prospects')
        df_pros = mise_a_jour_prospects(df_pros)
        if 'Var %' in df_pros.columns: df_pros['Var %'] = df_pros['Var %'] * 100
        
        h_pros = (len(df_pros) * 35) + 45
        st.dataframe(df_pros, use_container_width=True, hide_index=True, height=h_pros,
                     column_config={"Prix $": "$ %.2f", "Var %": "%.2f %%", "Pré 1an $": "$ %.2f", "Cible $": "$ %.2f"})

except Exception as e:
    st.error(f"Erreur : {e}")

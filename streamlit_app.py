import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import io
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Portefeuille BNC", layout="wide")

# --- ASTUCE CSS : Forcer les proportions exactes sur mobile ---
st.markdown("""
    <style>
        /* 1. S'applique uniquement au bloc de tri/rafraîchissement tout en haut */
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stSelectbox"]) {
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 10px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stSelectbox"]) > div:nth-child(1) {
            width: 35% !important;
            min-width: 35% !important;
            flex: none !important;
        }
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stSelectbox"]) > div:nth-child(2) {
            width: 65% !important;
            min-width: 65% !important;
            flex: none !important;
        }

        /* 2. S'applique spécifiquement aux filtres numériques Min/Max des prospects */
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stNumberInput"]) {
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 15px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stNumberInput"]) > div {
            min-width: 110px !important; 
        }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def heure_mise_a_jour():
    return datetime.now(ZoneInfo("America/Toronto")).strftime("%H:%M")

# --- TITRE PRINCIPAL ---
col_title, col_params = st.columns([8, 2])
with col_title:
    st.title("📈 BNC LIVE")
with col_params:
    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
    with st.popover("⚙️"):
        source_gain = st.selectbox("Calcul du Gain", ["Yahoo", "Affaires", "Moyenne"])

heure_actuelle = heure_mise_a_jour()

col_tri, col_btn = st.columns([1, 2.5])

with col_tri:
    colonne_tri = st.selectbox("Tri", ["Pré G %", "Gain %"], label_visibility="collapsed")
    
with col_btn:
    if st.button(f"🔄 Rafraîchir ({heure_actuelle})", use_container_width=True):
        st.cache_data.clear() 
        st.rerun()

URL_ONEDRIVE = "https://onedrive.live.com/:x:/g/personal/f3dc5429b587ae35/IQAm87v8ehTnQrt_lz2sW1Q5AUk-6g4cno5k6CgDX9V0qtU?download=1"

@st.cache_data(ttl=300)
def charger_donnees_base(nom_feuille):
    entetes = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    reponse = requests.get(URL_ONEDRIVE, headers=entetes, allow_redirects=True)
    reponse.raise_for_status() 
    df = pd.read_excel(io.BytesIO(reponse.content), sheet_name=nom_feuille, engine='openpyxl')
    
    # Nettoyage robuste des sauts de ligne Excel
    df.columns = [str(c).replace('\n', ' ').replace('\r', '') for c in df.columns]
    df.columns = [' '.join(c.split()) for c in df.columns] 
    return df

@st.cache_data(ttl=300, show_spinner=False)
def mise_a_jour_prix(df, est_portefeuille=True, symboles_portefeuille=None):
    df = df.copy() 
    df['Devise'] = 'USD'  
    df['Possede'] = False  
    
    if 'Pré 1an $' in df.columns and not est_portefeuille:
        df = df.rename(columns={'Pré 1an $': 'Pré 1an $ Fichier'})
        
    df['Pré 1an $ Yahoo'] = np.nan
    
    for index, row in df.iterrows():
        symbole = row.get('Symbole')
        if pd.notna(symbole):
            symbole_clean = str(symbole).strip()
            
            if symbole_clean.endswith('.TO') or '.V' in symbole_clean or '.NE' in symbole_clean:
                df.at[index, 'Devise'] = 'CAD'
            else:
                df.at[index, 'Devise'] = 'USD'
                
            if symboles_portefeuille and symbole_clean in symboles_portefeuille:
                df.at[index, 'Possede'] = True
                
            try:
                ticker = yf.Ticker(symbole_clean)
                infos = ticker.history(period="5d")
                
                prix_actuel = None
                
                if not infos.empty and len(infos) >= 2:
                    prix_actuel = infos['Close'].iloc[-1]
                    prix_veille = infos['Close'].iloc[-2]
                    
                    df.at[index, 'Prix $'] = prix_actuel
                    df.at[index, 'Var %'] = (prix_actuel - prix_veille) / prix_veille
                    
                    if est_portefeuille and 'Achat $' in row and pd.notna(row['Achat $']):
                        achat = row['Achat $']
                        qte = row['Qtée']
                        df.at[index, 'Gain %'] = (prix_actuel - achat) / achat
                        df.at[index, 'Gain $'] = (prix_actuel - achat) * qte
                
                infos_generales = ticker.info
                prevision_1an = infos_generales.get('targetMeanPrice')
                
                if prevision_1an is not None:
                    df.at[index, 'Pré 1an $ Yahoo'] = prevision_1an
                
                devise_officielle = infos_generales.get('currency')
                if devise_officielle:
                    df.at[index, 'Devise'] = str(devise_officielle).upper()
                
                df.at[index, 'Symbole'] = f"https://ca.finance.yahoo.com/quote/{symbole_clean}"
                        
            except Exception:
                pass
    return df

def calculer_potentiel_gain(df, source, est_portefeuille=True):
    df = df.copy()
    if 'Prix $' not in df.columns:
        return df
        
    prix = pd.to_numeric(df['Prix $'], errors='coerce')
    yahoo = pd.to_numeric(df['Pré 1an $ Yahoo'], errors='coerce')
    
    if est_portefeuille:
        affaires = pd.to_numeric(df.get('Pré 1an $ Affaires', np.nan), errors='coerce').replace(0, np.nan)
        yahoo_base = pd.to_numeric(df.get('Pré 1an $', np.nan), errors='coerce')
        yahoo = yahoo.fillna(yahoo_base)
    else:
        affaires = pd.to_numeric(df.get('Pré 1an $ Fichier', np.nan), errors='coerce').replace(0, np.nan)
    
    if source == "Yahoo":
        cible = yahoo.fillna(affaires)
    elif source == "Affaires":
        cible = affaires.fillna(yahoo)
    else: # Moyenne
        temp = pd.DataFrame({'Y': yahoo, 'A': affaires})
        cible = temp.mean(axis=1, skipna=True)
        
    mask = (prix > 0) & cible.notna()
    df.loc[mask, 'Pré G %'] = (cible[mask] - prix[mask]) / prix[mask]
    
    df['Pré 1an $ Display'] = yahoo
    df['Pré 1an $ Aff Display'] = affaires
        
    return df

try:
    with st.spinner("Connexion à OneDrive et Yahoo Finance..."):
        df_base_portefeuille = charger_donnees_base('Portefeuille BNC')
        df_base_prospects = charger_donnees_base('Prospects')

    if 'No.' in df_base_portefeuille.columns:
        df_portefeuille_actif = df_base_portefeuille[df_base_portefeuille['No.'] != 0].reset_index(drop=True)
    else:
        df_portefeuille_actif = df_base_portefeuille.copy()

    symboles_possedes = tuple(set(df_portefeuille_actif['Symbole'].dropna().astype(str).str.strip()))

    tab1, tab2, tab3 = st.tabs(["💰 Portefeuille", "🎯 Pros CAD", "🎯 Pros US"])

    # --- ONGLET 1 : PORTEFEUILLE ---
    with tab1:
        df_live = mise_a_jour_prix(df_portefeuille_actif, est_portefeuille=True)
        df_live = calculer_potentiel_gain(df_live, source_gain, est_portefeuille=True)

        for col in ["Pré G %", "Gain %", "Var %"]:
            if col in df_live.columns:
                df_live[col] = pd.to_numeric(df_live[col], errors='coerce') * 100

        if colonne_tri == "Pré G %":
            df_live = df_live.sort_values(by="Pré G %", ascending=True) 
        elif colonne_tri == "Gain %":
            df_live = df_live.sort_values(by="Gain %", ascending=False) 

        valeur_totale = (df_live['Prix $'] * df_live['Qtée']).sum()
        gain_total = df_live['Gain $'].sum()

        gain_formate = f"{gain_total:,.2f} $".replace(',', ' ')
        valeur_formate = f"{valeur_totale:,.2f} $".replace(',', ' ')

        st.markdown(f"""
            <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
                <div style="flex: 1; text-align: left;">
                    <p style="margin: 0px; font-size: 14px; color: gray;">Gain total</p>
                    <p style="margin: 0px; font-size: 20px; font-weight: bold;">{gain_formate}</p>
                </div>
                <div style="flex: 1; text-align: center;">
                    <p style="margin: 0px; font-size: 14px; color: gray;">Valeur totale</p>
                    <p style="margin: 0px; font-size: 20px; font-weight: bold;">{valeur_formate}</p>
                </div>
                <div style="flex: 1;"></div>
            </div>
        """, unsafe_allow_html=True)

        def couleur_alerte_vente(valeur):
            if pd.isna(valeur):
                return ''
            if valeur <= 5:
                return 'background-color: rgba(255, 0, 0, 0.3)'
            elif valeur < 15:
                return 'background-color: rgba(255, 255, 0, 0.3)'
            else:
                return 'background-color: rgba(0, 255, 0, 0.3)'

        df_stylise = df_live.style.map(couleur_alerte_vente, subset=['Pré G %'])
        hauteur_dynamique = (len(df_live) * 35) + 43

        st.dataframe(
            df_stylise,
            use_container_width=True,
            hide_index=True,
            height=hauteur_dynamique,
            column_order=["No.", "Symbole", "Prix $", "Var %", "Pré 1an $ Display", "Pré 1an $ Aff Display", "Pré G %", "Achat $", "Qtée", "Gain %", "Gain $", "Date Achat"],
            column_config={
                "No.": st.column_config.NumberColumn("No.", format="%d"),
                "Symbole": st.column_config.LinkColumn("Symbole", display_text=r"https://ca\.finance\.yahoo\.com/quote/(.*)"),
                "Pré G %": st.column_config.NumberColumn(format="%.1f %%"),
                "Prix $": st.column_config.NumberColumn(format="$ %.2f"),
                
                # TITRES ULTRA-COMPACTS
                "Pré 1an $ Display": st.column_config.NumberColumn("Pré YF", format="$ %.2f"),
                "Pré 1an $ Aff Display": st.column_config.NumberColumn("Pré Aff", format="$ %.2f"),
                
                "Achat $": st.column_config.NumberColumn(format="$ %.2f"),
                "Gain %": st.column_config.NumberColumn(format="%.1f %%"),
                "Var %": st.column_config.NumberColumn(format="%.1f %%"),
                "Gain $": st.column_config.NumberColumn(format="$ %.2f"),
                "Date Achat": st.column_config.DatetimeColumn(format="YYYY-MM-DD")
            }
        )

    # --- TRAITEMENT CENTRALISÉ DES PROSPECTS ---
    df_live_prospects = mise_a_jour_prix(df_base_prospects, est_portefeuille=False, symboles_portefeuille=symboles_possedes)
    df_live_prospects = calculer_potentiel_gain(df_live_prospects, source_gain, est_portefeuille=False)

    for col in ["Pré G %", "Var %"]:
        if col in df_live_prospects.columns:
            df_live_prospects[col] = pd.to_numeric(df_live_prospects[col], errors='coerce') * 100

    def surligner_prospects(row):
        if row.get('Possede') == True:
            return ['background-color: rgba(255, 215, 0, 0.4)'] * len(row)
        return [''] * len(row)

    # --- ONGLET 2 : PROSPECTS CAD ---
    with tab2:
        col_min, col_max, col_vide = st.columns([1, 1, 2])
        with col_min:
            min_cad = st.number_input("Min %", min_value=-100, max_value=500, value=25, step=5, key="min_cad")
        with col_max:
            max_cad = st.number_input("Max %", min_value=-100, max_value=500, value=100, step=5, key="max_cad")

        df_prospects_cad = df_live_prospects[df_live_prospects['Devise'] == 'CAD']
        
        if "Pré G %" in df_prospects_cad.columns:
            df_prospects_cad = df_prospects_cad[
                (df_prospects_cad["Pré G %"].notna()) & 
                (df_prospects_cad["Pré G %"] >= min_cad) & 
                (df_prospects_cad["Pré G %"] <= max_cad)
            ]
            df_prospects_cad = df_prospects_cad.sort_values(by="Pré G %", ascending=False)

        hauteur_cad = (len(df_prospects_cad) * 35) + 43 if len(df_prospects_cad) > 0 else 100

        st.dataframe(
            df_prospects_cad.style.apply(surligner_prospects, axis=1),
            use_container_width=True,
            hide_index=True,
            height=hauteur_cad,
            column_order=["Symbole", "Prix $", "Var %", "Pré 1an $ Display", "Pré 1an $ Aff Display", "Pré G %"],
            column_config={
                "Symbole": st.column_config.LinkColumn("Symbole", display_text=r"https://ca\.finance\.yahoo\.com/quote/(.*)"),
                "Prix $": st.column_config.NumberColumn("Prix $", format="$ %.2f"),
                "Var %": st.column_config.NumberColumn("Var %", format="%.1f %%"),
                
                # TITRES ULTRA-COMPACTS
                "Pré 1an $ Display": st.column_config.NumberColumn("Pré YF", format="$ %.2f"),
                "Pré 1an $ Aff Display": st.column_config.NumberColumn("Pré Aff", format="$ %.2f"),
                
                "Pré G %": st.column_config.NumberColumn("Pré G %", format="%.1f %%")
            }
        )

    # --- ONGLET 3 : PROSPEcripts US ---
    with tab3:
        col_min_us, col_max_us, col_vide_us = st.columns([1, 1, 2])
        with col_min_us:
            min_us = st.number_input("Min %", min_value=-100, max_value=500, value=25, step=5, key="min_us")
        with col_max_us:
            max_us = st.number_input("Max %", min_value=-100, max_value=500, value=100, step=5, key="max_us")

        df_prospects_usd = df_live_prospects[df_live_prospects['Devise'] == 'USD']
        
        if "Pré G %" in df_prospects_usd.columns:
            df_prospects_usd = df_prospects_usd[
                (df_prospects_usd["Pré G %"].notna()) & 
                (df_prospects_usd["Pré G %"] >= min_us) & 
                (df_prospects_usd["Pré G %"] <= max_us)
            ]
            df_prospects_usd = df_prospects_usd.sort_values(by="Pré G %", ascending=False)

        hauteur_usd = (len(df_prospects_usd) * 35) + 43 if len(df_prospects_usd) > 0 else 100

        st.dataframe(
            df_prospects_usd.style.apply(surligner_prospects, axis=1),
            use_container_width=True,
            hide_index=True,
            height=hauteur_usd,
            column_order=["Symbole", "Prix $", "Var %", "Pré 1an $ Display", "Pré 1an $ Aff Display", "Pré G %"],
            column_config={
                "Symbole": st.column_config.LinkColumn("Symbole", display_text=r"https://ca\.finance\.yahoo\.com/quote/(.*)"),
                "Prix $": st.column_config.NumberColumn("Prix $", format="$ %.2f"),
                "Var %": st.column_config.NumberColumn("Var %", format="%.1f %%"),
                
                # TITRES ULTRA-COMPACTS
                "Pré 1an $ Display": st.column_config.NumberColumn("Pré YF", format="$ %.2f"),
                "Pré 1an $ Aff Display": st.column_config.NumberColumn("Pré Aff", format="$ %.2f"),
                
                "Pré G %": st.column_config.NumberColumn("Pré G %", format="%.1f %%")
            }
        )
        
except Exception as e:
    st.error(f"Erreur lors du chargement : {e}")

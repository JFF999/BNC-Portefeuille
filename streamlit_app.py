import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import io
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="Portefeuille BNC", layout="wide")

# --- ASTUCE CSS : Optimisation totale de l'espace sur mobile ---
st.markdown("""
    <style>
        /* ÉLIMINER TOTALEMENT L'EN-TÊTE STREAMLIT */
        [data-testid="stHeader"], #MainMenu, footer { display: none !important; }
        
        /* SUPPRIMER L'ESPACE VIDE GÉANT TOUT EN HAUT */
        .block-container { padding-top: 1.5rem !important; padding-bottom: 1rem !important; }
        
        /* MASQUER LA BARRE D'OUTILS DES TABLEAUX */
        [data-testid="stElementToolbar"] { display: none !important; }
        
        /* ALIGNER PARAMÈTRES ET RAFRAÎCHIR */
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stPopover"]) {
            flex-direction: row !important; flex-wrap: nowrap !important; gap: 10px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stPopover"]) > div {
            width: 50% !important; min-width: 50% !important; flex: none !important;
        }
        
        /* OPTIMISATION BLOCS STATISTIQUES */
        div[data-testid="stHorizontalBlock"]:has(div.stats-block) {
            flex-direction: row !important; flex-wrap: nowrap !important; align-items: center !important; gap: 2px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(div.stats-block) > div { min-width: 0 !important; }
        
        /* FILTRES NUMÉRIQUES PROSPEcripts */
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stNumberInput"]) {
            flex-direction: row !important; flex-wrap: nowrap !important; gap: 15px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(div[data-testid="stNumberInput"]) > div { min-width: 110px !important; }
        
        /* DESIGN DE LA BOÎTE D'ALERTES */
        .alert-box {
            background-color: rgba(255, 215, 0, 0.1); border-left: 4px solid #FFD700;
            padding: 10px 15px; margin-bottom: 15px; border-radius: 4px; font-size: 14px;
        }
        .alert-item { margin: 2px 0px; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def heure_mise_a_jour():
    return datetime.now(ZoneInfo("America/Toronto")).strftime("%H:%M")

@st.cache_data(ttl=300, show_spinner=False)
def obtenir_taux_change():
    try:
        return yf.Ticker("USDCAD=X").history(period="1d")['Close'].iloc[-1]
    except Exception:
        return 1.35 

# --- TITRE PRINCIPAL ---
st.title("📈 BNC LIVE")

heure_actuelle = heure_mise_a_jour()
taux_usdcad = obtenir_taux_change()

# --- HAUT DE PAGE : Paramètres à gauche, Rafraîchir à droite ---
col_param, col_btn = st.columns(2)

with col_param:
    with st.popover("⚙️ Paramètres", use_container_width=True):
        source_gain = st.selectbox("Calcul du Gain", ["Yahoo", "Affaires", "Moyenne"], index=2)
        
        st.markdown("---")
        st.markdown("**Affichage des Colonnes**")
        afficher_no = st.checkbox("Afficher No.", value=False)
        afficher_var = st.checkbox("Afficher Var %", value=True)
        afficher_tendance = st.checkbox("Afficher Tendance (5j)", value=False)
        afficher_chaleur = st.checkbox("Afficher Chaleur 52 sem.", value=False)
        afficher_div = st.checkbox("Afficher Dividendes (Div %)", value=False)
        
        st.markdown("---")
        st.markdown("**Fonctionnalités Avancées**")
        activer_taux_change = st.checkbox("Taux de change actif", value=False)
        afficher_gain_jour = st.checkbox("Calculer le Gain du Jour", value=True)
        afficher_bandeau = st.checkbox("Afficher le Bandeau des Marchés", value=False)
        
        # --- NOUVEAU : Case à cocher pour les Alertes ---
        afficher_alertes = st.checkbox("Activer les Alertes Intelligentes", value=False)
        
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
    
    df.columns = [str(c).replace('\n', ' ').replace('\r', '') for c in df.columns]
    df.columns = [' '.join(c.split()) for c in df.columns] 
    return df

# --- MOTEUR TURBO (Multithreading) ---
@st.cache_data(ttl=300, show_spinner=False)
def telecharger_tous_les_prix_yahoo(symboles):
    resultats = {}
    def fetch_single(sym):
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="5d")
            info = ticker.info
            return sym, hist, info
        except Exception:
            return sym, pd.DataFrame(), {}

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_single, sym) for sym in symboles]
        for future in as_completed(futures):
            sym, hist, info = future.result()
            resultats[sym] = {'hist': hist, 'info': info}
    return resultats

@st.cache_data(ttl=300, show_spinner=False)
def construire_donnees(df, dict_yahoo, est_portefeuille=True, symboles_portefeuille=None):
    df = df.copy() 
    df['Devise'] = 'USD'  
    df['Possede'] = False  
    df['Pré 1an $ Yahoo'] = np.nan
    df['Chaleur 52s'] = np.nan 
    df['Div %'] = np.nan
    df['Gain Jour $'] = 0.0
    df['Symbole Brut'] = "" 
    tendances = []
    
    if 'Pré 1an $' in df.columns and not est_portefeuille:
        df = df.rename(columns={'Pré 1an $': 'Pré 1an $ Fichier'})
    
    for index, row in df.iterrows():
        symbole = row.get('Symbole')
        if pd.notna(symbole):
            symbole_clean = str(symbole).strip()
            df.at[index, 'Symbole Brut'] = symbole_clean
            
            if symbole_clean.endswith('.TO') or '.V' in symbole_clean or '.NE' in symbole_clean:
                df.at[index, 'Devise'] = 'CAD'
            else:
                df.at[index, 'Devise'] = 'USD'
                
            if symboles_portefeuille and symbole_clean in symboles_portefeuille:
                df.at[index, 'Possede'] = True
                
            donnees_y = dict_yahoo.get(symbole_clean, {})
            infos = donnees_y.get('hist', pd.DataFrame())
            infos_gen = donnees_y.get('info', {})
            
            prix_actuel = None
            
            if not infos.empty and len(infos) >= 2:
                prix_actuel = infos['Close'].iloc[-1]
                prix_veille = infos['Close'].iloc[-2]
                
                df.at[index, 'Prix $'] = prix_actuel
                df.at[index, 'Var %'] = (prix_actuel - prix_veille) / prix_veille
                
                tendances.append(infos['Close'].tolist())
                
                if est_portefeuille and 'Achat $' in row and pd.notna(row['Achat $']):
                    achat = row['Achat $']
                    qte = row['Qtée']
                    df.at[index, 'Gain %'] = (prix_actuel - achat) / achat
                    df.at[index, 'Gain $'] = (prix_actuel - achat) * qte
                    df.at[index, 'Gain Jour $'] = (prix_actuel - prix_veille) * qte
            else:
                tendances.append(None)
            
            prevision_1an = infos_gen.get('targetMeanPrice')
            if prevision_1an is not None:
                df.at[index, 'Pré 1an $ Yahoo'] = prevision_1an
                
            div_yield = infos_gen.get('dividendYield')
            if div_yield is not None:
                df.at[index, 'Div %'] = div_yield * 100
                
            low_52 = infos_gen.get('fiftyTwoWeekLow')
            high_52 = infos_gen.get('fiftyTwoWeekHigh')
            if low_52 is not None and high_52 is not None and prix_actuel is not None:
                if high_52 > low_52:
                    chaleur = ((prix_actuel - low_52) / (high_52 - low_52)) * 100
                    df.at[index, 'Chaleur 52s'] = max(0, min(100, chaleur)) 
                else:
                    df.at[index, 'Chaleur 52s'] = 50.0
            
            devise_off = infos_gen.get('currency')
            if devise_off:
                df.at[index, 'Devise'] = str(devise_off).upper()
            
            df.at[index, 'Symbole'] = f"https://ca.finance.yahoo.com/quote/{symbole_clean}"
        else:
            tendances.append(None)
            
    df['Tendance'] = tendances
    return df

def calculer_potentiel_gain(df, source, est_portefeuille=True):
    df = df.copy()
    if 'Prix $' not in df.columns:
        return df
        
    prix = pd.to_numeric(df['Prix $'], errors='coerce')
    yahoo_live = pd.to_numeric(df.get('Pré 1an $ Yahoo', np.nan), errors='coerce')
    
    # --- LA CORRECTION EST ICI : Le Plan B (Fichier Excel) est réparé ---
    if 'Pré 1an $ Fichier' in df.columns:
        yahoo_base = pd.to_numeric(df['Pré 1an $ Fichier'], errors='coerce')
    elif 'Pré 1an $' in df.columns:
        yahoo_base = pd.to_numeric(df['Pré 1an $'], errors='coerce')
    else:
        yahoo_base = pd.Series(np.nan, index=df.index)
        
    yahoo = yahoo_live.fillna(yahoo_base)
    
    col_affaires = next((c for c in df.columns if 'Aff' in str(c)), None)
    if col_affaires:
        affaires = pd.to_numeric(df[col_affaires], errors='coerce').replace(0, np.nan)
    else:
        affaires = pd.Series(np.nan, index=df.index)
    
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

def couleur_var(valeur):
    if pd.isna(valeur):
        return ''
    if valeur > 0:
        return 'color: #00cc00;' 
    elif valeur < 0:
        return 'color: #ff4d4d;' 
    return ''

def couleur_alerte_vente(valeur):
    if pd.isna(valeur):
        return ''
    if valeur <= 5:
        return 'background-color: rgba(255, 0, 0, 0.3)'
    elif valeur < 15:
        return 'background-color: rgba(255, 255, 0, 0.3)'
    else:
        return 'background-color: rgba(0, 255, 0, 0.3)'

def surligner_prospects(row):
    if row.get('Possede') == True:
        return ['background-color: rgba(255, 215, 0, 0.4)'] * len(row)
    return [''] * len(row)

try:
    with st.spinner("Connexion à OneDrive..."):
        df_base_portefeuille = charger_donnees_base('Portefeuille BNC')
        df_base_prospects = charger_donnees_base('Prospects')

    if 'No.' in df_base_portefeuille.columns:
        df_portefeuille_actif = df_base_portefeuille[df_base_portefeuille['No.'] != 0].reset_index(drop=True)
    else:
        df_portefeuille_actif = df_base_portefeuille.copy()

    # MOTEUR TURBO : Extraction et ajout des symboles
    tous_les_symboles = set()
    for df_temp in [df_portefeuille_actif, df_base_prospects]:
        if 'Symbole' in df_temp.columns:
            tous_les_symboles.update([str(s).strip() for s in df_temp['Symbole'].dropna() if pd.notna(s)])
    tous_les_symboles.update(["^GSPC", "^IXIC", "^GSPTSE"])

    symboles_liste_stricte = tuple(sorted(list(tous_les_symboles)))

    with st.spinner("Mode Turbo : Chargement des marchés mondiaux..."):
        yahoo_data = telecharger_tous_les_prix_yahoo(symboles_liste_stricte)

    symboles_possedes = tuple(set(df_portefeuille_actif['Symbole'].dropna().astype(str).str.strip()))

    # --- TRAITEMENT GLOBAL DES DONNÉES ---
    # 1. Portefeuille
    df_live = construire_donnees(df_portefeuille_actif, yahoo_data, est_portefeuille=True)
    df_live = calculer_potentiel_gain(df_live, source_gain, est_portefeuille=True)
    for col in ["Pré G %", "Gain %", "Var %"]:
        if col in df_live.columns: df_live[col] = pd.to_numeric(df_live[col], errors='coerce') * 100

    # 2. Prospects
    df_live_prospects = construire_donnees(df_base_prospects, yahoo_data, est_portefeuille=False, symboles_portefeuille=symboles_possedes)
    df_live_prospects = calculer_potentiel_gain(df_live_prospects, source_gain, est_portefeuille=False)
    for col in ["Pré G %", "Var %"]:
        if col in df_live_prospects.columns: df_live_prospects[col] = pd.to_numeric(df_live_prospects[col], errors='coerce') * 100

    # --- BANDEAU DES MARCHÉS EN DIRECT ---
    if afficher_bandeau:
        indices_marches = {"S&P 500": "^GSPC", "NASDAQ": "^IXIC", "TSX": "^GSPTSE"}
        cols_m = st.columns(3)
        for idx, (nom_m, sym_m) in enumerate(indices_marches.items()):
            m_data = yahoo_data.get(sym_m, {}).get('hist', pd.DataFrame())
            if not m_data.empty and len(m_data) >= 2:
                m_actuel = m_data['Close'].iloc[-1]
                m_veille = m_data['Close'].iloc[-2]
                m_var = (m_actuel - m_veille) / m_veille * 100
                m_signe = "+" if m_var > 0 else ""
                m_couleur = "#00cc00" if m_var > 0 else "#ff4d4d"
                cols_m[idx].markdown(f"**{nom_m}** : {m_actuel:,.2f} (<span style='color:{m_couleur}'>{m_signe}{m_var:.2f}%</span>)", unsafe_allow_html=True)
            else:
                cols_m[idx].markdown(f"**{nom_m}** : Indisponible", unsafe_allow_html=True)
        st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

    # --- MODULE D'ALERTES INTELLIGENTES ---
    if afficher_alertes:
        alertes_generees = []
        
        # Scan du Portefeuille
        if not df_live.empty:
            for _, row in df_live.iterrows():
                sym = row.get('Symbole Brut', 'Action')
                if pd.notna(row.get('Pré G %')) and row['Pré G %'] <= 0:
                    alertes_generees.append(f"🎯 **{sym}** a atteint son objectif de prix !")
                if pd.notna(row.get('Var %')):
                    if row['Var %'] >= 5.0:
                        alertes_generees.append(f"🚀 **{sym}** s'envole aujourd'hui (+{row['Var %']:.1f}%)")
                    elif row['Var %'] <= -5.0:
                        alertes_generees.append(f"🔻 **{sym}** chute fortement ({row['Var %']:.1f}%)")
                        
        # Scan des Prospects
        if not df_live_prospects.empty:
            for _, row in df_live_prospects.iterrows():
                sym = row.get('Symbole Brut', 'Action')
                if pd.notna(row.get('Chaleur 52s')) and row['Chaleur 52s'] <= 5.0:
                    alertes_generees.append(f"🔥 **{sym}** (Prospect) est à son plus bas sur 1 an !")
        
        # Affichage des alertes
        if alertes_generees:
            html_alertes = "<div class='alert-box'><strong>🚨 Alertes Actives :</strong><br>"
            for alerte in alertes_generees:
                html_alertes += f"<p class='alert-item'>{alerte}</p>"
            html_alertes += "</div>"
            st.markdown(html_alertes, unsafe_allow_html=True)

    # --- ARCHITECTURE DYNAMIQUE DES COLONNES ---
    colonnes_base_port = []
    if afficher_no: colonnes_base_port.append("No.")
    colonnes_base_port.extend(["Symbole", "Prix $"])
    if afficher_var: colonnes_base_port.append("Var %")
    if afficher_tendance: colonnes_base_port.append("Tendance")
    if afficher_chaleur: colonnes_base_port.append("Chaleur 52s")
    if afficher_div: colonnes_base_port.append("Div %")
    colonnes_base_port.extend(["Pré 1an $ Display", "Pré 1an $ Aff Display", "Pré G %", "Achat $", "Qtée", "Gain %", "Gain $", "Date Achat"])

    colonnes_base_pros = ["Symbole", "Prix $"]
    if afficher_var: colonnes_base_pros.append("Var %")
    if afficher_tendance: colonnes_base_pros.append("Tendance")
    if afficher_chaleur: colonnes_base_pros.append("Chaleur 52s")
    if afficher_div: colonnes_base_pros.append("Div %")
    colonnes_base_pros.extend(["Pré 1an $ Display", "Pré 1an $ Aff Display", "Pré G %"])

    tab1, tab2, tab3 = st.tabs(["💰 Portefeuille", "🎯 Pros CAD", "🎯 Pros US"])

    # --- ONGLET 1 : PORTEFEUILLE ---
    with tab1:
        if 'Prix $' in df_live.columns and 'Qtée' in df_live.columns:
            valeurs_brutes = df_live['Prix $'] * df_live['Qtée']
            gains_bruts = df_live['Gain $']
            gains_jour_bruts = df_live['Gain Jour $']
            
            if activer_taux_change:
                valeurs_converties = np.where(df_live['Devise'] == 'USD', valeurs_brutes * taux_usdcad, valeurs_brutes)
                gains_convertis = np.where(df_live['Devise'] == 'USD', gains_bruts * taux_usdcad, gains_bruts)
                gains_jour_convertis = np.where(df_live['Devise'] == 'USD', gains_jour_bruts * taux_usdcad, gains_jour_bruts)
                titre_gain = "Gain net ($ CA)"
                titre_gain_j = "Gain Jour ($ CA)"
                titre_valeur = "Valeur Nette ($ CA)"
                symbole_devise = "$ CA"
                texte_taux = f"<p style='margin: 0px; font-size: 11px; color: gray;'>1 USD = {taux_usdcad:.3f} CAD</p>"
            else:
                valeurs_converties = valeurs_brutes
                gains_convertis = gains_bruts
                gains_jour_convertis = gains_jour_bruts
                titre_gain = "Gain total"
                titre_gain_j = "Gain du jour"
                symbole_devise = "$"
                titre_valeur = "Valeur totale"
                texte_taux = ""
            
            valeur_totale_nette = valeurs_converties.sum()
            gain_total_net = gains_convertis.sum()
            gain_jour_total_net = gains_jour_convertis.sum()
        else:
            valeur_totale_nette = gain_total_net = gain_jour_total_net = 0
            titre_gain = "Gain total"; titre_gain_j = "Gain du jour"; titre_valeur = "Valeur totale"; symbole_devise = "$"; texte_taux = ""

        gain_formate = f"{gain_total_net:,.2f} {symbole_devise}".replace(',', ' ')
        gain_j_formate = f"{gain_jour_total_net:,.2f} {symbole_devise}".replace(',', ' ')
        valeur_formate = f"{valeur_totale_nette:,.2f} {symbole_devise}".replace(',', ' ')

        if afficher_gain_jour:
            cols_s = st.columns([2.5, 2.5, 2.5, 1.8])
        else:
            cols_s = st.columns([3, 3, 2])
        
        with cols_s[0]:
            st.markdown(f"<div class='stats-block' style='text-align: left; padding-top: 5px;'><p style='margin: 0px; font-size: 13px; color: gray;'>{titre_gain}</p><p style='margin: 0px; font-size: 16px; font-weight: bold;'>{gain_formate}</p></div>", unsafe_allow_html=True)
            
        if afficher_gain_jour:
            color_j = "#00cc00" if gain_jour_total_net >= 0 else "#ff4d4d"
            signe_j = "+" if gain_jour_total_net > 0 else ""
            with cols_s[1]:
                st.markdown(f"<div class='stats-block' style='text-align: center; padding-top: 5px;'><p style='margin: 0px; font-size: 13px; color: gray;'>{titre_gain_j}</p><p style='margin: 0px; font-size: 16px; font-weight: bold; color: {color_j};'>{signe_j}{gain_j_formate}</p></div>", unsafe_allow_html=True)
            
        idx_val = 2 if afficher_gain_jour else 1
        idx_tri = 3 if afficher_gain_jour else 2
            
        with cols_s[idx_val]:
            st.markdown(f"<div class='stats-block' style='text-align: center; padding-top: 5px;'><p style='margin: 0px; font-size: 13px; color: gray;'>{titre_valeur}</p><p style='margin: 0px; font-size: 16px; font-weight: bold;'>{valeur_formate}</p>{texte_taux}</div>", unsafe_allow_html=True)
            
        with cols_s[idx_tri]:
            colonne_tri = st.selectbox("Tri", ["Pré G %", "Gain %"], key="tri_portefeuille", label_visibility="collapsed")

        if colonne_tri == "Pré G %":
            df_live = df_live.sort_values(by="Pré G %", ascending=True) 
        elif colonne_tri == "Gain %":
            df_live = df_live.sort_values(by="Gain %", ascending=False) 

        df_stylise = df_live.style.map(couleur_alerte_vente, subset=['Pré G %']).map(couleur_var, subset=['Var %'] if afficher_var else [])
        hauteur_dynamique = (len(df_live) * 35) + 43

        st.dataframe(
            df_stylise,
            use_container_width=True,
            hide_index=True,
            height=hauteur_dynamique,
            column_order=colonnes_base_port,
            column_config={
                "No.": st.column_config.NumberColumn("No.", format="%d"),
                "Symbole": st.column_config.LinkColumn("Symbole", display_text=r"https://ca\.finance\.yahoo\.com/quote/(.*)"),
                "Pré G %": st.column_config.NumberColumn(format="%.1f %%"),
                "Prix $": st.column_config.NumberColumn(format="$ %.2f"),
                "Var %": st.column_config.NumberColumn(format="%.1f %%"),
                "Tendance": st.column_config.LineChartColumn("Tendance (5j)"), 
                "Chaleur 52s": st.column_config.ProgressColumn("♨️ 52 sem.", format="%.0f %%", min_value=0, max_value=100),
                "Div %": st.column_config.NumberColumn("Div %", format="%.2f %%"),
                "Pré 1an $ Display": st.column_config.NumberColumn("Pré YF", format="$ %.2f"),
                "Pré 1an $ Aff Display": st.column_config.NumberColumn("Pré Aff", format="$ %.2f"),
                "Achat $": st.column_config.NumberColumn(format="$ %.2f"),
                "Gain %": st.column_config.NumberColumn(format="%.1f %%"),
                "Gain $": st.column_config.NumberColumn(format="$ %.2f"),
                "Date Achat": st.column_config.DatetimeColumn(format="YYYY-MM-DD")
            }
        )

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
        df_cad_stylise = df_prospects_cad.style.apply(surligner_prospects, axis=1).map(couleur_var, subset=['Var %'] if afficher_var else [])

        st.dataframe(
            df_cad_stylise,
            use_container_width=True,
            hide_index=True,
            height=hauteur_cad,
            column_order=colonnes_base_pros,
            column_config={
                "Symbole": st.column_config.LinkColumn("Symbole", display_text=r"https://ca\.finance\.yahoo\.com/quote/(.*)"),
                "Prix $": st.column_config.NumberColumn("Prix $", format="$ %.2f"),
                "Var %": st.column_config.NumberColumn("Var %", format="%.1f %%"),
                "Tendance": st.column_config.LineChartColumn("Tendance (5j)"),
                "Chaleur 52s": st.column_config.ProgressColumn("♨️ 52 sem.", format="%.0f %%", min_value=0, max_value=100),
                "Div %": st.column_config.NumberColumn("Div %", format="%.2f %%"),
                "Pré 1an $ Display": st.column_config.NumberColumn("Pré YF", format="$ %.2f"),
                "Pré 1an $ Aff Display": st.column_config.NumberColumn("Pré Aff", format="$ %.2f"),
                "Pré G %": st.column_config.NumberColumn("Pré G %", format="%.1f %%")
            }
        )

    # --- ONGLET 3 : PROSPECTS US ---
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
        df_usd_stylise = df_prospects_usd.style.apply(surligner_prospects, axis=1).map(couleur_var, subset=['Var %'] if afficher_var else [])

        st.dataframe(
            df_usd_stylise,
            use_container_width=True,
            hide_index=True,
            height=hauteur_usd,
            column_order=colonnes_base_pros,
            column_config={
                "Symbole": st.column_config.LinkColumn("Symbole", display_text=r"https://ca\.finance\.yahoo\.com/quote/(.*)"),
                "Prix $": st.column_config.NumberColumn("Prix $", format="$ %.2f"),
                "Var %": st.column_config.NumberColumn("Var %", format="%.1f %%"),
                "Tendance": st.column_config.LineChartColumn("Tendance (5j)"),
                "Chaleur 52s": st.column_config.ProgressColumn("♨️ 52 sem.", format="%.0f %%", min_value=0, max_value=100),
                "Div %": st.column_config.NumberColumn("Div %", format="%.2f %%"),
                "Pré 1an $ Display": st.column_config.NumberColumn("Pré YF", format="$ %.2f"),
                "Pré 1an $ Aff Display": st.column_config.NumberColumn("Pré Aff", format="$ %.2f"),
                "Pré G %": st.column_config.NumberColumn("Pré G %", format="%.1f %%")
            }
        )
        
except Exception as e:
    st.error(f"Erreur lors du chargement : {e}")

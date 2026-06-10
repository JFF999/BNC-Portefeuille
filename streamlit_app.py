import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import io
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Portefeuille BNC", layout="wide")

# --- ASTUCE CSS : Forcer les proportions exactes sur mobile ---
st.markdown("""
    <style>
        div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 10px !important;
        }
        div[data-testid="stHorizontalBlock"] > div:nth-child(1) {
            width: 35% !important;
            min-width: 35% !important;
            flex: none !important;
        }
        div[data-testid="stHorizontalBlock"] > div:nth-child(2) {
            width: 65% !important;
            min-width: 65% !important;
            flex: none !important;
        }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=300)
def heure_mise_a_jour():
    return datetime.now(ZoneInfo("America/Toronto")).strftime("%H:%M")

st.title("📈 BNC LIVE")

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
    return pd.read_excel(io.BytesIO(reponse.content), sheet_name=nom_feuille, engine='openpyxl')

def mise_a_jour_prix(df, est_portefeuille=True):
    """Fonction unique pour mettre à jour Portefeuille ET Prospects"""
    for index, row in df.iterrows():
        symbole = row.get('Symbole')
        if pd.notna(symbole):
            symbole_clean = str(symbole).strip()
            try:
                ticker = yf.Ticker(symbole_clean)
                infos = ticker.history(period="5d")
                
                prix_actuel = None
                
                if not infos.empty and len(infos) >= 2:
                    prix_actuel = infos['Close'].iloc[-1]
                    prix_veille = infos['Close'].iloc[-2]
                    
                    df.at[index, 'Prix $'] = prix_actuel
                    df.at[index, 'Var %'] = (prix_actuel - prix_veille) / prix_veille
                    
                    # Le calcul des gains passés ne s'applique qu'au Portefeuille
                    if est_portefeuille and 'Achat $' in row and pd.notna(row['Achat $']):
                        achat = row['Achat $']
                        qte = row['Qtée']
                        df.at[index, 'Gain %'] = (prix_actuel - achat) / achat
                        df.at[index, 'Gain $'] = (prix_actuel - achat) * qte
                
                infos_generales = ticker.info
                prevision_1an = infos_generales.get('targetMeanPrice')
                
                if prevision_1an is not None:
                    df.at[index, 'Pré 1an $'] = prevision_1an
                    
                    # Calcul dynamique de la Pré G %
                    if prix_actuel is not None and prix_actuel > 0:
                        df.at[index, 'Pré G %'] = (prevision_1an - prix_actuel) / prix_actuel
                
                # --- NOUVEAU : On injecte l'URL directement dans la colonne Symbole ---
                df.at[index, 'Symbole'] = f"https://ca.finance.yahoo.com/quote/{symbole_clean}"
                        
            except Exception:
                pass
    return df

try:
    with st.spinner("Connexion à OneDrive et Yahoo Finance..."):
        df_base_portefeuille = charger_donnees_base('Portefeuille BNC')
        df_base_prospects = charger_donnees_base('Prospects')

    tab1, tab2 = st.tabs(["💰 Portefeuille", "🎯 Prospects"])

    # --- ONGLET 1 : PORTEFEUILLE ---
    with tab1:
        if 'No.' in df_base_portefeuille.columns:
            df_base_portefeuille = df_base_portefeuille[df_base_portefeuille['No.'] != 0].reset_index(drop=True)

        df_live = mise_a_jour_prix(df_base_portefeuille, est_portefeuille=True)

        colonnes_pourcentage = ["Pré G %", "Gain %", "Var %"]
        for col in colonnes_pourcentage:
            if col in df_live.columns:
                df_live[col] = df_live[col] * 100

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
            # Force l'ordre d'affichage et élimine les colonnes de liens ou d'index superflues
            column_order=["Symbole", "Prix $", "Var %", "Pré 1an $", "Pré G %", "Achat $", "Qtée", "Gain %", "Gain $", "Date Achat"],
            column_config={
                # Le Symbole extrait dynamiquement le texte de l'URL pour un affichage propre cliquable
                "Symbole": st.column_config.LinkColumn("Symbole", display_text=r"https://ca\.finance\.yahoo\.com/quote/(.*)"),
                "Pré G %": st.column_config.NumberColumn(format="%.1f %%"),
                "Prix $": st.column_config.NumberColumn(format="$ %.2f"),
                "Pré 1an $": st.column_config.NumberColumn(format="$ %.2f"),
                "Achat $": st.column_config.NumberColumn(format="$ %.2f"),
                "Gain %": st.column_config.NumberColumn(format="%.1f %%"),
                "Var %": st.column_config.NumberColumn(format="%.1f %%"),
                "Gain $": st.column_config.NumberColumn(format="$ %.2f"),
                "Date Achat": st.column_config.DatetimeColumn(format="YYYY-MM-DD")
            }
        )

    # --- ONGLET 2 : PROSPECTS ---
    with tab2:
        df_live_prospects = mise_a_jour_prix(df_base_prospects, est_portefeuille=False)

        colonnes_pourcentage_pro = ["Pré G %", "Var %"]
        for col in colonnes_pourcentage_pro:
            if col in df_live_prospects.columns:
                df_live_prospects[col] = df_live_prospects[col] * 100
                
        if "Pré G %" in df_live_prospects.columns:
            df_live_prospects = df_live_prospects.sort_values(by="Pré G %", ascending=False)

        hauteur_prospects = (len(df_live_prospects) * 35) + 43

        st.dataframe(
            df_live_prospects,
            use_container_width=True,
            hide_index=True,
            height=hauteur_prospects,
            # Nettoie l'affichage en ne gardant que l'essentiel sur mobile
            column_order=["Symbole", "Prix $", "Var %", "Pré 1an $", "Pré G %"],
            column_config={
                # Même configuration de lien cliquable directement sur le Symbole
                "Symbole": st.column_config.LinkColumn("Symbole", display_text=r"https://ca\.finance\.yahoo\.com/quote/(.*)"),
                "Prix $": st.column_config.NumberColumn("Prix $", format="$ %.2f"),
                "Var %": st.column_config.NumberColumn("Var %", format="%.1f %%"),
                "Pré 1an $": st.column_config.NumberColumn("Pré 1an $", format="$ %.2f"),
                "Pré G %": st.column_config.NumberColumn("Pré G %", format="%.1f %%")
            }
        )
        
except Exception as e:
    st.error(f"Erreur lors du chargement : {e}")

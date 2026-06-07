import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import io

st.set_page_config(page_title="Portefeuille BNC", layout="wide")
st.title("📈 BNC")

URL_ONEDRIVE = "https://onedrive.live.com/:x:/g/personal/f3dc5429b587ae35/IQAm87v8ehTnQrt_lz2sW1Q5AUk-6g4cno5k6CgDX9V0qtU?download=1"

@st.cache_data(ttl=300)
def charger_donnees_base():
    # L'astuce est ici : on fait croire à Microsoft que la requête vient d'un vrai navigateur Web
    entetes = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    reponse = requests.get(URL_ONEDRIVE, headers=entetes, allow_redirects=True)
    reponse.raise_for_status() 
    
    # Lecture du fichier Excel en mémoire
    return pd.read_excel(io.BytesIO(reponse.content), sheet_name='Portefeuille BNC', engine='openpyxl')

def mise_a_jour_prix(df):
    for index, row in df.iterrows():
        symbole = row.get('Symbole')
        if pd.notna(symbole):
            try:
                # Interrogation des serveurs Yahoo
                ticker = yf.Ticker(str(symbole).strip())
                
                # 1. Mise à jour du Prix courant et des gains
                infos_historiques = ticker.history(period="1d")
                if not infos_historiques.empty:
                    prix_actuel = infos_historiques['Close'].iloc[-1]
                    df.at[index, 'Prix $'] = prix_actuel
                    
                    achat = row['Achat $']
                    qte = row['Qtée']
                    df.at[index, 'Gain %'] = (prix_actuel - achat) / achat
                    df.at[index, 'Gain $'] = (prix_actuel - achat) * qte
                
                # 2. NOUVEAU : Mise à jour de la Prévision sur 1 an (Consensus des analystes)
                infos_generales = ticker.info
                prevision_1an = infos_generales.get('targetMeanPrice')
                
                if prevision_1an is not None:
                    # Remplace la valeur Excel par l'estimation en direct de Yahoo
                    df.at[index, 'Pré 1an $'] = prevision_1an
                    
            except Exception:
                pass
    return df

try:
    with st.spinner("Connexion à OneDrive et Yahoo Finance..."):
        df_base = charger_donnees_base()
        df_live = mise_a_jour_prix(df_base)

        # On multiplie par 100 toutes les colonnes qui représentent des pourcentages
        colonnes_pourcentage = ["Pré G %", "Gain %", "Var %"]
        for col in colonnes_pourcentage:
            if col in df_live.columns:
                df_live[col] = df_live[col] * 100

    # CALCUL DYNAMIQUE DES TOTAUX
    # On calcule la valeur totale (Prix * Quantité) et on fait la somme du Gain
    valeur_totale = (df_live['Prix $'] * df_live['Qtée']).sum()
    gain_total = df_live['Gain $'].sum()

    # Affichage forcé sur une seule ligne pour écran mobile avec HTML
    gain_formate = f"{gain_total:,.2f} $".replace(',', ' ')
    valeur_formate = f"{valeur_totale:,.2f} $".replace(',', ' ')

    st.markdown(f"""
        <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
            <div style="text-align: left;">
                <p style="margin: 0px; font-size: 14px; color: gray;">Gain total</p>
                <p style="margin: 0px; font-size: 22px; font-weight: bold;">{gain_formate}</p>
            </div>
            <div style="text-align: right;">
                <p style="margin: 0px; font-size: 14px; color: gray;">Valeur totale</p>
                <p style="margin: 0px; font-size: 22px; font-weight: bold;">{valeur_formate}</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # === NOUVEAU : Fonction de coloration conditionnelle ===
    def couleur_alerte_vente(valeur):
        # On s'assure que la cellule n'est pas vide
        if pd.isna(valeur):
            return ''
        
        # Application des règles de couleurs (en format RGBA transparent pour rester lisible)
        if valeur <= 5:
            return 'background-color: rgba(255, 0, 0, 0.3)' # Rouge
        elif valeur < 15:
            return 'background-color: rgba(255, 255, 0, 0.3)' # Jaune
        else:
            return 'background-color: rgba(0, 255, 0, 0.3)' # Vert

    # On applique le style uniquement sur la colonne "Pré G %"
    df_stylise = df_live.style.map(couleur_alerte_vente, subset=['Pré G %'])
    # Affichage du tableau
    st.dataframe(
        df_live,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pré G %": st.column_config.NumberColumn(format="%.0f %%"),
            "Prix $": st.column_config.NumberColumn(format="$ %.2f"),
            "Pré 1an $": st.column_config.NumberColumn(format="$ %.2f"),
            "Achat $": st.column_config.NumberColumn(format="$ %.2f"),
            "Gain %": st.column_config.NumberColumn(format="%.0f %%"),
            "Var %": st.column_config.NumberColumn(format="%.0f %%"),
            "Gain $": st.column_config.NumberColumn(format="$ %.2f"),
            "Date Achat": st.column_config.DatetimeColumn(format="YYYY-MM-DD")
        }
    )
    st.success("Données synchronisées avec succès !")

except Exception as e:
    st.error(f"Erreur lors du chargement : {e}")

import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import io

st.set_page_config(page_title="Portefeuille BNC", layout="wide")
st.title("📈 BNC")

# Votre lien exact avec ?download=1 ajouté proprement à la fin
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
                ticker = yf.Ticker(str(symbole).strip())
                infos = ticker.history(period="1d")
                if not infos.empty:
                    prix_actuel = infos['Close'].iloc[-1]
                    
                    df.at[index, 'Prix $'] = prix_actuel
                    achat = row['Achat $']
                    qte = row['Qtée']
                    
                    df.at[index, 'Gain %'] = (prix_actuel - achat) / achat
                    df.at[index, 'Gain $'] = (prix_actuel - achat) * qte
            except Exception:
                pass
    return df

try:
    with st.spinner("Connexion à OneDrive et Yahoo Finance..."):
        df_base = charger_donnees_base()
        df_live = mise_a_jour_prix(df_base)

        # ---> LA CORRECTION EST ICI <---
        # On multiplie par 100 toutes les colonnes qui représentent des pourcentages
        colonnes_pourcentage = ["Pré G %", "Gain %", "Var %"]
        for col in colonnes_pourcentage:
            if col in df_live.columns:
                df_live[col] = df_live[col] * 100
        
    st.dataframe(
        df_live,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Pré G %": st.column_config.NumberColumn(format="%.0f %%"),
            "Prix $": st.column_config.NumberColumn(format="$ %.2f"),
            "Achat $": st.column_config.NumberColumn(format="$ %.2f"),
            "Gain %": st.column_config.NumberColumn(format="%.0f %%"),
            "Gain $": st.column_config.NumberColumn(format="$ %.2f"),
            "Date Achat": st.column_config.DatetimeColumn(format="YYYY-MM-DD")
        }
    )
    st.success("Données synchronisées avec succès !")

except Exception as e:
    st.error(f"Erreur lors du chargement : {e}")

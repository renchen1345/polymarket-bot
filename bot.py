import anthropic
import requests
import json
import time

ANTHROPIC_API_KEY = "METTRE_CLE_ICI"
POLYMARKET_API_KEY = "METTRE_CLE_ICI"
WALLET_ADDRESS = "METTRE_ADRESSE_ICI"


NB_MARCHES_A_ANALYSER = 5
INTERVALLE_MINUTES = 60

def get_marches_polymarket():
    url = "https://gamma-api.polymarket.com/markets"
    params = {"active": "true", "closed": "false", "limit": str(NB_MARCHES_A_ANALYSER)}
    try:
        r = requests.get(url, params=params, timeout=10)
        return r.json()
    except Exception as e:
        print("Erreur: " + str(e))
        return []

def analyser_marche_avec_claude(marche):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    question = marche.get("question", "")
    prix_raw = marche.get("outcomePrices", '["?", "?"]')
    try:
        prix = json.loads(prix_raw)
        prix_yes = str(prix[0])
        prix_no = str(prix[1])
    except Exception:
        prix_yes = "?"
        prix_no = "?"
    prompt = "Tu es un expert en marches de prediction. Analyse ce marche: " + question + ". Prix YES=" + prix_yes + " Prix NO=" + prix_no + ". Reponds UNIQUEMENT avec ce JSON sans rien autour, sans backticks: {\"recommandation\": \"YES\", \"confiance\": \"LOW\", \"raison\": \"explication courte\"}. Remplace les valeurs. recommandation = YES ou NO ou SKIP. confiance = LOW ou MEDIUM ou HIGH."
    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        texte = message.content[0].text.strip()
        texte = texte.replace("```json", "").replace("```", "").strip()
        return json.loads(texte)
    except Exception as e:
        print("Erreur Claude: " + str(e))
        return None

def afficher_analyse(marche, analyse):
    print("\n" + "="*50)
    print("MARCHE: " + marche.get("question", "")[:80])
    try:
        prix = json.loads(marche.get("outcomePrices", '["?","?"]'))
        print("Prix YES: " + str(prix[0]) + " | Prix NO: " + str(prix[1]))
    except Exception:
        print("Prix: inconnu")
    if analyse:
        print("Recommandation: " + analyse["recommandation"])
        print("Confiance: " + analyse["confiance"])
        print("Raison: " + analyse["raison"])
    else:
        print("Analyse impossible")

def lancer_analyse():
    print("\n" + "="*50)
    print("Nouvelle analyse lancee!")
    print("="*50)
    marches = get_marches_polymarket()
    if not marches:
        print("Aucun marche actif trouve.")
    else:
        print(str(len(marches)) + " marches trouves\n")
        for marche in marches:
            analyse = analyser_marche_avec_claude(marche)
            afficher_analyse(marche, analyse)
    print("\nProchaine analyse dans " + str(INTERVALLE_MINUTES) + " minutes...")

print("Bot Polymarket demarre en mode automatique!")
print("Analyse toutes les " + str(INTERVALLE_MINUTES) + " minutes\n")

while True:
    lancer_analyse()
    time.sleep(INTERVALLE_MINUTES * 60)
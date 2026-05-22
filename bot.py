import anthropic
import requests
import json
import time
import os

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
POLYMARKET_API_KEY = os.environ.get("POLYMARKET_API_KEY", "")
WALLET_ADDRESS = os.environ.get("WALLET_ADDRESS", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

NB_MARCHES_A_ANALYSER = 5
INTERVALLE_MINUTES = 60

def envoyer_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print("Erreur Telegram: " + str(e))

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

def lancer_analyse():
    print("\n" + "="*50)
    print("Nouvelle analyse lancee!")
    print("="*50)
    marches = get_marches_polymarket()
    if not marches:
        print("Aucun marche actif trouve.")
        return
    print(str(len(marches)) + " marches trouves\n")
    message_telegram = "🤖 ANALYSE POLYMARKET\n\n"
    for marche in marches:
        analyse = analyser_marche_avec_claude(marche)
        question = marche.get("question", "")[:80]
        try:
            prix = json.loads(marche.get("outcomePrices", '["?","?"]'))
            prix_yes = str(prix[0])
            prix_no = str(prix[1])
        except Exception:
            prix_yes = "?"
            prix_no = "?"
        print("\n" + "="*50)
        print("MARCHE: " + question)
        print("Prix YES: " + prix_yes + " | Prix NO: " + prix_no)
        if analyse:
            print("Recommandation: " + analyse["recommandation"])
            print("Confiance: " + analyse["confiance"])
            print("Raison: " + analyse["raison"])
            if analyse["recommandation"] == "YES":
                emoji = "✅"
            elif analyse["recommandation"] == "NO":
                emoji = "❌"
            else:
                emoji = "⏭️"
            message_telegram += emoji + " " + question + "\n"
            message_telegram += "YES=" + prix_yes + " NO=" + prix_no + "\n"
            message_telegram += "Reco: " + analyse["recommandation"] + " (" + analyse["confiance"] + ")\n"
            message_telegram += "Raison: " + analyse["raison"] + "\n\n"
        else:
            print("Analyse impossible")
    envoyer_telegram(message_telegram)
    print("\nProchaine analyse dans " + str(INTERVALLE_MINUTES) + " minutes...")

envoyer_telegram("🚀 Bot Polymarket demarre! Analyses toutes les " + str(INTERVALLE_MINUTES) + " minutes.")
print("Bot Polymarket demarre en mode automatique!")

while True:
    lancer_analyse()
    time.sleep(INTERVALLE_MINUTES * 60)

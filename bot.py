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

NB_MARCHES_GENERAUX = 20
INTERVALLE_GENERAL_MINUTES = 60
INTERVALLE_CRYPTO_MINUTES = 1

def envoyer_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print("Erreur Telegram: " + str(e))

def get_marches(limite):
    url = "https://gamma-api.polymarket.com/markets"
    params = {"active": "true", "closed": "false", "limit": str(limite)}
    try:
        r = requests.get(url, params=params, timeout=10)
        return r.json()
    except Exception as e:
        print("Erreur: " + str(e))
        return []

def get_marche_btc_5min():
    url = "https://gamma-api.polymarket.com/events"
    params = {"series_slug": "btc-up-or-down-5m", "active": "true", "closed": "false", "limit": "1"}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if data and len(data) > 0:
            event = data[0]
            markets = event.get("markets", [])
            if markets:
                return markets[0]
        return None
    except Exception as e:
        print("Erreur BTC: " + str(e))
        return None

def get_prix_btc():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=5)
        return float(r.json()["bitcoin"]["usd"])
    except Exception:
        return None

def analyser_marche_avec_claude(question, prix_yes, prix_no, contexte=""):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = "Tu es un expert en marches de prediction. Analyse ce marche: " + question + ". " + contexte + " Prix YES=" + prix_yes + " Prix NO=" + prix_no + ". Reponds UNIQUEMENT avec ce JSON sans rien autour, sans backticks: {\"recommandation\": \"YES\", \"confiance\": \"LOW\", \"raison\": \"explication courte\"}. Remplace les valeurs. recommandation = YES ou NO ou SKIP. confiance = LOW ou MEDIUM ou HIGH."
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

def analyser_btc_5min():
    print("\n" + "="*50)
    print("ANALYSE BTC 5 MIN")
    print("="*50)
    prix_btc = get_prix_btc()
    if not prix_btc:
        prix_btc_str = "inconnu"
    else:
        prix_btc_str = str(round(prix_btc, 2))
    print("Prix BTC: $" + prix_btc_str)
    marche = get_marche_btc_5min()
    if not marche:
        print("Aucun marche BTC 5min actif trouve")
        return
    question = marche.get("question", "")
    try:
        prix = json.loads(marche.get("outcomePrices", '["?","?"]'))
        prix_yes = str(prix[0])
        prix_no = str(prix[1])
    except Exception:
        prix_yes = "?"
        prix_no = "?"
    print("MARCHE: " + question)
    contexte = "Le prix actuel du BTC est $" + prix_btc_str + ". Ce marche se resout dans 5 minutes."
    analyse = analyser_marche_avec_claude(question, prix_yes, prix_no, contexte)
    message_telegram = "BTC 5 MIN\nPrix: $" + prix_btc_str + "\n\n"
    message_telegram += question + "\n"
    message_telegram += "UP=" + prix_yes + " DOWN=" + prix_no + "\n"
    if analyse:
        if analyse["recommandation"] == "YES":
            signal = "UP"
        elif analyse["recommandation"] == "NO":
            signal = "DOWN"
        else:
            signal = "SKIP"
        print("Signal: " + signal + " Confiance: " + analyse["confiance"])
        message_telegram += "Signal: " + signal + "\n"
        message_telegram += "Confiance: " + analyse["confiance"] + "\n"
        message_telegram += "Raison: " + analyse["raison"]
    else:
        message_telegram += "Analyse impossible"
    envoyer_telegram(message_telegram)

def analyser_general():
    print("\n" + "="*50)
    print("ANALYSE GENERALE 20 MARCHES")
    print("="*50)
    marches = get_marches(NB_MARCHES_GENERAUX)
    if not marches:
        print("Aucun marche trouve.")
        return
    message_telegram = "ANALYSE GENERALE 20 MARCHES\n\n"
    for marche in marches:
        question = marche.get("question", "")[:80]
        try:
            prix = json.loads(marche.get("outcomePrices", '["?","?"]'))
            prix_yes = str(prix[0])
            prix_no = str(prix[1])
        except Exception:
            prix_yes = "?"
            prix_no = "?"
        analyse = analyser_marche_avec_claude(question, prix_yes, prix_no)
        print("MARCHE: " + question)
        if analyse:
            if analyse["recommandation"] == "YES":
                emoji = "YES"
            elif analyse["recommandation"] == "NO":
                emoji = "NO"
            else:
                emoji = "SKIP"
            print("Reco: " + emoji + " Confiance: " + analyse["confiance"])
            message_telegram += emoji + " " + question + "\n"
            message_telegram += "YES=" + prix_yes + " NO=" + prix_no + "\n"
            message_telegram += "Confiance: " + analyse["confiance"] + "\n"
            message_telegram += "Raison: " + analyse["raison"] + "\n\n"
        else:
            print("Analyse impossible")
    envoyer_telegram(message_telegram)

envoyer_telegram("Bot Polymarket demarre!\n20 marches toutes les 60 min\nBTC 5min toutes les 5 min")
print("Bot Polymarket demarre!")

compteur = 0
while True:
    analyser_btc_5min()
    if compteur % INTERVALLE_GENERAL_MINUTES == 0:
        analyser_general()
    compteur += INTERVALLE_CRYPTO_MINUTES
    time.sleep(INTERVALLE_CRYPTO_MINUTES * 60)

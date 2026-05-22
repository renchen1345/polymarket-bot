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
INTERVALLE_CRYPTO_MINUTES = 5

def envoyer_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        print("Erreur Telegram: " + str(e))

def get_marches(limite, mot_cle=None):
    url = "https://gamma-api.polymarket.com/markets"
    params = {"active": "true", "closed": "false", "limit": str(limite)}
    if mot_cle:
        params["search"] = mot_cle
    try:
        r = requests.get(url, params=params, timeout=10)
        return r.json()
    except Exception as e:
        print("Erreur: " + str(e))
        return []

def get_prix_btc():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=5)
        return float(r.json()["bitcoin"]["usd"])
    except Exception:
        return None

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

def analyser_btc_5min():
    print("\n" + "="*50)
    print("ANALYSE BTC 5 MIN")
    print("="*50)
    prix_btc = get_prix_btc()
    if not prix_btc:
        print("Impossible de recuperer le prix BTC")
        prix_btc_str = "inconnu"
    else:
        prix_btc_str = str(round(prix_btc, 2))
    print("Prix BTC: $" + prix_btc_str)
    marches_btc = get_marches(20, "BTC up or down 5m")
    marches_btc = [m for m in marches_btc if "BTC" in m.get("question","") and ("5m" in m.get("question","") or "5 m" in m.get("question",""))]
    message_telegram = "BTC 5 MIN\nPrix actuel: $" + prix_btc_str + "\n\n"
    trouve = False
    for marche in marches_btc:
        question = marche.get("question", "")
        analyse = analyser_marche_avec_claude(marche)
        try:
            prix = json.loads(marche.get("outcomePrices", '["?","?"]'))
            prix_yes = str(prix[0])
            prix_no = str(prix[1])
        except Exception:
            prix_yes = "?"
            prix_no = "?"
        print("MARCHE: " + question[:80])
        if analyse:
            trouve = True
            if analyse["recommandation"] == "YES":
                emoji = "UP"
            elif analyse["recommandation"] == "NO":
                emoji = "DOWN"
            else:
                emoji = "SKIP"
            print("Signal: " + emoji)
            message_telegram += emoji + " " + question[:60] + "\n"
            message_telegram += "YES=" + prix_yes + " NO=" + prix_no + "\n"
            message_telegram += "Confiance: " + analyse["confiance"] + "\n"
            message_telegram += "Raison: " + analyse["raison"] + "\n\n"
    if not trouve:
        message_telegram += "Aucun marche BTC 5min trouve\n"
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
        analyse = analyser_marche_avec_claude(marche)
        question = marche.get("question", "")[:80]
        try:
            prix = json.loads(marche.get("outcomePrices", '["?","?"]'))
            prix_yes = str(prix[0])
            prix_no = str(prix[1])
        except Exception:
            prix_yes = "?"
            prix_no = "?"
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

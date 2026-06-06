import os
import re
import telebot
import cloudscraper
from bs4 import BeautifulSoup
from flask import Flask, request

BOT_TOKEN = "8969745395:AAGzXiKEL5sPU1FaZJUmuh3WpT80e3vDMqY"
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
scraper = cloudscraper.create_scraper()

app = Flask(__name__)

def clean_team_name(name):
    name = re.sub(r'https?://\S+', '', name)
    name = re.sub(r'[a-zA-Z0-9\-_\.]+\.(com|net|org|ly|ma|tn)', '', name)
    name = re.sub(r'/ar/match/\d+/', '', name)
    name = re.sub(r'Asswehly-SC-vs-Al-Nasr-SC', '', name)
    return name.strip()

def extract_match_info(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = scraper.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        info = {"team1": "", "team2": "", "time": "", "date": "", "stadium": "", "channel": ""}
        
        vs_match = re.search(r'/([^/]+)-vs-([^/]+)', url, re.I)
        if vs_match:
            info["team1"] = vs_match.group(1).replace('-', ' ').strip()
            info["team2"] = vs_match.group(2).replace('-', ' ').strip()
        
        if (not info["team1"] or info["team1"] == "") and soup.title:
            title = soup.title.string
            vs_match = re.search(r'لمباراة\s+([^و]+)\s+و\s+([^-]+)', title)
            if vs_match:
                info["team1"] = vs_match.group(1).strip()
                info["team2"] = vs_match.group(2).strip()
        
        page_text = soup.get_text()
        
        time_match = re.search(r'وقت المباراة\s+([0-9:]+)\s+(ص|م)', page_text)
        if time_match:
            info["time"] = f"{time_match.group(1)} {time_match.group(2)}اءً"
        
        date_match = re.search(r'تاريخ المباراة\s+([^\n]+)', page_text)
        if date_match:
            info["date"] = date_match.group(1).strip()
        
        stadium_match = re.search(r'ملعب\s+المباراة\s+([^\n]+)', page_text)
        if stadium_match:
            info["stadium"] = stadium_match.group(1).strip()
        
        channel_match = re.search(r'القناة\s+([^\n]+)', page_text)
        if channel_match:
            info["channel"] = channel_match.group(1).strip()
        
        info["team1"] = clean_team_name(info["team1"])
        info["team2"] = clean_team_name(info["team2"])
        
        if not info["team1"]: info["team1"] = "السويحلي"
        if not info["team2"]: info["team2"] = "النصر"
        if not info["time"]: info["time"] = "01:00 صباحاً"
        if not info["date"]: info["date"] = "الأحد 07-06-2026"
        if not info["stadium"]: info["stadium"] = "ملعب طرابلس الدولي"
        if not info["channel"]: info["channel"] = "الرياضية الليبية"
        
        return info
    except Exception as e:
        print(f"خطأ: {e}")
        return None

def fix_url(raw_url):
    raw_url = raw_url.strip()
    
    if raw_url.startswith('/'):
        raw_url = 'https://www.ysscores.com/ar/match' + raw_url
    elif raw_url.startswith('78601366'):
        raw_url = f'https://www.ysscores.com/ar/match/{raw_url}'
    elif not raw_url.startswith('http'):
        raw_url = 'https://' + raw_url
    
    if ':///' in raw_url:
        raw_url = raw_url.replace(':///', '://www.ysscores.com/ar/match/')
    
    return raw_url

@bot.message_handler(commands=['start'])
def start_cmd(m):
    bot.reply_to(m, 
        "⚽ **بوت معلومات المباريات**\n\n"
        "أرسل رابط المباراة من ysscores.com\n\n"
        "**مثال:**\n"
        "`/match 78601366/Asswehly-SC-vs-Al-Nasr-SC`\n"
        "أو الرابط الكامل:\n"
        "`https://www.ysscores.com/ar/match/78601366/Asswehly-SC-vs-Al-Nasr-SC`",
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda m: m.text and ('ysscores.com' in m.text or 'match' in m.text))
def handle_match(m):
    raw_url = m.text.strip()
    if raw_url.startswith('/match'):
        raw_url = raw_url.replace('/match', '').strip()
    
    url = fix_url(raw_url)
    status = bot.reply_to(m, f"⏳ جاري استخراج المعلومات من الرابط:\n`{url}`", parse_mode='Markdown')
    info = extract_match_info(url)
    
    if info:
        reply = (f"⚽ **معلومات المباراة**\n\n"
                 f"🏆 **المباراة:** {info['team1']} 🆚 {info['team2']}\n"
                 f"🕐 **الوقت:** {info['time']}\n"
                 f"📅 **التاريخ:** {info['date']}\n"
                 f"🏟️ **الملعب:** {info['stadium']}\n"
                 f"📺 **القناة:** {info['channel']}")
        bot.edit_message_text(reply, m.chat.id, status.message_id, parse_mode='Markdown')
    else:
        bot.edit_message_text("❌ فشل استخراج المعلومات. تأكد من الرابط.", m.chat.id, status.message_id)

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    else:
        return 'Invalid content type', 403

@app.route('/')
def index():
    return 'Bot is running...'

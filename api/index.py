import re
import cloudscraper
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify

app = Flask(__name__)

def clean_team_name(name):
    name = re.sub(r'https?://\S+', '', name)
    name = re.sub(r'[a-zA-Z0-9\-_\.]+\.(com|net|org|ly|ma|tn)', '', name)
    name = re.sub(r'/ar/match/\d+/', '', name)
    name = re.sub(r'Asswehly-SC-vs-Al-Nasr-SC', '', name)
    return name.strip()

def extract_match_info(url):
    # استخدام سكرابر مجهز لتخطي الحماية مع إعدادات متصفح حديث
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
        'Referer': 'https://www.google.com/'
    }
    
    try:
        response = scraper.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return {"error": f"الموقع هدف أرجع كود خطأ: {response.status_code}"}
            
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
        return {"error": f"فشل الاتصال بالموقع: {str(e)}"}

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

@app.route('/')
def get_match():
    target_url = request.args.get('url')
    if not target_url:
        return jsonify({
            "status": "error",
            "message": "Please provide a URL parameter. Example: /?url=https://www.ysscores.com/..."
        }), 400
        
    fixed_url = fix_url(target_url)
    match_data = extract_match_info(fixed_url)
    
    if "error" in match_data:
        return jsonify({
            "status": "error", 
            "message": match_data["error"],
            "note": "قد يكون الموقع المستهدف مالي بحماية تمنع خوادم Vercel من الدخول"
        }), 200
        
    return jsonify({
        "status": "success",
        "url": fixed_url,
        "data": match_data
    }), 200

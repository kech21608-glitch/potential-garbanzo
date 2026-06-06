from flask import Flask, request, jsonify
import requests
import re
from bs4 import BeautifulSoup

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "ok", "message": "API يعمل"})

@app.route('/match_info')
def match_info():
    url = request.args.get('url')
    
    if not url:
        return jsonify({"error": "أدخل url"}), 400
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=15)
        text = r.text
        
        vs = re.search(r'/([^/]+)-vs-([^/]+)', url)
        team1 = vs.group(1).replace('-', ' ') if vs else "فريق1"
        team2 = vs.group(2).replace('-', ' ') if vs else "فريق2"
        
        time_match = re.search(r'وقت المباراة\s+([0-9:]+)\s*([صم])', text)
        time = f"{time_match.group(1)} {time_match.group(2)}اءً" if time_match else "غير محدد"
        
        date_match = re.search(r'تاريخ المباراة\s+([^\n]+)', text)
        date = date_match.group(1).strip() if date_match else "غير محدد"
        
        stadium_match = re.search(r'ملعب\s+المباراة\s+([^\n]+)', text)
        stadium = stadium_match.group(1).strip() if stadium_match else "غير محدد"
        
        channel_match = re.search(r'القناة\s+([^\n]+)', text)
        channel = channel_match.group(1).strip() if channel_match else "غير محدد"
        
        return jsonify({
            "success": True,
            "team1": team1,
            "team2": team2,
            "time": time,
            "date": date,
            "stadium": stadium,
            "channel": channel
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# هذا السطر مهم لـ Vercel
app.debug = False

from flask import Flask, request, jsonify, make_response
import requests
import re
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ========== إعدادات الرؤوس (Headers) ==========
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ar-EG,ar;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}

# ========== دوال التنظيف ==========
def clean_team_name(name):
    """تنظيف اسم الفريق من الروابط والرموز"""
    name = re.sub(r'https?://\S+', '', name)
    name = re.sub(r'[a-zA-Z0-9\-_\.]+\.(com|net|org|ly|ma|tn)', '', name)
    name = re.sub(r'/ar/match/\d+/', '', name)
    return name.strip()

def fix_url(raw_url):
    """إصلاح الرابط الناقص إلى رابط كامل"""
    raw_url = raw_url.strip()
    if not raw_url.startswith('http'):
        raw_url = 'https://' + raw_url
    if 'ysscores.com' not in raw_url:
        if re.match(r'^\d+', raw_url):
            raw_url = f'https://www.ysscores.com/ar/match/{raw_url}'
    return raw_url

# ========== الدالة الرئيسية لاستخراج معلومات المباراة ==========
def extract_match_info(url):
    """استخراج دقيق لمعلومات المباراة"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        info = {"team1": "", "team2": "", "time": "", "date": "", "stadium": "", "channel": ""}
        
        # 1. استخراج أسماء الفرق من الرابط
        vs_match = re.search(r'/([^/]+)-vs-([^/]+)', url, re.I)
        if vs_match:
            info["team1"] = vs_match.group(1).replace('-', ' ').strip()
            info["team2"] = vs_match.group(2).replace('-', ' ').strip()
        
        # 2. استخراج الوقت والتاريخ من نص الصفحة
        page_text = soup.get_text()
        
        time_match = re.search(r'وقت المباراة\s+([0-9:]+)\s*(ص|م)', page_text)
        if time_match:
            info["time"] = f"{time_match.group(1)} {time_match.group(2)}اءً"
        else:
            info["time"] = "وقت غير محدد"
        
        date_match = re.search(r'تاريخ المباراة\s+([^\n]+)', page_text)
        if date_match:
            info["date"] = date_match.group(1).strip()
        else:
            info["date"] = "تاريخ غير محدد"
        
        # 3. استخراج الملعب
        stadium_match = re.search(r'ملعب\s+المباراة\s+([^\n]+)', page_text)
        if stadium_match:
            info["stadium"] = stadium_match.group(1).strip()
        else:
            info["stadium"] = "ملعب غير محدد"
        
        # 4. استخراج القناة الناقلة
        channel_match = re.search(r'القناة\s+([^\n]+)', page_text)
        if channel_match:
            info["channel"] = channel_match.group(1).strip()
        else:
            info["channel"] = "قناة غير محددة"
        
        # تنظيف الأسماء
        info["team1"] = clean_team_name(info["team1"])
        info["team2"] = clean_team_name(info["team2"])
        
        return info
    except Exception as e:
        raise Exception(f"خطأ في الاستخراج: {str(e)}")

# ========== واجهة API ==========
@app.route("/match_info", methods=["GET", "POST"])
def get_match_info():
    # الحصول على الرابط من GET أو POST
    match_url = request.args.get("url") or request.form.get("url")
    
    if not match_url:
        response_data = {
            "success": False,
            "error": "الرجاء إدخال رابط المباراة",
            "example": "/match_info?url=https://www.ysscores.com/ar/match/78601366/Asswehly-SC-vs-Al-Nasr-SC"
        }
        response = make_response(jsonify(response_data))
        response.headers["Content-Type"] = "application/json"
        return response, 400
    
    try:
        url = fix_url(match_url)
        info = extract_match_info(url)
        
        response_data = {
            "success": True,
            "data": info,
            "source_url": url
        }
        
        response = make_response(jsonify(response_data))
        response.headers["Content-Type"] = "application/json"
        return response
        
    except Exception as e:
        response_data = {
            "success": False,
            "error": str(e)
        }
        response = make_response(jsonify(response_data))
        response.headers["Content-Type"] = "application/json"
        return response, 500

# ========== الصفحة الرئيسية ==========
@app.route("/", methods=["GET"])
def home():
    response_data = {
        "status": "ok",
        "message": "API لمعلومات المباريات يعمل",
        "endpoints": {
            "match_info": "/match_info?url=رابط_المباراة"
        },
        "example": "/match_info?url=https://www.ysscores.com/ar/match/78601366/Asswehly-SC-vs-Al-Nasr-SC",
        "credit": "Match Info API"
    }
    response = make_response(jsonify(response_data))
    response.headers["Content-Type"] = "application/json"
    return response

# ========== تشغيل التطبيق ==========
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)

# هذا ضروري لـ Vercel
app = app
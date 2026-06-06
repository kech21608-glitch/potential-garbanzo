from flask import Flask, request, jsonify, make_response
import requests
import re
import json
import time
import urllib3
from bs4 import BeautifulSoup
from datetime import datetime
import traceback

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ========== الإعدادات الثابتة ==========
VERSION = "2.0.0"
API_NAME = "Match Info API"
DEVELOPER = "Kodi Stream"
CACHE_TIMEOUT = 300  # 5 دقائق

# ========== الرؤوس (Headers) ==========
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# ========== قاموس التخزين المؤقت ==========
cache = {}

# ========== دوال مساعدة ==========
def clean_team_name(name):
    """تنظيف اسم الفريق من الروابط والرموز الزائدة"""
    if not name:
        return ""
    
    # إزالة الروابط
    name = re.sub(r'https?://\S+', '', name)
    name = re.sub(r'www\.\S+\.\S+', '', name)
    
    # إزادة امتدادات المواقع
    name = re.sub(r'[a-zA-Z0-9\-_\.]+\.(com|net|org|ly|ma|tn|dz|sa|eg|ae|qa|kw|om|bh|jo|ps|iq|sy|lb|ye|tr|ir)', '', name)
    
    # إزالة مسارات الموقع
    name = re.sub(r'/ar/match/\d+/', '', name)
    name = re.sub(r'/match/\d+/', '', name)
    
    # إزالة الأرقام والرموز غير المرغوب فيها
    name = re.sub(r'[0-9]+', '', name)
    name = re.sub(r'[-_]', ' ', name)
    
    # تنظيف المسافات
    name = re.sub(r'\s+', ' ', name)
    
    return name.strip()

def fix_url(raw_url):
    """إصلاح الرابط الناقص إلى رابط كامل"""
    if not raw_url:
        return None
    
    raw_url = raw_url.strip()
    
    # إزالة أي نص قبل الرابط
    if 'http' not in raw_url:
        # البحث عن رابط في النص
        url_match = re.search(r'(https?://[^\s]+|ysscores\.com[^\s]+|\d+/[^\s]+)', raw_url)
        if url_match:
            raw_url = url_match.group(1)
    
    # إضافة https إذا لم يوجد
    if not raw_url.startswith('http'):
        raw_url = 'https://' + raw_url
    
    # إضافة النطاق الأساسي إذا كان الرابط ناقصاً
    if 'ysscores.com' not in raw_url:
        # إذا كان الرابط يبدأ برقم (معرف المباراة)
        id_match = re.match(r'^(\d+)(?:/|$)', raw_url)
        if id_match:
            match_id = id_match.group(1)
            # محاولة استخراج أسماء الفرق من الرابط إذا وجدت
            teams_match = re.search(r'([A-Za-z-]+)-vs-([A-Za-z-]+)', raw_url, re.I)
            if teams_match:
                team1 = teams_match.group(1)
                team2 = teams_match.group(2)
                raw_url = f'https://www.ysscores.com/ar/match/{match_id}/{team1}-vs-{team2}'
            else:
                raw_url = f'https://www.ysscores.com/ar/match/{match_id}'
    
    # إزالة أي معاملات زائدة
    raw_url = raw_url.split('?')[0]
    
    return raw_url

def get_from_cache(url):
    """الحصول على بيانات من التخزين المؤقت"""
    if url in cache:
        data, timestamp = cache[url]
        if time.time() - timestamp < CACHE_TIMEOUT:
            return data
        else:
            del cache[url]
    return None

def save_to_cache(url, data):
    """حفظ البيانات في التخزين المؤقت"""
    cache[url] = (data, time.time())

def extract_match_info(url):
    """استخراج دقيق لمعلومات المباراة"""
    headers = DEFAULT_HEADERS.copy()
    
    try:
        # إضافة رأس إضافي لتجنب الحظر
        headers["Referer"] = "https://www.google.com/"
        
        response = requests.get(url, headers=headers, timeout=20, verify=False)
        
        # التحقق من حالة الاستجابة
        if response.status_code == 404:
            raise Exception("المباراة غير موجودة (404)")
        elif response.status_code == 403:
            raise Exception("تم حظر الوصول (403) - حاول لاحقاً")
        elif response.status_code != 200:
            raise Exception(f"خطأ في الخادم: {response.status_code}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        info = {
            "team1": "",
            "team2": "",
            "time": "",
            "date": "",
            "stadium": "",
            "channel": "",
            "referee": "",
            "round": "",
            "league": ""
        }
        
        # 1. استخراج أسماء الفرق من الرابط
        vs_match = re.search(r'/([^/]+)-vs-([^/]+)', url, re.I)
        if vs_match:
            info["team1"] = vs_match.group(1).replace('-', ' ').strip()
            info["team2"] = vs_match.group(2).replace('-', ' ').strip()
        
        # 2. استخراج أسماء الفرق من عنوان الصفحة
        if soup.title and (not info["team1"] or not info["team2"]):
            title = soup.title.string
            title_match = re.search(r'لمباراة\s+([^و]+)\s+و\s+([^-]+)', title)
            if title_match:
                info["team1"] = title_match.group(1).strip()
                info["team2"] = title_match.group(2).strip()
        
        # 3. استخراج النص الكامل للصفحة
        page_text = soup.get_text()
        
        # 4. استخراج الوقت
        time_patterns = [
            r'وقت المباراة\s+([0-9]{1,2}:[0-9]{2})\s*([صم])',
            r'الساعة\s+([0-9]{1,2}:[0-9]{2})\s*([صم])',
            r'([0-9]{1,2}:[0-9]{2})\s*([صم])اءً',
        ]
        for pattern in time_patterns:
            time_match = re.search(pattern, page_text)
            if time_match:
                if len(time_match.groups()) == 2:
                    info["time"] = f"{time_match.group(1)} {time_match.group(2)}اءً"
                else:
                    info["time"] = time_match.group(1)
                break
        
        # 5. استخراج التاريخ
        date_patterns = [
            r'تاريخ المباراة\s+([^\n]+)',
            r'التاريخ\s+([^\n]+)',
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{2}-\d{2}-\d{4})',
        ]
        for pattern in date_patterns:
            date_match = re.search(pattern, page_text)
            if date_match:
                info["date"] = date_match.group(1).strip()
                break
        
        # 6. استخراج الملعب
        stadium_patterns = [
            r'ملعب\s+المباراة\s+([^\n]+)',
            r'الملعب\s+([^\n]+)',
            r'استاد\s+([^\n]+)',
        ]
        for pattern in stadium_patterns:
            stadium_match = re.search(pattern, page_text)
            if stadium_match:
                info["stadium"] = stadium_match.group(1).strip()
                break
        
        # 7. استخراج القناة
        channel_patterns = [
            r'القناة\s+([^\n]+)',
            r'الناقل\s+([^\n]+)',
            r'قناة\s+([^\n]+)',
        ]
        for pattern in channel_patterns:
            channel_match = re.search(pattern, page_text)
            if channel_match:
                info["channel"] = channel_match.group(1).strip()
                break
        
        # 8. استخراج الحكم
        referee_match = re.search(r'حكم\s+الساحة\s+([^\n]+)', page_text)
        if referee_match:
            info["referee"] = referee_match.group(1).strip()
        
        # 9. استخراج الجولة والبطولة
        round_match = re.search(r'الجولة\s+([^\n]+)', page_text)
        if round_match:
            info["round"] = round_match.group(1).strip()
        
        league_match = re.search(r'البطولة\s+([^\n]+)', page_text)
        if league_match:
            info["league"] = league_match.group(1).strip()
        
        # تنظيف الأسماء
        info["team1"] = clean_team_name(info["team1"])
        info["team2"] = clean_team_name(info["team2"])
        
        # تعيين قيم افتراضية
        if not info["team1"]: info["team1"] = "الفريق الأول"
        if not info["team2"]: info["team2"] = "الفريق الثاني"
        if not info["time"]: info["time"] = "وقت غير محدد"
        if not info["date"]: info["date"] = "تاريخ غير محدد"
        if not info["stadium"]: info["stadium"] = "ملعب غير محدد"
        if not info["channel"]: info["channel"] = "قناة غير محددة"
        
        return info
        
    except requests.exceptions.Timeout:
        raise Exception("انتهى وقت الاتصال - الخادم لا يستجيب")
    except requests.exceptions.ConnectionError:
        raise Exception("فشل الاتصال - تحقق من الإنترنت")
    except Exception as e:
        raise Exception(f"خطأ في الاستخراج: {str(e)}")

# ========== واجهات API ==========
@app.route("/", methods=["GET"])
def home():
    """الصفحة الرئيسية"""
    response_data = {
        "success": True,
        "api": API_NAME,
        "version": VERSION,
        "developer": DEVELOPER,
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "match_info": {
                "url": "/match_info",
                "method": "GET",
                "params": {"url": "رابط المباراة من ysscores.com"},
                "example": "/match_info?url=https://www.ysscores.com/ar/match/78601366/Asswehly-SC-vs-Al-Nasr-SC"
            },
            "health": {
                "url": "/health",
                "method": "GET",
                "description": "فحص صحة الخدمة"
            },
            "cache_stats": {
                "url": "/cache_stats",
                "method": "GET",
                "description": "إحصائيات التخزين المؤقت"
            }
        }
    }
    return make_response(jsonify(response_data), 200)

@app.route("/health", methods=["GET"])
def health_check():
    """فحص صحة الخدمة"""
    response_data = {
        "status": "healthy",
        "api": API_NAME,
        "version": VERSION,
        "timestamp": datetime.now().isoformat(),
        "cache_size": len(cache),
        "cache_timeout": CACHE_TIMEOUT
    }
    return make_response(jsonify(response_data), 200)

@app.route("/cache_stats", methods=["GET"])
def cache_stats():
    """إحصائيات التخزين المؤقت"""
    response_data = {
        "success": True,
        "cache_size": len(cache),
        "cached_urls": list(cache.keys()),
        "cache_timeout_seconds": CACHE_TIMEOUT
    }
    return make_response(jsonify(response_data), 200)

@app.route("/match_info", methods=["GET", "POST"])
def get_match_info():
    """استخراج معلومات المباراة"""
    # الحصول على الرابط
    match_url = None
    
    if request.method == "GET":
        match_url = request.args.get("url")
    elif request.method == "POST":
        data = request.get_json()
        if data:
            match_url = data.get("url")
        if not match_url:
            match_url = request.form.get("url")
    
    # التحقق من وجود الرابط
    if not match_url:
        response_data = {
            "success": False,
            "error": "الرجاء إدخال رابط المباراة",
            "usage": {
                "method": "GET",
                "url": "/match_info?url=رابط_المباراة",
                "example": "/match_info?url=https://www.ysscores.com/ar/match/78601366/Asswehly-SC-vs-Al-Nasr-SC"
            }
        }
        return make_response(jsonify(response_data), 400)
    
    # إصلاح الرابط
    try:
        fixed_url = fix_url(match_url)
        if not fixed_url:
            response_data = {
                "success": False,
                "error": "الرابط غير صالح",
                "provided_url": match_url
            }
            return make_response(jsonify(response_data), 400)
    except Exception as e:
        response_data = {
            "success": False,
            "error": f"فشل إصلاح الرابط: {str(e)}",
            "provided_url": match_url
        }
        return make_response(jsonify(response_data), 400)
    
    # التحقق من التخزين المؤقت
    cached_data = get_from_cache(fixed_url)
    if cached_data:
        response_data = {
            "success": True,
            "data": cached_data,
            "cached": True,
            "source_url": fixed_url,
            "timestamp": datetime.now().isoformat()
        }
        return make_response(jsonify(response_data), 200)
    
    # استخراج المعلومات
    try:
        info = extract_match_info(fixed_url)
        save_to_cache(fixed_url, info)
        
        response_data = {
            "success": True,
            "data": info,
            "cached": False,
            "source_url": fixed_url,
            "timestamp": datetime.now().isoformat()
        }
        return make_response(jsonify(response_data), 200)
        
    except Exception as e:
        response_data = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
            "source_url": fixed_url,
            "timestamp": datetime.now().isoformat()
        }
        return make_response(jsonify(response_data), 500)

@app.route("/match_info/clear_cache", methods=["POST"])
def clear_cache():
    """مسح التخزين المؤقت"""
    cache.clear()
    response_data = {
        "success": True,
        "message": "تم مسح التخزين المؤقت",
        "timestamp": datetime.now().isoformat()
    }
    return make_response(jsonify(response_data), 200)

@app.errorhandler(404)
def not_found(error):
    response_data = {
        "success": False,
        "error": "الواجهة غير موجودة",
        "available_endpoints": ["/", "/health", "/match_info", "/cache_stats"]
    }
    return make_response(jsonify(response_data), 404)

@app.errorhandler(500)
def internal_error(error):
    response_data = {
        "success": False,
        "error": "خطأ داخلي في الخادم",
        "timestamp": datetime.now().isoformat()
    }
    return make_response(jsonify(response_data), 500)

# ========== تشغيل التطبيق ==========
if __name__ == "__main__":
    print(f"🚀 {API_NAME} v{VERSION}")
    print(f"👨‍💻 {DEVELOPER}")
    print("=" * 50)
    print("✅ API يعمل على http://127.0.0.1:5000")
    print("📝 endpoints:")
    print("   - GET  /")
    print("   - GET  /health")
    print("   - GET  /match_info?url=...")
    print("   - GET  /cache_stats")
    print("   - POST /match_info/clear_cache")
    print("=" * 50)
    app.run(host="127.0.0.1", port=5000, debug=False)

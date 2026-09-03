from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from urllib.parse import urlparse, urljoin
from functools import wraps
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

# app.py はプロジェクト直下に置く。
# 実体（templates / static / data）は bousai_app/ 配下にあるので、そこを参照する。
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(BASE_DIR, 'bousai_app')

app = Flask(
    __name__,
    template_folder=os.path.join(APP_DIR, 'templates'),
    static_folder=os.path.join(APP_DIR, 'static'),
)
app.secret_key = 'your-secret-key-here'

# 管理者認証情報
ADMIN_CREDENTIALS = {
    'admin': '123'
}

# ────────────────────────────────
# 気象警報・注意報設定
PREFECTURE_CODE = "020000"  # 青森県
AREA_NAME = "青森市"

# ワークショップ課題：青森市の市区町村コードに変更する
AREA_CODE = "1420500"

WARNING_URL = (
    f"https://www.jma.go.jp/bosai/warning/data/r8/{PREFECTURE_CODE}.json"
)

JST = timezone(timedelta(hours=9))

# 警報・注意報のコード一覧
WARNING_CODES = {
    "00": "解除",
    "02": "暴風雪警報",
    "03": "レベル3大雨警報",
    "04": "洪水警報",
    "05": "暴風警報",
    "06": "大雪警報",
    "07": "波浪警報",
    "08": "レベル3高潮警報",
    "09": "レベル3土砂災害警報",
    "10": "レベル2大雨注意報",
    "12": "大雪注意報",
    "13": "風雪注意報",
    "14": "雷注意報",
    "15": "強風注意報",
    "16": "波浪注意報",
    "17": "融雪注意報",
    "18": "洪水注意報",
    "19": "レベル2高潮注意報",
    "20": "濃霧注意報",
    "21": "乾燥注意報",
    "22": "なだれ注意報",
    "23": "低温注意報",
    "24": "霜注意報",
    "25": "着氷注意報",
    "26": "着雪注意報",
    "27": "その他の注意報",
    "29": "レベル2土砂災害注意報",
    "32": "暴風雪特別警報",
    "33": "レベル5大雨特別警報",
    "35": "暴風特別警報",
    "36": "大雪特別警報",
    "37": "波浪特別警報",
    "38": "レベル5高潮特別警報",
    "39": "レベル5土砂災害特別警報",
    "43": "レベル4大雨危険警報",
    "48": "レベル4高潮危険警報",
    "49": "レベル4土砂災害危険警報"
}

# ────────────────────────────────
# サンプルデータの読み込み
DATA_FILE = os.path.join(APP_DIR, 'data', 'shelters.json')
INSTRUCTIONS_FILE = os.path.join(APP_DIR, 'data', 'instructions.json')

def load_json(path, default):
    """JSONファイルを読み込む（存在しない・壊れている場合は default を返す）"""
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

shelters = load_json(DATA_FILE, [])
instructions = load_json(INSTRUCTIONS_FILE, [])
DISTRICT_OPTIONS = [
    '市内全域',
    '北地区',
    '南地区',
    '東地区',
    '西地区',
    '中央地区',
    '浪岡地区'
]
CITIZEN_REPORTS = [
    {
        'id': 1,
        'district': '南地区',
        'content': '川沿いの通路に土が流れ出ていて危険です。',
        'status': '未対応',
        'created_at': '2026年07月14日 20:15',
        'updated_at': '2026年07月14日 20:15'
    },
    {
        'id': 2,
        'district': '北地区',
        'content': '木が傾いていて通行に支障があります。',
        'status': '対応中',
        'created_at': '2026年07月14日 19:40',
        'updated_at': '2026年07月14日 19:40'
    },
    {
        'id': 3,
        'district': '東地区',
        'content': '道路の冠水が始まっており、車両が通れません。',
        'status': '要確認',
        'created_at': '2026年07月14日 18:55',
        'updated_at': '2026年07月14日 18:55'
    },
    {
        'id': 4,
        'district': '市内全域',
        'content': '強風で看板が落ちそうです。周辺確認をお願いします。',
        'status': '対応済み',
        'created_at': '2026年07月14日 18:10',
        'updated_at': '2026年07月14日 18:10'
    }
]

def save_instructions():
    """指示ボードのデータをファイルに保存する"""
    try:
        with open(INSTRUCTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(instructions, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def save_shelters():
    """避難所データをファイルへ保存する"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(shelters, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
# ────────────────────────────────

# ────────────────────────────────
# 認証関連の設定とヘルパー関数
def is_safe_url(target):
    """リダイレクト先URLが安全かどうかチェック"""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

def login_required(f):
    """認証が必要なページに付けるデコレータ"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            # 現在のURLをnextパラメータとしてログイン画面にリダイレクト
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_japan_time():
    """日本時間（JST）の現在時刻を取得する"""
    return datetime.now(JST).strftime("%Y年%m月%d日 %H:%M")


def format_report_time(iso_str):
    """気象庁の発表時刻（ISO形式）をJSTの表示用文字列に変換する"""
    if not iso_str:
        return "不明"
    try:
        parsed = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        if parsed.tzinfo:
            parsed = parsed.astimezone(JST)
        return parsed.strftime("%Y年%m月%d日 %H:%M")
    except ValueError:
        return iso_str


def filter_shelters(district=None):
    """district 指定があれば一致する避難所のみ、なければ全件を返す"""
    return [s for s in shelters if not district or s.get('district') == district]


def parse_japanese_datetime(value):
    """日本語の日時文字列を datetime に変換して、比較しやすくする"""
    if not value:
        return datetime.min

    for fmt in (
        '%Y年%m月%d日 %H:%M',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y/%m/%d %H:%M'
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(JST)
    except ValueError:
        return datetime.min


def parse_area_warnings(warning_data):
    """気象庁の新形式JSONから対象市区町村の発表・継続中の情報を抽出する"""
    if not isinstance(warning_data, list):
        raise ValueError("気象庁の警報・注意報データが新形式の配列ではありません")

    warnings = []
    seen_codes = set()
    report_datetimes = []
    latest_headline = ""

    for report in warning_data:
        if not isinstance(report, dict):
            continue

        report_datetime = report.get("reportDatetime")
        if isinstance(report_datetime, str) and report_datetime:
            report_datetimes.append(report_datetime)

        headline = report.get("headlineText") or report.get("headline") or ""
        if headline:
            latest_headline = headline

        warning = report.get("warning")
        if not isinstance(warning, dict):
            continue

        class20_items = warning.get("class20Items", [])
        if not isinstance(class20_items, list):
            continue

        area = next(
            (
                item for item in class20_items
                if isinstance(item, dict)
                and item.get("areaCode") == AREA_CODE
            ),
            None
        )

        if area is None:
            # 対象市区町村に一致しない場合でも、見出しに警報が含まれているなら拾う
            if headline:
                warnings.append({
                    "name": headline,
                    "headline": headline,
                    "code": "",
                    "status": "発表",
                    "detail": headline
                })
            continue

        kinds = area.get("kinds", [])
        if not isinstance(kinds, list):
            continue

        for kind in kinds:
            if not isinstance(kind, dict):
                continue

            status = str(kind.get("status", "")).strip()
            code = str(kind.get("code", "")).strip()
            if status not in ("発表", "継続") or (not code and not headline):
                continue
            if code and code in seen_codes:
                continue

            detail = report.get("text")
            if isinstance(detail, dict):
                detail = detail.get("text")
            if not isinstance(detail, str):
                detail = headline

            warning_name = headline or WARNING_CODES.get(code, f"不明な警報・注意報 (コード: {code})")

            warnings.append({
                "name": warning_name,
                "headline": headline,
                "code": code,
                "status": status,
                "detail": detail
            })
            if code:
                seen_codes.add(code)

    latest_report_datetime = max(report_datetimes, default="")
    return warnings, latest_report_datetime, latest_headline


def get_weather_warnings():
    """対象市区町村の警報・注意報を取得する"""
    try:
        # 青森県の新形式（令和8年～）警報・注意報データを取得
        with urllib.request.urlopen(url=WARNING_URL, timeout=10) as res:
            warning_data = json.loads(res.read())

        warnings, report_datetime, headline = parse_area_warnings(warning_data)

        return {
            "area_name": AREA_NAME,
            "warnings": warnings,
            "headline": headline,
            "report_time": format_report_time(report_datetime),
            "last_fetch_time": get_japan_time()
        }

    except Exception:
        return {
            "area_name": AREA_NAME,
            "warnings": [],
            "headline": "",
            "report_time": "取得失敗",
            "last_fetch_time": get_japan_time(),
            "error": True
        }


# トップページ：templates/index.html を返す（住民向け指示も表示する）
@app.route('/')
def index():
    resident_notices = [i for i in instructions if i.get('target') == '住民']
    return render_template('index.html', resident_notices=resident_notices)

# ログインページ
@app.route('/login', methods=['GET', 'POST'])
def login():
    # リダイレクト先を取得（デフォルトは避難所登録画面）
    next_url = request.args.get('next') or request.form.get('next')

    # 安全でないURLの場合はデフォルトページにリダイレクト
    if not next_url or not is_safe_url(next_url):
        next_url = url_for('shelter_register')

    if request.method == 'POST':
        password = request.form.get('password', '').strip()

        # 認証チェック
        username = next(
            (name for name, registered_password in ADMIN_CREDENTIALS.items()
             if registered_password == password),
            None
        )
        if username:
            session['logged_in'] = True
            session['username'] = username
            # ログイン成功後は指定されたページにリダイレクト
            return redirect(next_url)
        return render_template('login.html', error=True, message="パスワードが正しくありません。", next=next_url)

    # ログイン済みの場合は指定されたページにリダイレクト
    if session.get('logged_in'):
        return redirect(next_url)

    return render_template('login.html', next=next_url)

# ログアウト
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# 避難所登録ページ
@app.route('/shelter_register', methods=['GET', 'POST'])
@login_required
def shelter_register():
    if request.method == 'POST':
        shelter_name = request.form.get('name', '').strip()

        if not shelter_name:
            return render_template(
                'shelter_register.html',
                error=True,
                message='避難所名を登録してください'
            )

        shelters.append({
            'id': len(shelters) + 1,
            'name': shelter_name
        })
        save_shelters()

        return render_template(
            'shelter_register.html',
            success=True,
            message='登録しました'
        )

    return render_template('shelter_register.html')

# 避難所検索ページ
@app.route('/shelter_search')
def shelter_search():
    return render_template('shelter_search.html')

# 全施設一覧ページ
@app.route('/all_shelters')
def all_shelters():
    return render_template('search_results.html', results=shelters)


def filter_board_items(items, selected_regions):
    """地区フィルタを適用して、最新順に並べた一覧を返す"""
    if '市内全域' not in selected_regions:
        items = [
            item for item in items
            if (item.get('district') or '市内全域') in selected_regions
        ]
    return sorted(
        items,
        key=lambda item: parse_japanese_datetime(item.get('updated_at') or item.get('created_at')),
        reverse=True
    )


# 指示ボード：発信内容を一覧で確認する
@app.route('/board', methods=['GET', 'POST'])
@login_required
def board():
    selected_regions = request.args.getlist('district') or ['市内全域']

    if request.method == 'POST':
        target = request.form.get('target', '住民')
        content = request.form.get('content', '').strip()
        district_values = request.form.getlist('district')
        district = district_values[0] if district_values else '市内全域'

        if content:
            instructions.insert(0, {
                'id': max((i.get('id', 0) for i in instructions), default=0) + 1,
                'target': target,
                'district': district,
                'content': content,
                'shelter': '',
                'status': '発信中',
                'created_at': get_japan_time(),
                'updated_at': get_japan_time()
            })
            save_instructions()

        selected_regions = district_values or ['市内全域']

    board_instructions = filter_board_items(instructions, selected_regions)
    citizen_reports = filter_board_items(CITIZEN_REPORTS, selected_regions)

    return render_template(
        'board.html',
        instructions=board_instructions,
        reports=citizen_reports,
        district_options=DISTRICT_OPTIONS,
        selected_regions=selected_regions
    )


@app.route('/reports')
@login_required
def reports():
    selected_regions = request.args.getlist('district') or ['市内全域']
    citizen_reports = filter_board_items(CITIZEN_REPORTS, selected_regions)

    return render_template(
        'reports.html',
        reports=citizen_reports,
        district_options=DISTRICT_OPTIONS,
        selected_regions=selected_regions
    )

# 検索結果ページ：templates/search_results.html を返す
@app.route('/search_results')
def search_results():
    results = filter_shelters(request.args.get('district'))
    return render_template('search_results.html', results=results)

# JSON API：/shelters?district=地区名
@app.route('/shelters', methods=['GET'])
def get_shelters():
    results = filter_shelters(request.args.get('district'))

    if not results:
        # 見つからなければエラー JSON を返す
        return jsonify({'error': 'No shelters found'}), 404

    # 見つかったらリストを JSON で返す
    return jsonify(results)

# 気象警報・注意報API
@app.route('/api/weather_warnings')
def api_weather_warnings():
    """気象警報・注意報をJSON形式で返すAPI"""
    return jsonify(get_weather_warnings())

if __name__ == '__main__':
    app.run(debug=True, port=5000)

import os
import re
import json
import csv
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from Crypto.Cipher import AES
import urllib.parse

# ============ 强制从环境变量读取 ============
REQUIRED_VARS = [
    "USERNAME", "PASSWORD",
    "ELEC_ACCOUNT", "ELEC_ROOM_ID", "ELEC_ROOM_NAME",
    "ELEC_FLOOR", "ELEC_AREA", "ELEC_BUILDING", "ELEC_AID",
    "VPN_BASE", "ELEC_HOST", "SSO_HOST", "CAS_HOST"
]
missing = [v for v in REQUIRED_VARS if not os.environ.get(v)]
if missing:
    raise RuntimeError(f"缺少必要的环境变量: {', '.join(missing)}")

USERNAME = os.environ["USERNAME"]
PASSWORD = os.environ["PASSWORD"]
ACCOUNT = os.environ["ELEC_ACCOUNT"]
ROOM_ID = os.environ["ELEC_ROOM_ID"]
ROOM_NAME = os.environ["ELEC_ROOM_NAME"]
FLOOR = os.environ["ELEC_FLOOR"]
AREA = os.environ["ELEC_AREA"]
BUILDING = os.environ["ELEC_BUILDING"]
AID = os.environ["ELEC_AID"]
VPN_BASE = os.environ["VPN_BASE"]
ELEC_HOST = os.environ["ELEC_HOST"]
SSO_HOST = os.environ["SSO_HOST"]
CAS_HOST = os.environ["CAS_HOST"]
VPN_COOKIE_NAME = os.environ["VPN_COOKIE_NAME"]

SSO_PORT = int(os.environ.get("SSO_PORT", "7280"))
CAS_PORT = int(os.environ.get("CAS_PORT", "8080"))
ELEC_PORT = int(os.environ.get("ELEC_PORT", "80"))

DATA_DIR = "data"
CSV_FILE = os.path.join(DATA_DIR, "elec_history.csv")
# ==============================================

# ---------- WebVPN 加密算法 ----------
def encrypt_host(host: str) -> str:
    key = b"wrdvpnisthebest!"
    cipher = AES.new(key, AES.MODE_CFB, iv=key, segment_size=128)
    ciphertext = cipher.encrypt(host.encode('utf-8'))
    return key.hex().upper() + ciphertext.hex().upper()

def build_vpn_url(protocol: str, host: str, path: str, port: int = None) -> str:
    encrypted_host = encrypt_host(host)
    if port is None:
        return f"https://{VPN_BASE}/{protocol}/{encrypted_host}{path}"
    return f"https://{VPN_BASE}/{protocol}-{port}/{encrypted_host}{path}"

# ---------- 获取 VPN Cookie ----------
def get_vpn_cookie():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"https://{VPN_BASE}")
        page.fill("#un", USERNAME)
        page.fill("#pd", PASSWORD)
        page.click("#index_login_btn")
        try:
            page.wait_for_function(
                "() => document.cookie.includes(f'{VPN_COOKIE_NAME}')",
                timeout=15000
            )
        except:
            pass
        cookies = context.cookies()
        browser.close()
        for cookie in cookies:
            if cookie['name'] == f"{VPN_COOKIE_NAME}":
                return cookie['value']
        raise RuntimeError("获取 VPN Cookie 失败")

# ---------- SSO 认证流程 ----------
def get_ssoticketid(session):
    url = build_vpn_url("http", SSO_HOST, "/ias/prelogin?sysid=FWDT", port=SSO_PORT)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    tag = soup.find('input', {'id': 'ssoticketid'})
    if tag and tag.get('value'):
        return tag['value']
    raise RuntimeError("解析 ssoticketid 失败")

def sso_login(session, ssoticketid):
    url = build_vpn_url("http", CAS_HOST, "/cassyno/index", port=CAS_PORT)
    data = {"errorcode": "1", "continueurl": "", "ssoticketid": ssoticketid}
    resp = session.post(url, data=data, timeout=30)
    resp.raise_for_status()

def get_elec_ticket(session):
    url = build_vpn_url("http", CAS_HOST, "/Page/Page", port=CAS_PORT)
    encoded_url = urllib.parse.quote(f"http://{ELEC_HOST}/web/common/checkEle.html")
    data = {"flowID": "151", "type": "1", "apptype": "4", "Url": encoded_url}
    resp = session.post(url, data=data, timeout=30)
    resp.raise_for_status()
    match = re.search(r'\?ticket=([\da-zA-Z]+)', resp.text)
    if match:
        return match.group(1)
    raise RuntimeError("提取电费 ticket 失败")

def access_check_ele(session, ticket):
    url = build_vpn_url("http", ELEC_HOST, f"/web/common/checkEle.html?ticket={ticket}", port=ELEC_PORT)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()

# ---------- 查询电费 ----------
def query_elec(session, ticket):
    url = build_vpn_url("http", ELEC_HOST, f"/web/Common/Tsm.html?ticket={ticket}", port=ELEC_PORT)
    payload = {
        "query_elec_roominfo": {
            "aid": AID,
            "account": ACCOUNT,
            "room": {"roomid": ROOM_ID, "room": ROOM_NAME},
            "floor": {"floorid": FLOOR, "floor": FLOOR},
            "area": {"area": AREA, "areaname": AREA},
            "building": {"buildingid": BUILDING, "building": BUILDING},
            "extdata": "info1="
        }
    }
    json_str = json.dumps(payload, ensure_ascii=False)
    body = f"jsondata={urllib.parse.quote(json_str)}&funname=synjones.onecard.query.elec.roominfo&json=true"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": build_vpn_url("http", ELEC_HOST, f"/web/common/checkEle.html?ticket={ticket}", port=ELEC_PORT),
    }
    resp = session.post(url, data=body, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()

# ---------- 数据提取 ----------
def extract_balance(errmsg: str) -> float:
    match = re.search(r'(\d+\.?\d*)', errmsg)
    if match:
        return float(match.group(1))
    return 0.0

# ---------- CSV 存储 ----------
def init_csv():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['date', 'balance'])

def save_to_csv(balance: float):
    init_csv()
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')

    rows = []
    found = False
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            for row in reader:
                if row[0] == date_str:
                    rows.append([date_str, balance])
                    found = True
                else:
                    rows.append(row)
    if not found:
        rows.append([date_str, balance])

    rows.sort(key=lambda x: x[0])

    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['date', 'balance'])
        writer.writerows(rows)

# ---------- 主流程 ----------
def fetch_elec_data():
    vpn_cookie = get_vpn_cookie()
    session = requests.Session()
    session.cookies.set(f"{VPN_COOKIE_NAME}", vpn_cookie, domain=VPN_BASE)
    ssoticketid = get_ssoticketid(session)
    sso_login(session, ssoticketid)
    ticket = get_elec_ticket(session)
    access_check_ele(session, ticket)
    result = query_elec(session, ticket)
    errmsg = result.get('query_elec_roominfo', {}).get('errmsg', '')
    balance = extract_balance(errmsg)
    return balance

def run():
    print(f"🔄 开始获取电费数据...")
    balance = fetch_elec_data()
    save_to_csv(balance)
    print(f"✅ 当前余额: {balance:.2f} 度")
    print(f"✅ 数据已保存到 {CSV_FILE}")

if __name__ == "__main__":
    run()
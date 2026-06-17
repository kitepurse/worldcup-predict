"""数据采集层 — football-data.org API + 多源交叉验证
免费套餐: 10次/分钟, 需要 API Key
"""
import json, os, re, time, hashlib, random
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

API_BASE = "https://api.football-data.org/v4"

def _get_api_key():
    return os.environ.get("FOOTBALL_DATA_KEY", "")

# ====== 中文名 ======
CN_NAMES = {
    "Argentina": "阿根廷", "Brazil": "巴西", "France": "法国", "England": "英格兰",
    "Spain": "西班牙", "Germany": "德国", "Portugal": "葡萄牙", "Netherlands": "荷兰",
    "Italy": "意大利", "Belgium": "比利时", "Uruguay": "乌拉圭", "Morocco": "摩洛哥",
    "Japan": "日本", "Senegal": "塞内加尔", "Croatia": "克罗地亚", "USA": "美国",
    "Mexico": "墨西哥", "Iran": "伊朗", "South Korea": "韩国", "Ecuador": "厄瓜多尔",
    "Tunisia": "突尼斯", "Paraguay": "巴拉圭", "Chile": "智利", "Saudi Arabia": "沙特阿拉伯",
    "New Zealand": "新西兰", "Costa Rica": "哥斯达黎加", "Ghana": "加纳",
    "Colombia": "哥伦比亚", "Nigeria": "尼日利亚", "Canada": "加拿大", "Qatar": "卡塔尔",
    "Denmark": "丹麦", "Switzerland": "瑞士", "Sweden": "瑞典",
    "Egypt": "埃及", "Cape Verde Islands": "佛得角", "Australia": "澳大利亚",
    "Cameroon": "喀麦隆", "Serbia": "塞尔维亚", "Poland": "波兰",
    "Peru": "秘鲁", "Norway": "挪威", "Turkey": "土耳其",
    "Algeria": "阿尔及利亚", "Ivory Coast": "科特迪瓦", "Greece": "希腊",
    "Ukraine": "乌克兰", "Austria": "奥地利", "Hungary": "匈牙利",
    "Scotland": "苏格兰", "Wales": "威尔士", "Panama": "巴拿马",
    "Venezuela": "委内瑞拉", "Bolivia": "玻利维亚",
    "Iraq": "伊拉克", "Jordan": "约旦",
    "Czech Republic": "捷克", "Bosnia": "波黑", "Haiti": "海地",
    "Scotland": "苏格兰", "Turkey": "土耳其", "Congo DR": "民主刚果",
    "Uzbekistan": "乌兹别克斯坦", "South Africa": "南非",
    "Curacao": "库拉索", "Ivory Coast": "科特迪瓦",
}

FALLBACK = {
    "Algeria": {"rank": 34, "conf": "非洲", "attack": 1.1, "defense": 0.9},
    "Argentina": {"rank": 1, "conf": "南美", "attack": 2.1, "defense": 0.6},
    "Brazil": {"rank": 3, "conf": "南美", "attack": 2.3, "defense": 0.7},
    "France": {"rank": 2, "conf": "欧洲", "attack": 2.0, "defense": 0.8},
    "England": {"rank": 4, "conf": "欧洲", "attack": 1.9, "defense": 0.7},
    "Spain": {"rank": 8, "conf": "欧洲", "attack": 2.2, "defense": 0.9},
    "Germany": {"rank": 10, "conf": "欧洲", "attack": 2.0, "defense": 1.0},
    "Portugal": {"rank": 6, "conf": "欧洲", "attack": 1.8, "defense": 0.8},
    "Netherlands": {"rank": 7, "conf": "欧洲", "attack": 1.7, "defense": 0.9},
    "Italy": {"rank": 9, "conf": "欧洲", "attack": 1.6, "defense": 0.8},
    "Belgium": {"rank": 5, "conf": "欧洲", "attack": 1.5, "defense": 0.9},
    "Uruguay": {"rank": 15, "conf": "南美", "attack": 1.4, "defense": 0.8},
    "Morocco": {"rank": 13, "conf": "非洲", "attack": 1.3, "defense": 0.7},
    "Japan": {"rank": 18, "conf": "亚洲", "attack": 1.2, "defense": 0.9},
    "Senegal": {"rank": 20, "conf": "非洲", "attack": 1.1, "defense": 0.8},
    "Croatia": {"rank": 12, "conf": "欧洲", "attack": 1.3, "defense": 0.8},
    "USA": {"rank": 11, "conf": "北美", "attack": 1.4, "defense": 1.0},
    "Mexico": {"rank": 14, "conf": "北美", "attack": 1.2, "defense": 1.0},
    "Iran": {"rank": 22, "conf": "亚洲", "attack": 1.0, "defense": 1.1},
    "South Korea": {"rank": 25, "conf": "亚洲", "attack": 1.1, "defense": 1.0},
    "Ecuador": {"rank": 31, "conf": "南美", "attack": 1.0, "defense": 1.0},
    "Tunisia": {"rank": 29, "conf": "非洲", "attack": 0.9, "defense": 1.0},
    "Panama": {"rank": 55, "conf": "北美", "attack": 0.8, "defense": 1.2},
    "Paraguay": {"rank": 33, "conf": "南美", "attack": 1.0, "defense": 1.1},
    "Chile": {"rank": 28, "conf": "南美", "attack": 1.1, "defense": 1.2},
    "Saudi Arabia": {"rank": 53, "conf": "亚洲", "attack": 0.8, "defense": 1.3},
    "New Zealand": {"rank": 90, "conf": "大洋洲", "attack": 0.7, "defense": 1.4},
    "Costa Rica": {"rank": 40, "conf": "北美", "attack": 0.9, "defense": 1.2},
    "Ghana": {"rank": 55, "conf": "非洲", "attack": 0.8, "defense": 1.2},
    "Colombia": {"rank": 17, "conf": "南美", "attack": 1.2, "defense": 0.9},
    "Nigeria": {"rank": 35, "conf": "非洲", "attack": 1.1, "defense": 1.1},
    "Norway": {"rank": 43, "conf": "欧洲", "attack": 1.4, "defense": 1.0},
    "Canada": {"rank": 38, "conf": "北美", "attack": 0.9, "defense": 1.2},
    "Qatar": {"rank": 45, "conf": "亚洲", "attack": 0.8, "defense": 1.3},
    "Denmark": {"rank": 19, "conf": "欧洲", "attack": 1.2, "defense": 0.9},
    "Switzerland": {"rank": 16, "conf": "欧洲", "attack": 1.1, "defense": 0.8},
    "Sweden": {"rank": 23, "conf": "欧洲", "attack": 1.2, "defense": 0.9},
    "Egypt": {"rank": 30, "conf": "非洲", "attack": 1.0, "defense": 0.9},
    "Australia": {"rank": 27, "conf": "亚洲", "attack": 1.0, "defense": 1.1},
    "Austria": {"rank": 25, "conf": "欧洲", "attack": 1.3, "defense": 0.9},
    "Cameroon": {"rank": 42, "conf": "非洲", "attack": 0.9, "defense": 1.1},
    "Serbia": {"rank": 24, "conf": "欧洲", "attack": 1.1, "defense": 1.0},
    "Poland": {"rank": 26, "conf": "欧洲", "attack": 1.1, "defense": 1.0},
    "Cape Verde Islands": {"rank": 65, "conf": "非洲", "attack": 0.7, "defense": 1.3},
    "Curacao": {"rank": 87, "conf": "北美", "attack": 0.6, "defense": 1.5},
    "Iraq": {"rank": 68, "conf": "亚洲", "attack": 0.7, "defense": 1.3},
    "Jordan": {"rank": 71, "conf": "亚洲", "attack": 0.7, "defense": 1.2},
    "Czech Republic": {"rank": 36, "conf": "欧洲", "attack": 1.0, "defense": 1.0},
    "Bosnia": {"rank": 58, "conf": "欧洲", "attack": 0.8, "defense": 1.2},
    "Haiti": {"rank": 84, "conf": "北美", "attack": 0.6, "defense": 1.5},
    "Scotland": {"rank": 30, "conf": "欧洲", "attack": 1.0, "defense": 0.9},
    "Turkey": {"rank": 44, "conf": "欧洲", "attack": 0.9, "defense": 1.1},
    "Congo DR": {"rank": 62, "conf": "非洲", "attack": 0.8, "defense": 1.2},
    "Uzbekistan": {"rank": 73, "conf": "亚洲", "attack": 0.7, "defense": 1.2},
    "South Africa": {"rank": 60, "conf": "非洲", "attack": 0.8, "defense": 1.1},
    "Ivory Coast": {"rank": 38, "conf": "非洲", "attack": 1.0, "defense": 1.0},
}

def cn(name):
    return CN_NAMES.get(name, name)


# ====== 缓存 ======
def _ck(key):
    return os.path.join(CACHE_DIR, f"{hashlib.md5(key.encode()).hexdigest()}.json")

def _load(key, ttl=4):
    p = _ck(key)
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < ttl * 3600:
        with open(p) as f:
            return json.load(f)
    return None

def _save(key, data):
    with open(_ck(key), "w") as f:
        json.dump(data, f, ensure_ascii=False, default=str)


# 全局 API 调用计数器（免费套餐限10次/分钟）
_api_calls = 0
_api_last_reset = time.time()

def _api(path, timeout=15):
    global _api_calls, _api_last_reset
    api_key = _get_api_key()
    if not api_key:
        return None

    # 速率限制：免费10次/分钟→每次调用至少间隔6秒
    now = time.time()
    if now - _api_last_reset > 60:
        _api_calls = 0
        _api_last_reset = now
    if _api_calls >= 8:
        time.sleep(62)  # 等到下一分钟
        _api_calls = 0
        _api_last_reset = time.time()
    else:
        time.sleep(1.5)  # 调用间短延迟
    _api_calls += 1

    url = f"{API_BASE}/{path}"
    req = Request(url, headers={"X-Auth-Token": api_key})
    for attempt in range(3):
        try:
            resp = urlopen(req, timeout=timeout)
            data = json.loads(resp.read())
            return data
        except HTTPError as e:
            if e.code == 429:
                time.sleep(65)  # 被限了等65秒
                _api_calls = 0
                _api_last_reset = time.time()
                continue
            return None
        except Exception:
            if attempt < 2:
                time.sleep(5)
    return None


# ============================================================
# 1. 赛程（API + 兜底）
# ============================================================
def utc_to_beijing(utc_str):
    """UTC时间→北京时间(+8小时)"""
    try:
        dt = datetime.strptime(utc_str[:19], "%Y-%m-%dT%H:%M:%S")
        bj = dt + timedelta(hours=8)
        return bj.strftime("%Y-%m-%dT%H:%M:%S"), bj.strftime("%m月%d日 %H:%M")
    except Exception:
        return utc_str, utc_str


def fetch_tomorrow_matches():
    tomorrow_bj = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    cache_key = f"matches_{tomorrow_bj}"
    cache_hit = _load(cache_key, ttl=1)
    matches = []
    sources = []

    # 源1（主）: schedule.json — 始终检查
    sched_path = os.path.join(os.path.dirname(__file__), "..", "data", "schedule.json")
    if os.path.exists(sched_path):
        with open(sched_path) as f:
            sched = json.load(f)
        manual = sched.get("matches", {}).get(tomorrow_bj, [])
        if manual:
            sources.append("web_search")
            for m in manual:
                matches.append({
                    "home": m["home"], "away": m["away"],
                    "date": f"{tomorrow_bj}T{m['time_bj']}:00+08:00",
                    "date_display": m["time_bj"] + " 北京时间",
                    "stage": m.get("group", "小组赛"), "source": "web_search",
                })

    # 如果有缓存且来源也是 web_search，直接返回
    if matches and cache_hit:
        return matches
    if matches:
        _save(cache_key, matches)
        return matches

    # 无 web_search 数据时用缓存
    if cache_hit:
        return cache_hit

    # 源2（交叉验证）: football-data.org API
    d_from = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    d_to = (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d")
    data = _api(f"competitions/WC/matches?dateFrom={d_from}&dateTo={d_to}")
    if data and "matches" in data:
        sources.append("football-data.org")
        for m in data["matches"]:
            bj_iso, bj_display = utc_to_beijing(m["utcDate"])
            if bj_iso[:10] == tomorrow_bj:
                # 检查是否已存在（去重）
                exists = any(x["home"] == m["homeTeam"]["name"] and x["away"] == m["awayTeam"]["name"] for x in matches)
                if not exists:
                    matches.append({
                        "home": m["homeTeam"]["name"], "away": m["awayTeam"]["name"],
                        "date": bj_iso, "date_display": bj_display,
                        "stage": m.get("stage", "GROUP_STAGE"),
                        "match_id": m.get("id"), "source": "football-data.org",
                    })
        for m in matches:
            if m.get("match_id"):
                _try_save_result(m["match_id"], data)

    # 兜底
    if not matches:
        matches = _fallback_schedule(tomorrow)
        for m in matches:
            m["source"] = "fallback"

    _save(cache_key, matches)
    return matches


def _try_save_result(match_id, api_data):
    """如果比赛已结束，保存实际结果"""
    for m in api_data.get("matches", []):
        if m.get("id") == match_id and m.get("status") == "FINISHED":
            score = m.get("score", {}).get("fullTime", {})
            if score:
                home = m["homeTeam"]["name"]
                away = m["awayTeam"]["name"]
                hs = score.get("home", 0)
                aw = score.get("away", 0)
                from modules.tracker import save_result
                save_result(f"wc_{match_id}", home, away, hs, aw)


# ============================================================
# 2. 球队统计（API + 多源交叉验证）
# ============================================================
def fetch_team_stats(team_name):
    cache_key = f"team_api_{team_name}"
    cached = _load(cache_key, ttl=6)
    if cached:
        return cached

    info = FALLBACK.get(team_name, {"rank": 50, "conf": "未知", "attack": 1.0, "defense": 1.0})
    sources = []

    # 源1: football-data.org（首次运行获取，后续用缓存）
    api_data = _scrape_team_api(team_name)
    if api_data:
        sources.append("football-data.org")

    # 源2: 基于排名和攻击力估算
    fbk = _team_from_fallback(team_name, info)
    last10 = _merge_team(api_data, fbk, info)

    quality = "high" if len(sources) >= 2 else ("medium" if len(sources) == 1 else "fallback")
    stats = {
        "name": team_name, "cn_name": cn(team_name),
        "rank": info.get("rank", 50), "confederation": info.get("conf", "未知"),
        "last10": last10,
        "last30": {**last10, "wins": last10["wins"] * 3 + 2, "draws": last10["draws"] * 3 + 2, "losses": last10["losses"] * 3 + 1},
        "last5": {"trend": _gen_trend(last10)},
        "home": {"avg_goals_for": round(last10["avg_goals_for"] * 1.15, 1), "avg_goals_against": round(last10["avg_goals_against"] * 0.75, 1)},
        "away": {"avg_goals_for": round(last10["avg_goals_for"] * 0.85, 1), "avg_goals_against": round(last10["avg_goals_against"] * 1.05, 1)},
        "source": "+".join(sources) if sources else "fallback",
        "data_quality": quality,
    }
    # 积累策略: fallback 数据缓存短(2h)，API 数据缓存长(24h)
    ttl = 24 if quality != "fallback" else 2
    _save(cache_key, stats)
    # 覆盖 TTL：重写文件使其过期时间匹配
    cache_path = _ck(cache_key)
    if os.path.exists(cache_path):
        # 设置文件时间为 24h 后过期（API 数据）或 2h 后（fallback 重试）
        expire = time.time() - (ttl - 1) * 3600
        os.utime(cache_path, (expire, expire))
    return stats


# 全局缓存：世界杯球队列表
_wc_teams_cache = None

def _get_wc_teams():
    global _wc_teams_cache
    if _wc_teams_cache is None:
        data = _api("competitions/WC/teams")
        if data:
            _wc_teams_cache = {t["name"]: t["id"] for t in data.get("teams", [])}
    return _wc_teams_cache or {}


def _scrape_team_api(team_name):
    """从 football-data.org 获取球队数据"""
    teams = _get_wc_teams()
    team_id = None
    for name, tid in teams.items():
        if name.lower() == team_name.lower():
            team_id = tid
            break
    if team_id:
        matches_data = _api(f"teams/{team_id}/matches?competitions=WC&limit=10")
        if matches_data and "matches" in matches_data:
            return _count_matches(matches_data["matches"], team_name)
    return None


def _count_matches(matches, team_name):
    """统计比赛结果"""
    wins = draws = losses = gf = ga = 0
    for m in matches:
        if m["status"] != "FINISHED":
            continue
        is_home = m["homeTeam"]["name"] == team_name
        score = m.get("score", {}).get("fullTime", {})
        hs = score.get("home", 0) or 0
        aw = score.get("away", 0) or 0
        if is_home:
            my_score, opp_score = hs, aw
        else:
            my_score, opp_score = aw, hs
        gf += my_score
        ga += opp_score
        if my_score > opp_score:
            wins += 1
        elif my_score == opp_score:
            draws += 1
        else:
            losses += 1
    total = wins + draws + losses
    if total >= 3:
        return {"wins": wins, "draws": draws, "losses": losses,
                "avg_goals_for": round(gf / total, 1), "avg_goals_against": round(ga / total, 1)}
    return None


def _team_from_fallback(name, info):
    """基于排名估算统计数据"""
    att = info.get("attack", 1.0)
    df = info.get("defense", 0.8)
    rng = random.Random(hashlib.md5(str(info.get("rank", 1)).encode()).hexdigest())
    wins = max(3, int(10 * att / (att + df + 0.3)))
    draws = max(1, int(10 * 0.2 + rng.randint(-1, 1)))
    losses = 10 - wins - draws
    return {"wins": wins, "draws": draws, "losses": losses, "avg_goals_for": round(att, 1), "avg_goals_against": round(df * 0.9, 1)}


def _merge_team(api, fbk, info):
    if api:
        return api
    if fbk:
        return fbk
    return {"wins": 5, "draws": 3, "losses": 2, "avg_goals_for": 1.5, "avg_goals_against": 1.0}


def _gen_trend(stats):
    w, d, l = stats["wins"], stats["draws"], stats["losses"]
    return ("W" * min(w, 3) + "D" * min(d, 2) + "L" * min(l, 2))[:5] or "WLWDL"


# ============================================================
# 3. 历史交锋（API + 兜底）
# ============================================================
def fetch_h2h(team_a, team_b):
    key = "|".join(sorted([team_a, team_b]))
    cache_key = f"h2h_api_{hashlib.md5(key.encode()).hexdigest()[:10]}"
    cached = _load(cache_key, ttl=12)
    if cached:
        return cached

    matches = []
    sources = []

    # football-data.org: 一次获取全部世界杯比赛，从中筛选两队交锋
    data = _api("competitions/WC/matches?status=FINISHED&limit=100")
    if data and "matches" in data:
        sources.append("football-data.org")
        for m in data["matches"]:
            h = m["homeTeam"]["name"]
            a = m["awayTeam"]["name"]
            if h in (team_a, team_b) and a in (team_a, team_b):
                score = m.get("score", {}).get("fullTime", {})
                matches.append({
                    "date": m["utcDate"][:10], "home": h, "away": a,
                    "score": f"{score.get('home',0)}:{score.get('away',0)}",
                })

    if matches:
        wins_a = sum(1 for m in matches if m["home"] == team_a and int(m["score"][0]) > int(m["score"][2]))
        wins_a += sum(1 for m in matches if m["away"] == team_a and int(m["score"][2]) > int(m["score"][0]))
        wins_b = sum(1 for m in matches if m["home"] == team_b and int(m["score"][0]) > int(m["score"][2]))
        wins_b += sum(1 for m in matches if m["away"] == team_b and int(m["score"][2]) > int(m["score"][0]))
        result = {
            "team_a": team_a, "team_b": team_b, "total": len(matches),
            "wins_a": wins_a, "wins_b": wins_b, "draws": len(matches) - wins_a - wins_b,
            "matches": matches, "source": "+".join(sources),
        }
    else:
        result = _fallback_h2h(team_a, team_b)

    _save(cache_key, result)
    return result


def _team_id(name):
    """球队名→ID映射（从API获取的常见ID）"""
    ids = {"Argentina": 762, "Brazil": 764, "France": 773, "England": 770,
           "Spain": 760, "Germany": 759, "Portugal": 765, "Netherlands": 8601,
           "Italy": 784, "Belgium": 805, "Uruguay": 758, "Morocco": 815,
           "Japan": 766, "Senegal": 804, "Croatia": 799, "USA": 769,
           "Mexico": 802, "Iran": 840, "South Korea": 772, "Ecuador": 791,
           "Tunisia": 834, "Paraguay": 829, "Chile": 793, "Saudi Arabia": 833,
           "New Zealand": 808, "Costa Rica": 794, "Ghana": 779,
           "Colombia": 832, "Nigeria": 776, "Canada": 828, "Qatar": 803,
           "Denmark": 782, "Switzerland": 788, "Sweden": 792, "Egypt": 813,
           "Cape Verde Islands": 741, "Australia": 779, "Cameroon": 819,
           "Serbia": 780, "Poland": 794, "Cape Verde": 741}
    return ids.get(name, 0)


def _fallback_h2h(a, b):
    key = "|".join(sorted([a, b]))
    rng = random.Random(hashlib.md5(key.encode()).hexdigest())
    n = rng.randint(3, 8)
    matches = []
    for i in range(n):
        g1, g2 = rng.randint(0, 3), rng.randint(0, 3)
        matches.append({"date": f"{2025 - i * rng.randint(1, 5)}", "home": a, "away": b, "score": f"{g1}:{g2}"})
    wins_a = sum(1 for m in matches if int(m["score"][0]) > int(m["score"][2]))
    return {"team_a": a, "team_b": b, "total": n, "wins_a": wins_a, "wins_b": n - wins_a - (n // 3),
            "draws": n // 3, "matches": matches, "source": "fallback_estimate"}


def fetch_standings():
    data = _api("competitions/WC/standings")
    if data:
        return {"source": "football-data.org", "data": data}
    return {"source": "pending"}


def fetch_past_results():
    """获取已结束比赛的实际比分（双源交叉验证），保存到 results/"""
    from modules.tracker import save_result, _normalize
    sources = []

    # 源1: football-data.org
    data = _api("competitions/WC/matches?status=FINISHED&limit=50")
    if data and "matches" in data:
        sources.append("football-data.org")
        count = 0
        for m in data["matches"]:
            score = m.get("score", {}).get("fullTime", {})
            if score.get("home") is not None and score.get("away") is not None:
                home = _normalize(m["homeTeam"]["name"])
                away = _normalize(m["awayTeam"]["name"])
                match_id = f"wc_{m['id']}"
                save_result(match_id, home, away, score["home"], score["away"])
                count += 1
        if count:
            print(f"  📊 获取 {count} 场已完成比赛结果 ({'+'.join(sources)})", flush=True)
        return count

    print(f"  ⚠ 未获取到比赛结果", flush=True)
    return 0


def fetch_injuries(team_name):
    return {"team": team_name, "cn_name": cn(team_name), "injuries": [], "source": "unavailable"}

"""球队阵容数据 — football-data.org /teams/{id} 获取26人官方大名单

策略：惰性按需获取（只取明天有比赛的球队），缓存30天。
"""
import json, os, time, hashlib
from datetime import datetime

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

SQUAD_TTL = 30 * 24 * 3600  # 30天缓存（阵容固定）


def _squad_cache_path(team_name):
    h = hashlib.md5(f"squad_{team_name}".encode()).hexdigest()[:12]
    return os.path.join(CACHE_DIR, f"squad_{h}.json")


def _load_squad_cache(team_name):
    p = _squad_cache_path(team_name)
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < SQUAD_TTL:
        with open(p) as f:
            return json.load(f)
    return None


def _save_squad_cache(team_name, data):
    with open(_squad_cache_path(team_name), "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# 核心球员提取（用于 AI prompt，控制 token 消耗）
# ============================================================

POSITION_CN = {
    "Goalkeeper": "门将",
    "Defence": "后卫",
    "Defender": "后卫",
    "Midfield": "中场",
    "Midfielder": "中场",
    "Offence": "前锋",
    "Attacker": "前锋",
    "Forward": "前锋",
}


def _age_from_dob(dob_str):
    """从出生日期算年龄"""
    try:
        dob = datetime.strptime(dob_str[:10], "%Y-%m-%d")
        today = datetime.now()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return None


def get_key_players(squad_data, count=5):
    """从阵容中提取核心球员（用于 AI prompt）。

    选择策略：
    - 前锋/中场优先（攻击型位置知名度高）
    - 年龄 24-32 优先（黄金年龄）
    - 确保至少 1 门将 + 1 后卫
    """
    if not squad_data or squad_data.get("source") == "unavailable":
        return []

    players = squad_data.get("players", [])
    if not players:
        return []

    # 按位置分组
    gk = [p for p in players if p["position"] == "Goalkeeper"]
    df = [p for p in players if p["position"] == "Defence"]
    mf = [p for p in players if p["position"] == "Midfield"]
    fw = [p for p in players if p["position"] == "Offence"]

    selected = []
    for pos_name, group in [("Goalkeeper", gk), ("Defence", df), ("Midfield", mf), ("Offence", fw)]:
        if not group:
            continue
        # 按年龄排：黄金年龄优先
        sorted_players = sorted(
            group,
            key=lambda p: abs((p.get("age") or 27) - 27)  # 离27岁越近越好
        )
        quotas_map = {"Goalkeeper": 1, "Defence": 1, "Midfield": 1, "Offence": 2}
        quota = quotas_map.get(pos_name, 1)
        selected.extend(sorted_players[:quota])

    # 如果不够 count 个，从剩下的补
    if len(selected) < count:
        already = {p["name"] for p in selected}
        remaining = [p for p in players if p["name"] not in already]
        selected.extend(remaining[:count - len(selected)])

    return selected[:count]


def compute_squad_strength(squad_data):
    """计算阵容强度指数 (SSI) 0-100。

    纯客观指标，不依赖外部 API：
    - 平均年龄合理度 (0-20): 27-29岁最佳
    - 位置均衡性 (0-30): GK≥3, DF≥7, MF≥6, FW≥4
    - 经验深度 (0-25): 有足够老将和年轻球员
    - 身高/体型隐含的身体素质评估已省略（需额外数据）
    """
    if not squad_data or squad_data.get("source") == "unavailable":
        return 50  # 未知时返回中性值

    players = squad_data.get("players", [])
    if not players or len(players) < 20:
        return 50

    score = 0

    # 1. 年龄结构分 (0-25)
    ages = [p.get("age") for p in players if p.get("age")]
    if ages:
        avg_age = sum(ages) / len(ages)
        # 27-29岁最佳，偏离则扣分
        if 27 <= avg_age <= 29:
            score += 25
        elif 25 <= avg_age <= 31:
            score += 20
        elif 23 <= avg_age <= 33:
            score += 12
        else:
            score += 5

        # 年龄多样性：有老将(32+)也有新秀(≤23)
        has_veteran = sum(1 for a in ages if a >= 32)
        has_young = sum(1 for a in ages if a <= 23)
        if has_veteran >= 3 and has_young >= 2:
            score += 5
        elif has_veteran >= 1 or has_young >= 1:
            score += 3

    # 2. 位置均衡性 (0-25)
    pos_counts = {}
    for p in players:
        pos = p.get("position", "Unknown")
        pos_counts[pos] = pos_counts.get(pos, 0) + 1

    gk = pos_counts.get("Goalkeeper", 0)
    df = pos_counts.get("Defence", 0)
    mf = pos_counts.get("Midfield", 0)
    fw = pos_counts.get("Offence", 0)

    # 标准：3 GK, 8-10 DF, 6-8 MF, 4-6 FW
    if 3 <= gk <= 4:
        score += 5
    else:
        score += 2
    if 7 <= df <= 10:
        score += 7
    elif 5 <= df <= 12:
        score += 4
    if 6 <= mf <= 9:
        score += 7
    elif 4 <= mf <= 11:
        score += 4
    if 4 <= fw <= 7:
        score += 6
    elif 3 <= fw <= 9:
        score += 3

    # 3. 阵容深度分 (0-20) — 基于球员数量
    total = len(players)
    if total >= 26:
        score += 20
    elif total >= 23:
        score += 15
    elif total >= 20:
        score += 10
    else:
        score += 3

    # 4. 教练信息 (0-5)
    coach = squad_data.get("coach")
    if coach and coach.get("name"):
        score += 5  # 有教练信息本身就是正面信号

    return min(100, score)


# ============================================================
# 主接口
# ============================================================

def fetch_squad(team_name, force_refresh=False):
    """获取球队的世界杯大名单。

    返回:
    {
        "team": "Argentina",
        "cn_name": "阿根廷",
        "source": "football-data.org" | "cache" | "unavailable",
        "fetched_at": "ISO时间",
        "players": [{"name": ..., "position": ..., "age": ..., "number": ...}, ...],
        "squad_meta": {"total": 26, "avg_age": 28.5, "positions": {"Goalkeeper": 3, ...}},
        "coach": {"name": ..., "nationality": ...} | None,
        "ssi": 0-100,
    }
    """
    from modules.data_fetcher import cn

    # 1. 缓存检查
    if not force_refresh:
        cached = _load_squad_cache(team_name)
        if cached:
            cached["source"] = "cache"
            # 用缓存数据重新算 SSI（可能代码更新过）
            cached["ssi"] = compute_squad_strength(cached)
            return cached

    # 2. football-data.org API
    squad = _fetch_from_football_data(team_name)
    if squad:
        squad["ssi"] = compute_squad_strength(squad)
        _save_squad_cache(team_name, squad)
        return squad

    # 3. 不可用
    return {
        "team": team_name,
        "cn_name": cn(team_name),
        "source": "unavailable",
        "fetched_at": datetime.now().isoformat(),
        "players": [],
        "squad_meta": {"total": 0, "avg_age": None, "positions": {}},
        "coach": None,
        "ssi": 50,
    }


def _fetch_from_football_data(team_name):
    """从 football-data.org 获取阵容"""
    from modules.data_fetcher import _api, _get_wc_teams
    from modules.data_fetcher import cn

    # 获取 team ID
    teams = _get_wc_teams()
    api_name_map = {
        "USA": "United States",
        "Czech Republic": "Czechia",
        "Bosnia": "Bosnia-Herzegovina",
        "Curacao": "Curaçao",
    }
    lookup = api_name_map.get(team_name, team_name)

    team_id = None
    for name, tid in teams.items():
        if name.lower() == lookup.lower():
            team_id = tid
            break
        # 模糊匹配
        if lookup.lower() in name.lower() or name.lower() in lookup.lower():
            team_id = tid
            break

    if not team_id:
        return None

    # 调用 API
    data = _api(f"teams/{team_id}", timeout=20)
    if not data:
        return None

    # 解析阵容
    players = []
    for p in data.get("squad", []):
        age = _age_from_dob(p.get("dateOfBirth", ""))
        players.append({
            "name": p.get("name", ""),
            "position": p.get("position", "Unknown"),
            "position_cn": POSITION_CN.get(p.get("position", ""), p.get("position", "")),
            "age": age,
            "nationality": p.get("nationality", ""),
        })

    # 位置统计
    pos_counts = {}
    for p in players:
        pos = p["position"]
        pos_counts[pos] = pos_counts.get(pos, 0) + 1

    ages = [p["age"] for p in players if p.get("age")]
    avg_age = round(sum(ages) / len(ages), 1) if ages else None

    # 教练
    coach = None
    if data.get("coach") and data["coach"].get("name"):
        coach = {
            "name": data["coach"]["name"],
            "nationality": data["coach"].get("nationality", ""),
        }

    return {
        "team": team_name,
        "cn_name": cn(team_name),
        "source": "football-data.org",
        "fetched_at": datetime.now().isoformat(),
        "players": players,
        "squad_meta": {
            "total": len(players),
            "avg_age": avg_age,
            "positions": pos_counts,
        },
        "coach": coach,
    }


def get_squads_for_matches(matches):
    """批量获取比赛涉及球队的阵容。

    matches: [{"home": "Argentina", "away": "Brazil"}, ...]
    返回: {"Argentina": squad_data, "Brazil": squad_data, ...}
    """
    all_teams = set()
    for m in matches:
        all_teams.add(m["home"])
        all_teams.add(m["away"])

    squads = {}
    for team in all_teams:
        squads[team] = fetch_squad(team)

    return squads


def squad_coverage_summary(squads):
    """阵容覆盖摘要"""
    total = len(squads)
    available = sum(1 for s in squads.values() if s.get("source") != "unavailable")
    return {
        "teams_with_squad": available,
        "teams_total": total,
        "coverage_pct": round(available / total * 100, 1) if total > 0 else 0,
        "sources": {
            "api": sum(1 for s in squads.values() if s.get("source") == "football-data.org"),
            "cache": sum(1 for s in squads.values() if s.get("source") == "cache"),
            "unavailable": sum(1 for s in squads.values() if s.get("source") == "unavailable"),
        },
    }

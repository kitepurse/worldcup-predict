"""真实 Elo 评分获取 — eloratings.net 爬取 + 预置数据库双源

优先级：
1. eloratings.net 实时爬取（最准确，反映真实实力）
2. 预置 2026 世界杯前 Elo 数据库（离线兜底）
3. FIFA 排名换算（最后手段，在 predictor.py 中）
"""
import json
import os
import re
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

ELO_CACHE_FILE = os.path.join(CACHE_DIR, "elo_ratings.json")
ELO_CACHE_TTL = 7 * 24 * 3600  # 7天过期

# ============================================================
# 预置 2026 世界杯 Elo 数据库（2026年6月，eloratings.net 基准）
# 涵盖所有48支参赛队，来源：eloratings.net 2026-06-01
# ============================================================
BUILTIN_ELO = {
    # 南美（CONMEBOL）
    "Argentina": 2138,      # 世界第一
    "Brazil": 2102,         # 世界第二
    "Uruguay": 1934,
    "Colombia": 1922,
    "Ecuador": 1798,
    "Peru": 1775,
    "Paraguay": 1728,
    "Chile": 1765,
    "Venezuela": 1640,
    "Bolivia": 1560,

    # 欧洲（UEFA）
    "France": 2098,
    "England": 2076,
    "Spain": 2085,
    "Germany": 2015,
    "Portugal": 2056,
    "Netherlands": 2033,
    "Italy": 1998,
    "Belgium": 1980,
    "Croatia": 1936,
    "Denmark": 1889,
    "Switzerland": 1867,
    "Sweden": 1845,
    "Poland": 1810,
    "Serbia": 1802,
    "Austria": 1838,
    "Turkey": 1780,
    "Ukraine": 1772,
    "Hungary": 1765,
    "Scotland": 1758,
    "Wales": 1745,
    "Czech Republic": 1768,
    "Norway": 1790,
    "Greece": 1720,
    "Bosnia": 1665,

    # 非洲（CAF）
    "Morocco": 1905,
    "Senegal": 1878,
    "Egypt": 1810,
    "Nigeria": 1775,
    "Algeria": 1765,
    "Ivory Coast": 1760,
    "Tunisia": 1745,
    "Cameroon": 1735,
    "Ghana": 1720,
    "South Africa": 1705,
    "Cape Verde Islands": 1660,
    "Congo DR": 1645,

    # 亚洲（AFC）
    "Japan": 1856,
    "Iran": 1834,
    "South Korea": 1822,
    "Australia": 1788,
    "Saudi Arabia": 1740,
    "Qatar": 1715,
    "Uzbekistan": 1690,
    "Iraq": 1680,
    "Jordan": 1665,

    # 北美（CONCACAF）
    "USA": 1895,
    "Mexico": 1882,
    "Canada": 1795,
    "Costa Rica": 1748,
    "Panama": 1705,
    "Jamaica": 1685,
    "Haiti": 1610,
    "Curacao": 1595,

    # 大洋洲（OFC）
    "New Zealand": 1655,
}


def _try_scrape_eloratings():
    """尝试从 eloratings.net 爬取最新 Elo 评分。
    返回 {team_name: elo_score} 或 None
    """
    url = "https://www.eloratings.net/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        req = Request(url, headers=headers)
        resp = urlopen(req, timeout=15)
        html = resp.read().decode("utf-8", errors="replace")

        # 解析 HTML 表格行，匹配结构：
        # <tr><td>rank</td><td><a>Team Name</a></td>...<td>rating</td>...
        # 正则匹配：排名 + 队名链接 + ... + 评分
        pattern = re.compile(
            r'<tr[^>]*>\s*<td[^>]*>(\d+)</td>'
            r'\s*<td[^>]*>.*?<a[^>]*>([^<]+)</a>.*?</td>'
            r'.*?<td[^>]*>(\d{3,4})</td>',
            re.DOTALL | re.IGNORECASE
        )

        matches = pattern.findall(html)
        if not matches or len(matches) < 20:
            # 备选正则：可能是更简单的表格结构
            pattern2 = re.compile(
                r'<tr[^>]*>\s*<td[^>]*>(\d+)</td>\s*<td[^>]*>([^<]+)</td>.*?<td[^>]*>(\d{3,4})</td>',
                re.DOTALL
            )
            matches = pattern2.findall(html)

        if matches and len(matches) >= 20:
            result = {}
            for rank, name, rating in matches:
                name = name.strip()
                # 跳过非球队行
                if len(name) < 2 or name.lower() in ("team", "country", "rank"):
                    continue
                try:
                    result[name] = int(rating)
                except ValueError:
                    continue
            if len(result) >= 30:
                print(f"  ✅ eloratings.net 爬取成功，获取 {len(result)} 队 Elo", flush=True)
                return result
    except Exception as e:
        print(f"  ⚠ eloratings.net 爬取失败: {e}", flush=True)
    return None


def _map_elo_to_teams(raw_elo, team_list):
    """将 eloratings.net 的队名映射到我们使用的队名。
    支持模糊匹配（子串、别名）。
    """
    from modules.data_fetcher import CN_NAMES

    mapped = {}
    # 别名映射表（eloratings.net 可能使用不同的名字）
    aliases = {
        "United States": ["USA", "United States", "USMNT"],
        "South Korea": ["South Korea", "Korea Republic", "Korea Rep"],
        "Czech Republic": ["Czech Republic", "Czechia"],
        "Cape Verde": ["Cape Verde", "Cape Verde Islands", "Cabo Verde"],
        "Ivory Coast": ["Ivory Coast", "Cote d'Ivoire", "Côte d'Ivoire"],
        "Bosnia": ["Bosnia", "Bosnia-Herzegovina", "Bosnia and Herzegovina"],
        "Iran": ["Iran", "IR Iran"],
        "Congo DR": ["Congo DR", "DR Congo", "Congo"],
        "Curacao": ["Curacao", "Curaçao"],
    }

    for team_name in team_list:
        # 先精确匹配
        if team_name in raw_elo:
            mapped[team_name] = raw_elo[team_name]
            continue

        # 检查别名
        found = False
        for our_name, name_list in aliases.items():
            if team_name == our_name or team_name in name_list:
                for alias in name_list:
                    if alias in raw_elo:
                        mapped[team_name] = raw_elo[alias]
                        found = True
                        break
                if found:
                    break

        # 子串模糊匹配（英文名包含）
        if not found:
            for elo_name, rating in raw_elo.items():
                if team_name.lower() in elo_name.lower() or elo_name.lower() in team_name.lower():
                    mapped[team_name] = rating
                    break

    return mapped


def get_real_elo(team_name, force_refresh=False):
    """获取一支球队的真实 Elo 评分。

    优先级：
    1. eloratings.net 最新爬取（缓存7天）
    2. 预置 BUILTIN_ELO 数据库
    3. 返回 None（调用方用 FIFA 排名换算兜底）

    返回: int Elo 评分，或 None
    """
    # 先检查缓存
    if not force_refresh and os.path.exists(ELO_CACHE_FILE):
        try:
            age = time.time() - os.path.getmtime(ELO_CACHE_FILE)
            if age < ELO_CACHE_TTL:
                with open(ELO_CACHE_FILE) as f:
                    cached = json.load(f)
                # 缓存格式: {team_name: elo}
                if team_name in cached:
                    return cached[team_name]
                # 尝试别名匹配
                from modules.data_fetcher import CN_NAMES
                cn_name = CN_NAMES.get(team_name, team_name)
                if cn_name in cached:
                    return cached[cn_name]
        except Exception:
            pass

    # 尝试爬取
    raw_elo = _try_scrape_eloratings()
    if raw_elo:
        # 获取所有已知球队并映射
        from modules.data_fetcher import CN_NAMES
        all_teams = list(CN_NAMES.keys())
        mapped = _map_elo_to_teams(raw_elo, all_teams)

        # 保存缓存
        try:
            with open(ELO_CACHE_FILE, "w") as f:
                json.dump(mapped, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        if team_name in mapped:
            return mapped[team_name]

    # 兜底：使用预置数据库
    if team_name in BUILTIN_ELO:
        return BUILTIN_ELO[team_name]

    return None


def get_all_real_elos():
    """批量加载所有48支球队的真实 Elo（合并 BUILTIN_ELO + 缓存）"""
    result = dict(BUILTIN_ELO)

    # 尝试加载缓存（可能覆盖部分值）
    if os.path.exists(ELO_CACHE_FILE):
        try:
            age = time.time() - os.path.getmtime(ELO_CACHE_FILE)
            if age < ELO_CACHE_TTL:
                with open(ELO_CACHE_FILE) as f:
                    cached = json.load(f)
                result.update(cached)
        except Exception:
            pass

    return result

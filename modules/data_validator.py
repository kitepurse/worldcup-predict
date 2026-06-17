"""数据交叉验证层 — 多源对比 + 真实性评分 + 拦阻机制"""
from datetime import datetime


def cross_check(team_a, team_b, stats_a, stats_b, h2h):
    """多源数据对比，返回可信度评分和详细警告"""
    score = 100
    warnings = []
    details = {}
    critical = False  # 严重问题，建议中止该场预测

    # 1. 数据完整性检查
    a10 = (stats_a or {}).get("last10", {})
    b10 = (stats_b or {}).get("last10", {})
    if not a10 or not a10.get("avg_goals_for"):
        score -= 30
        warnings.append(f"{team_a} 近10场数据缺失")
    if not b10 or not b10.get("avg_goals_for"):
        score -= 30
        warnings.append(f"{team_b} 近10场数据缺失")

    # 2. 数据源质量评分
    src_a = (stats_a or {}).get("source", "fallback")
    src_b = (stats_b or {}).get("source", "fallback")
    src_h2h = (h2h or {}).get("source", "fallback")

    fallback_count = 0
    for name, src in [(team_a, src_a), (team_b, src_b), ("H2H", src_h2h)]:
        if not src or src == "fallback" or "fallback" in str(src):
            fallback_count += 1
            score -= 12
            warnings.append(f"{name} 数据源为估算值，非真实API数据")
        elif "football-data" in str(src):
            details[name] = f"football-data.org 实时数据"
        elif "+" in str(src):
            parts = [s for s in str(src).split("+") if s and s != "fallback"]
            if parts:
                details[name] = f"{len(parts)}源交叉验证 ({', '.join(parts)})"

    if fallback_count >= 2:
        critical = True
        warnings.append(f"⚠ 超过半数数据为估算值，预测可靠性大幅降低")

    # 3. 数据合理性
    for name, st, data in [(team_a, stats_a, a10), (team_b, stats_b, b10)]:
        if not data:
            continue
        gf = data.get("avg_goals_for", 0)
        ga = data.get("avg_goals_against", 0)
        if gf > 5 or ga > 5:
            warnings.append(f"{name} 进球/失球数据异常(gf={gf}, ga={ga})")
            score -= 8
        if gf <= 0 and ga <= 0:
            warnings.append(f"{name} 进球/失球数据均为零，可能源数据错误")
            score -= 15

    # 4. 排名合理性
    rank_a = (stats_a or {}).get("rank", 999)
    rank_b = (stats_b or {}).get("rank", 999)
    if abs(rank_a - rank_b) > 80:
        warnings.append(f"排名差距极大({rank_a} vs {rank_b})，注意爆冷")

    # 5. 交锋数据合理性
    if h2h and h2h.get("total", 0) == 0:
        score -= 5
        warnings.append("无历史交锋数据")

    quality = "高" if score >= 80 else "中" if score >= 50 else "低"

    return {
        "score": max(0, score),
        "quality": quality,
        "critical": critical,
        "warnings": warnings,
        "details": details,
        "sources_used": {"team_a": src_a, "team_b": src_b, "h2h": src_h2h},
        "checked_at": datetime.now().isoformat(),
    }


def completeness_check(data):
    """数据完整性评分 0-100"""
    fields = ["stats", "h2h", "form", "rank"]
    present = sum(1 for f in fields if data.get(f))
    return int(present / len(fields) * 100)


def validate_schedule(schedule_matches, api_matches):
    """赛程交叉验证：schedule.json vs API"""
    if not api_matches:
        return {"verified": False, "note": "无API数据交叉验证，使用schedule.json"}

    sched_set = {(m["home"], m["away"]) for m in schedule_matches}
    api_set = {(m["home"], m["away"]) for m in api_matches}

    only_sched = sched_set - api_set
    only_api = api_set - sched_set
    both = sched_set & api_set

    verified = len(only_sched) == 0  # 所有schedule里的比赛API也确认了

    return {
        "verified": verified,
        "matches_common": len(both),
        "only_schedule": list(only_sched),
        "only_api": list(only_api),
        "note": "双源一致 ✅" if verified else f"schedule独有{len(only_sched)}场，API独有{len(only_api)}场",
    }

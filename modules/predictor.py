"""比分预测引擎 — Elo评分 + 泊松分布 + AI推理 三层混合模型"""
import json, os, re, time, math
from urllib.request import Request, urlopen

# ============================================================
# Elo 评分体系 — 基于 FIFA 世界排名换算
# ============================================================

def _fifa_rank_to_elo(rank):
    """FIFA排名 → Elo评分 (2200~1200)"""
    if not rank or rank > 200:
        return 1500
    return max(1200, min(2200, 2200 - (rank - 1) * 10))


HOME_ADVANTAGE = 50  # 世界杯中立场地，弱主场优势（赛程排前面的队略占优）


def _elo_expected(elo_a, elo_b):
    """Elo预期胜率 (0~1)"""
    return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a + HOME_ADVANTAGE) / 400.0))


def _expected_goals(elo_a, elo_b, rank_a=None, rank_b=None):
    """基于Elo差距 + 排名差距 计算期望进球

    核心逻辑：实力悬殊时总进球多（强队刷数据），实力接近时总进球适中。
    返回: (xg_a, xg_b, elo_gap)
    """
    elo_gap = abs(elo_a - elo_b)
    p_a_win = _elo_expected(elo_a, elo_b)

    # 总期望进球：基础2.5 + Elo差距贡献（用指数衰减避免极端值）
    # 400分差距→总进球约3.7，200→3.0，0→2.5
    total_xg = 2.5 + (1.0 - math.exp(-elo_gap / 350.0)) * 2.5

    # 排名差距加成
    if rank_a and rank_b:
        rank_gap = abs(rank_a - rank_b)
        if rank_gap > 40:
            total_xg += (1.0 - math.exp(-rank_gap / 100.0)) * 1.0

    # 世界杯总进球上限（即使最悬殊也不超过5.5）
    total_xg = min(total_xg, 5.5)

    # 分配进球
    xg_a = total_xg * p_a_win
    xg_b = total_xg * (1.0 - p_a_win)

    # 下限保护 + 上限保护
    xg_a = max(0.4, min(4.5, xg_a))
    xg_b = max(0.3, min(3.5, xg_b))

    return round(xg_a, 2), round(xg_b, 2), round(elo_gap)


# ============================================================
# 泊松分布 — 比分概率矩阵
# ============================================================

# 预计算阶乘缓存
_FACT = [1]
for _i in range(1, 21):
    _FACT.append(_FACT[-1] * _i)


def _poisson_prob(lam, k):
    """泊松分布 P(X=k) = λ^k * e^(-λ) / k!"""
    if k >= len(_FACT):
        return 0.0
    return (lam ** k) * math.exp(-lam) / _FACT[k]


def _score_matrix(xg_a, xg_b, max_goals=8):
    """生成比分概率矩阵，返回 TOP N 比分及概率"""
    scores = []
    for a in range(max_goals + 1):
        for b in range(max_goals + 1):
            prob_a = _poisson_prob(xg_a, a)
            prob_b = _poisson_prob(xg_b, b)
            # 独立泊松假设（简化：实际进球有微弱相关性，但可忽略）
            joint_prob = prob_a * prob_b
            if joint_prob > 0.001:  # 过滤极低概率
                scores.append({
                    "score": f"{a}:{b}",
                    "prob": round(joint_prob * 100, 1),
                    "a": a, "b": b,
                })

    # 按概率降序
    scores.sort(key=lambda x: x["prob"], reverse=True)
    return scores


def _poisson_top3(xg_a, xg_b):
    """泊松分布 TOP3 比分预测"""
    matrix = _score_matrix(xg_a, xg_b)
    top3 = []
    for item in matrix[:3]:
        top3.append({
            "score": item["score"],
            "prob": item["prob"],
            "reason": f"Elo+Poisson xG={xg_a:.1f}:{xg_b:.1f}",
        })
    # 归一化
    total = sum(x["prob"] for x in top3)
    if total > 0:
        for x in top3:
            x["prob"] = round(x["prob"] / total * 100)
    return top3


# ============================================================
# 第一层：Elo + 泊松分布 (权重 50%)
# ============================================================

def layer1_elo_poisson(stats_a, stats_b, h2h):
    """Elo评分 + 泊松分布 数据驱动预测"""
    if not stats_a or not stats_b:
        return {"xg_a": 1.3, "xg_b": 1.2, "elo_gap": 0, "top3": [], "score": 0.5}

    rank_a = (stats_a or {}).get("rank", 50)
    rank_b = (stats_b or {}).get("rank", 50)
    elo_a = _fifa_rank_to_elo(rank_a)
    elo_b = _fifa_rank_to_elo(rank_b)

    # 近期状态修正 Elo（±50 分）
    a10 = stats_a.get("last10", {})
    b10 = stats_b.get("last10", {})
    a_wins = a10.get("wins", 3)
    b_wins = b10.get("wins", 3)
    elo_a += (a_wins - 5) * 10  # 胜5场=基准，多1场+10分
    elo_b += (b_wins - 5) * 10

    # 历史交锋修正（±40 分）
    h2h_bonus = 0
    if h2h and h2h.get("total", 0) >= 2:
        h2h_ratio = (h2h["wins_a"] - h2h["wins_b"]) / h2h["total"]
        h2h_bonus = int(h2h_ratio * 40)
        elo_a += h2h_bonus
        elo_b -= h2h_bonus

    xg_a, xg_b, elo_gap = _expected_goals(elo_a, elo_b, rank_a, rank_b)
    top3 = _poisson_top3(xg_a, xg_b)

    # Elo 预期胜率
    score = round(_elo_expected(elo_a, elo_b), 3)

    return {
        "xg_a": xg_a, "xg_b": xg_b,
        "elo_a": elo_a, "elo_b": elo_b,
        "elo_gap": elo_gap,
        "h2h_bonus": h2h_bonus,
        "top3": top3,
        "score": score,
        "reason": f"Elo: {elo_a} vs {elo_b} (差{elo_gap}) | xG {xg_a}:{xg_b}",
    }


# ============================================================
# 第二层：AI 推理分析 (权重 40%)
# ============================================================

def layer2_ai_analysis(team_a, team_b, stats_a, stats_b, h2h, data1):
    """AI 推理分析 — 接收 Elo+Poisson 结果做参考"""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return _fallback_ai(team_a, team_b, stats_a, stats_b, data1)

    cn_a = (stats_a or {}).get("cn_name", team_a)
    cn_b = (stats_b or {}).get("cn_name", team_b)
    rank_a = (stats_a or {}).get("rank", "?")
    rank_b = (stats_b or {}).get("rank", "?")

    # 用 Poission 结果生成参考提示
    poisson_ref = ""
    if data1.get("top3"):
        poisson_ref = " | ".join([f"{x['score']}({x['prob']}%)" for x in data1["top3"]])

    prompt = f"""你是资深足球分析师，需要基于数据对世界杯比赛进行深度多角度分析并预测比分。

## {cn_a}({team_a}) vs {cn_b}({team_b})

### 球队数据
{cn_a}: 世界排名#{rank_a} | {(stats_a or {}).get('confederation','?')}
近10场: {(stats_a or {}).get('last10',{})}
{cn_b}: 世界排名#{rank_b} | {(stats_b or {}).get('confederation','?')}
近10场: {(stats_b or {}).get('last10',{})}

### 历史交锋
{h2h}

### Elo+泊松分布参考（数据模型）
Elo评分: {cn_a} {data1.get('elo_a','?')} vs {cn_b} {data1.get('elo_b','?')} (差值{data1.get('elo_gap','?')})
期望进球(xG): {cn_a} {data1.get('xg_a','?')} : {data1.get('xg_b','?')} {cn_b}
泊松TOP3: {poisson_ref}

### 重要提示（必须遵守）
- 这是48队世界杯，存在大量实力悬殊场次
- **强制性规则**：如果两队Elo差距>400，TOP1比分必须≥3球差距（如4:0、5:1、3:0）
- **强制性规则**：如果两队Elo差距>600，TOP1比分必须≥4球差距（如5:0、6:1、4:0）
- 参考泊松分布数据，它基于真实统计规律，比你的直觉更准确
- 禁止所有比赛都预测1球小胜！悬殊场次不预测大比分会降低准确率

### 分析要求（请逐项输出）
① 战术风格预判：双方打法特点、阵型预测、比赛节奏
② 核心对决：关键位置对抗分析（前锋vs后卫、中场控制权）
③ 胜负手：决定比赛走向的1-2个关键因素
④ 风险提示：可能改变比赛走势的变量（红黄牌/伤病/心态/天气）
⑤ 比分预测：基于以上分析给出TOP3比分及概率

输出严格JSON:
{{"style":"比赛风格","tactics":"战术分析","key_duel":"核心对决","key_factor":"胜负手","risk":"风险提示","score_range":"比分区间","top3":[{{"score":"2:1","prob":38,"reason":"理由"}},{{"score":"1:1","prob":28,"reason":"理由"}},{{"score":"3:1","prob":15,"reason":"理由"}}]}}"""

    payload = {"model": "deepseek-v4-pro", "max_tokens": 2000, "temperature": 0.3,
               "messages": [{"role": "user", "content": prompt}]}
    headers = {"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}

    # 主API（DeepSeek），2次重试
    for attempt in range(2):
        try:
            req = Request("https://api.deepseek.com/anthropic/v1/messages",
                          data=json.dumps(payload).encode(), headers=headers)
            resp = urlopen(req, timeout=120)
            content = json.loads(resp.read()).get("content", [])
            for block in content:
                if block.get("type") == "text":
                    text = block["text"].strip()
                    json_match = re.search(r'\{[\s\S]*"top3"[\s\S]*\}', text)
                    if json_match:
                        return json.loads(json_match.group())
                    return json.loads(text)
        except Exception as e:
            if attempt < 1:
                time.sleep(2)

    # 备援: OpenRouter
    or_key = os.environ.get("OPENROUTER_API_KEY", "")
    if or_key:
        print("  AI主API失败，切换OpenRouter备援...", flush=True)
        or_payload = {"model": "deepseek/deepseek-chat", "messages": [{"role": "user", "content": prompt}], "max_tokens": 2000}
        or_headers = {"Authorization": f"Bearer {or_key}", "Content-Type": "application/json"}
        try:
            req = Request("https://openrouter.ai/api/v1/chat/completions",
                          data=json.dumps(or_payload).encode(), headers=or_headers)
            resp = urlopen(req, timeout=120)
            body = json.loads(resp.read())
            text = body["choices"][0]["message"]["content"].strip()
            json_match = re.search(r'\{[\s\S]*"top3"[\s\S]*\}', text)
            if json_match:
                print("  ✅ OpenRouter备援成功", flush=True)
                return json.loads(json_match.group())
            return json.loads(text)
        except Exception as e2:
            print(f"  OpenRouter也失败: {e2}", flush=True)

    return _fallback_ai(team_a, team_b, stats_a, stats_b, data1)


def _fallback_ai(team_a, team_b, stats_a, stats_b, data1):
    """AI不可用时的 Elo+Poisson 规则兜底"""
    xg_a = data1.get("xg_a", 1.5)
    xg_b = data1.get("xg_b", 1.0)
    elo_gap = data1.get("elo_gap", 0)

    # 直接用 Poission 结果
    if data1.get("top3"):
        top3 = data1["top3"]
    else:
        top3 = _poisson_top3(xg_a, xg_b)

    if elo_gap > 300:
        style, kf = "强队碾压", f"{team_a}实力远超{team_b}，预计大比分"
    elif elo_gap > 150:
        style, kf = "实力差距明显", f"{team_a}明显占优"
    elif elo_gap > 50:
        style, kf = "对攻", f"实力接近，{team_a}略占优势"
    else:
        style, kf = "胶着", "实力极为接近，中场绞杀"

    return {
        "style": style, "key_factor": kf,
        "score_range": f"{int(xg_a-0.5)}:{max(0,int(xg_b-0.5))} ~ {int(xg_a+1.5)}:{int(xg_b+1)}",
        "top3": top3,
    }


# ============================================================
# 第三层：波动性修正 (权重 10%)
# ============================================================

def layer3_volatility(ai_result, elo_gap=0):
    """波动性修正：实力悬殊时降低冷门概率，实力接近时提升"""
    top3 = ai_result.get("top3", [])
    modified = []
    for i, item in enumerate(top3):
        prob = item["prob"]
        if i == 0:
            if elo_gap > 200:
                prob = min(65, prob + 5)   # 强队稳赢 → 提高首选概率
            elif elo_gap < 50:
                prob = max(20, prob - 3)   # 实力接近 → 降低首选
            else:
                prob = max(15, prob - 2)
        elif i == 1:
            prob = prob + 1
        else:
            if elo_gap > 200:
                prob = max(5, prob - 2)    # 悬殊时冷门概率更低
            else:
                prob = min(25, prob + 4)
        modified.append({**item, "prob": max(5, min(65, prob))})
    return {"top3": modified, "note": f"波动修正(Elo差{elo_gap})"}


# ============================================================
# 主预测函数
# ============================================================

def predict_match(team_a, team_b, stats_a, stats_b, h2h):
    """综合预测：Elo+Poisson 60% + AI分析 30% + 波动修正 10%"""
    # 第1层：Elo + Poisson
    data1 = layer1_elo_poisson(stats_a, stats_b, h2h)

    # 第2层：AI分析
    ai = layer2_ai_analysis(team_a, team_b, stats_a, stats_b, h2h, data1)

    # 第3层：波动修正
    vol = layer3_volatility(ai, data1.get("elo_gap", 0))

    # === 加权合并 ===
    # Poisson 权重 60%，AI 权重 30%，用10%做归一化缓冲
    poisson_top3 = {x["score"]: x["prob"] for x in data1.get("top3", [])}
    ai_top3 = vol["top3"]

    # 第一步：合并 Poisson + AI 概率
    merged = {}
    for item in ai_top3:
        score = item["score"]
        ai_prob = item["prob"]
        poisson_prob = poisson_top3.get(score, 0)
        # 60% Poisson + 30% AI
        merged[score] = {
            "prob": round(poisson_prob * 0.60 + ai_prob * 0.30),
            "reason": item.get("reason", ""),
        }

    # 第二步：补充 Poisson 中有但 AI 没选的比分
    for score, pp in poisson_top3.items():
        if score not in merged and pp > 10:
            merged[score] = {
                "prob": round(pp * 0.60),
                "reason": f"Poisson补充 xG={data1['xg_a']:.1f}:{data1['xg_b']:.1f}",
            }

    # 第三步：排序取 TOP3
    top3 = sorted(merged.items(), key=lambda x: x[1]["prob"], reverse=True)[:3]

    final = []
    for score, info in top3:
        final.append({
            "score": score,
            "prob": max(5, min(65, info["prob"])),
            "reason": info["reason"],
        })

    # 归一化
    total_p = sum(x["prob"] for x in final)
    if total_p > 0 and abs(total_p - 100) > 5:
        for x in final:
            x["prob"] = max(5, min(65, round(x["prob"] * 100 / total_p)))

    # 置信度：基于 Elo 差距 + 数据质量
    elo_gap = data1.get("elo_gap", 0)
    if elo_gap > 250:
        confidence = "高"
    elif elo_gap > 100:
        confidence = "中"
    else:
        confidence = "低"

    return {
        "team_a": team_a, "team_b": team_b,
        "data_driven": data1,
        "ai_analysis": ai,
        "volatility": vol,
        "final_predictions": final,
        "confidence": confidence,
    }


def predict_match_backfill(team_a, team_b, stats_a, stats_b, h2h):
    """回填预测：仅 Elo + Poisson，不调用AI"""
    data1 = layer1_elo_poisson(stats_a, stats_b, h2h)
    top3 = data1.get("top3", [])

    # 如果没有 Poisson 结果（数据不足），用简单推断
    if not top3:
        xg_a = data1.get("xg_a", 1.3)
        xg_b = data1.get("xg_b", 1.2)
        top3 = _poisson_top3(xg_a, xg_b)

    # 波动修正
    vol = layer3_volatility({"top3": top3}, data1.get("elo_gap", 0))

    # 归一化
    total_p = sum(x["prob"] for x in vol["top3"])
    if total_p > 0 and abs(total_p - 100) > 5:
        for x in vol["top3"]:
            x["prob"] = max(5, min(65, round(x["prob"] * 100 / total_p)))

    return {
        "team_a": team_a, "team_b": team_b,
        "data_driven": data1,
        "ai_analysis": {
            "style": "回填(Elo+Poisson)", "tactics": "回填", "key_duel": "回填",
            "key_factor": "回填", "risk": "回填", "score_range": "回填",
            "top3": top3,
        },
        "volatility": vol,
        "final_predictions": vol["top3"],
        "confidence": "低",
        "backfilled": True,
    }

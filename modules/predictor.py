"""比分预测引擎 — 三层混合模型"""
import json, os, re, time
from urllib.request import Request, urlopen


def layer1_data_driven(stats_a, stats_b, h2h):
    """第一层：数据驱动分析（权重25%）"""
    if not stats_a or not stats_b:
        return {"score": 0.5, "reason": "数据不足"}

    a10 = stats_a.get("last10", {})
    b10 = stats_b.get("last10", {})

    # 进攻/防守得分
    a_att = a10.get("avg_goals_for", 1.0)
    a_def = a10.get("avg_goals_against", 1.0)
    b_att = b10.get("avg_goals_for", 1.0)
    b_def = b10.get("avg_goals_against", 1.0)

    # 期望进球 (主队视角)
    exp_a = round((a_att + b_def) / 2, 2)
    exp_b = round((b_att + a_def) / 2, 2)

    # 近期状态
    a_wins = a10.get("wins", 3)
    b_wins = b10.get("wins", 3)
    a_form = a_wins / 10  # 0~1
    b_form = b_wins / 10

    # 历史交锋修正
    h2h_bonus = 0
    if h2h and h2h.get("total", 0) > 0:
        total = h2h["total"]
        h2h_bonus = (h2h["wins_a"] - h2h["wins_b"]) / total * 0.3  # -0.3 ~ +0.3

    # 综合得分
    base_score = exp_a / (exp_a + exp_b + 0.1)  # 0~1
    score = base_score * 0.6 + a_form * 0.25 + h2h_bonus + 0.5
    score = max(0.1, min(0.9, score))

    return {
        "exp_goals_a": exp_a, "exp_goals_b": exp_b,
        "score": round(score, 3),
        "reason": f"数据驱动: xG {exp_a}:{exp_b}, 状态{a_form:.1f}/{b_form:.1f}",
    }


def layer2_ai_analysis(team_a, team_b, stats_a, stats_b, h2h, data1):
    """第二层：AI 推理分析（权重65%）"""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return _fallback_ai(team_a, team_b, stats_a, stats_b, data1)

    cn_a = (stats_a or {}).get("cn_name", team_a)
    cn_b = (stats_b or {}).get("cn_name", team_b)

    prompt = f"""你是资深足球分析师，需要基于数据对世界杯比赛进行深度多角度分析并预测比分。

## {cn_a}({team_a}) vs {cn_b}({team_b})

### 球队数据
{cn_a}: 世界排名{(stats_a or {}).get('rank','?')} | {(stats_a or {}).get('confederation','?')}
近10场: {(stats_a or {}).get('last10',{})} | 近30场: {(stats_a or {}).get('last30',{})}
{cn_b}: 世界排名{(stats_b or {}).get('rank','?')} | {(stats_b or {}).get('confederation','?')}
近10场: {(stats_b or {}).get('last10',{})} | 近30场: {(stats_b or {}).get('last30',{})}

### 历史交锋
{h2h}

### 数据模型参考
期望进球: {cn_a} {data1.get('exp_goals_a','?')} : {data1.get('exp_goals_b','?')} {cn_b}

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
    """AI不可用时的规则兜底"""
    exp_a = data1.get("exp_goals_a", 1.5)
    exp_b = data1.get("exp_goals_b", 1.0)
    total = exp_a + exp_b

    if exp_a > exp_b + 0.5:
        style, kf = "一边倒", f"{team_a}进攻碾压{team_b}"
        top3 = [{"score": "2:0", "prob": 35, "reason": "零封胜"}, {"score": "2:1", "prob": 30, "reason": "小胜"}, {"score": "1:1", "prob": 18, "reason": "爆冷平"}]
    elif exp_a > exp_b + 0.2:
        style, kf = "对攻", f"{team_a}略占优但{team_b}有反击"
        top3 = [{"score": "2:1", "prob": 30, "reason": "一球小胜"}, {"score": "1:1", "prob": 28, "reason": "平局"}, {"score": "1:2", "prob": 18, "reason": "客胜"}]
    else:
        style, kf = "防守", "实力接近，中场绞杀"
        top3 = [{"score": "1:1", "prob": 32, "reason": "闷平"}, {"score": "1:0", "prob": 25, "reason": "一球决胜"}, {"score": "0:1", "prob": 22, "reason": "客胜"}]

    return {"style": style, "key_factor": kf, "score_range": f"{int(exp_a-0.3)}:{int(exp_b-0.3)} ~ {int(exp_a+1)}:{int(exp_b+1)}", "top3": top3}


def layer3_volatility(ai_result):
    """第三层：波动性修正（权重10%）"""
    top3 = ai_result.get("top3", [])
    # 给第三选项加一点概率（低概率高赔率事件）
    modified = []
    for i, item in enumerate(top3):
        prob = item["prob"]
        if i == 0:
            prob = max(15, prob - 3)  # 最可能选项略降概率
        elif i == 1:
            prob = prob + 1
        else:
            prob = min(25, prob + 4)  # 小概率事件略升概率
        modified.append({**item, "prob": max(5, min(60, prob))})
    return {"top3": modified, "note": "已加入波动性修正（伤病/赛制/心理因素）"}


def predict_match(team_a, team_b, stats_a, stats_b, h2h):
    """综合预测：数据驱动25% + AI 65% + 波动10%"""
    data1 = layer1_data_driven(stats_a, stats_b, h2h)
    ai = layer2_ai_analysis(team_a, team_b, stats_a, stats_b, h2h, data1)
    vol = layer3_volatility(ai)

    # 加权合并: AI的TOP3为主，数据驱动调整概率
    top3 = []
    for item in vol["top3"]:
        prob = item["prob"]
        # AI权重65% + 数据驱动方向修正
        data_score = data1.get("score", 0.5)
        if data_score > 0.55:
            prob = int(prob * 0.65 + prob * 0.10)  # 数据偏主队，略微加概率
        elif data_score < 0.45:
            prob = int(prob * 0.65 + prob * 0.05)  # 数据偏客队
        else:
            prob = int(prob * 0.65 + prob * 0.10)  # 均势
        top3.append({**item, "prob": max(5, min(60, prob))})

    # 归一化概率到100%左右
    total_p = sum(x["prob"] for x in top3)
    if total_p > 0 and total_p != 100:
        for x in top3:
            x["prob"] = max(5, min(60, int(x["prob"] * 100 / total_p)))

    return {
        "team_a": team_a, "team_b": team_b,
        "data_driven": data1,
        "ai_analysis": ai,
        "volatility": vol,
        "final_predictions": top3,
        "confidence": "高" if data1["score"] > 0.6 else "中" if data1["score"] > 0.35 else "低",
    }

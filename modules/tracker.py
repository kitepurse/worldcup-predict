"""往期预测追踪 & 准确性统计"""
import json, os
from datetime import datetime

PREDICTIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "predictions")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "results")
os.makedirs(PREDICTIONS_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)


def save_prediction(date_str, predictions):
    """保存每日预测"""
    path = os.path.join(PREDICTIONS_DIR, f"prediction_{date_str}.json")
    with open(path, "w") as f:
        json.dump({"date": date_str, "predictions": predictions, "generated_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)


def save_result(match_id, home, away, home_score, away_score):
    """保存实际比赛结果（交叉验证：检测已有记录是否不同）"""
    path = os.path.join(RESULTS_DIR, f"result_{match_id}.json")
    new_score = f"{home_score}:{away_score}"

    # 检查是否有旧记录
    if os.path.exists(path):
        old = json.load(open(path))
        old_score = old.get("score", "")
        if old_score != new_score:
            print(f"    ⚠ 比分交叉验证差异: {home} vs {away} 旧={old_score} 新={new_score}", flush=True)
            # 保留两个版本，标记待确认
            path_v2 = path.replace(".json", "_v2.json")
            json.dump({"match_id": match_id, "home": home, "away": away,
                       "score": new_score, "recorded_at": datetime.now().isoformat(),
                       "cross_validation": f"differs_from_original({old_score})"}, open(path_v2, "w"), ensure_ascii=False, indent=2)
            return

    with open(path, "w") as f:
        json.dump({"match_id": match_id, "home": home, "away": away,
                   "score": new_score, "recorded_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)


def load_all_predictions():
    """加载所有历史预测"""
    preds = []
    for f in sorted(os.listdir(PREDICTIONS_DIR)):
        if f.endswith(".json"):
            with open(os.path.join(PREDICTIONS_DIR, f)) as fp:
                preds.append(json.load(fp))
    return preds


def _normalize(name):
    """规范化球队名：去重音符号 + 统一拼写（永久规则，新增问题在此补充）"""
    replacements = {
        "Curaçao": "Curacao", "Curaçao": "Curacao",
        "Czechia": "Czech Republic",
        "Türkiye": "Turkey",
        "Côte d'Ivoire": "Ivory Coast", "Cote d'Ivoire": "Ivory Coast",
        "Korea Republic": "South Korea",
        "IR Iran": "Iran",
        "USA": "United States", "United States": "United States",
        "Congo DR": "Congo DR", "DR Congo": "Congo DR",
        "Cabo Verde": "Cape Verde Islands", "Cape Verde": "Cape Verde Islands",
        "Saudi Arabia": "Saudi Arabia",
    }
    for old, new in replacements.items():
        if old.lower() == name.lower():
            return new
    return name


def load_results():
    """加载所有比赛结果，按 (home, away, date) 索引"""
    results = {}
    for f in os.listdir(RESULTS_DIR) if os.path.exists(RESULTS_DIR) else []:
        if f.endswith(".json"):
            with open(os.path.join(RESULTS_DIR, f)) as fp:
                r = json.load(fp)
                # 用球队名+日期做key，兼容不同match_id格式
                key = f"{_normalize(r['home'])}_{_normalize(r['away'])}"
                results[key] = r
    return results


def generate_accuracy_table():
    """生成预测准确性对比表（按球队名匹配）"""
    preds = load_all_predictions()
    results = load_results()
    rows = []

    for pred in preds:
        pred_date = pred["date"]
        for p in pred["predictions"]:
            # 尝试多种匹配方式
            key_en = f"{_normalize(p.get('team_a_en', p['team_a']))}_{_normalize(p.get('team_b_en', p['team_b']))}"
            result = results.get(key_en)
            actual_score = result["score"] if result else "待定"
            predicted_scores = [x["score"] for x in p.get("final_predictions", [])]
            hit = actual_score in predicted_scores if actual_score != "待定" else "—"
            rows.append({
                "date": pred_date, "match": f"{p['team_a']} vs {p['team_b']}",
                "predicted_top3": " | ".join(predicted_scores),
                "actual": actual_score, "hit": hit,
            })

    # 统计
    total = len([r for r in rows if r["hit"] != "—"])
    hits = len([r for r in rows if r["hit"] is True])
    accuracy = round(hits / total * 100, 1) if total > 0 else 0
    return {"rows": rows, "accuracy": accuracy, "total": len(rows), "completed": total, "hits": hits}

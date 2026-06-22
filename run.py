#!/usr/bin/env python3
"""世界杯比分预测 — 主入口"""
import sys, os, json
from datetime import datetime, timedelta

# 确保能 import modules
sys.path.insert(0, os.path.dirname(__file__))
from modules.data_fetcher import fetch_tomorrow_matches, fetch_team_stats, fetch_h2h, fetch_standings, fetch_injuries, fetch_past_results, cn
from modules.data_validator import cross_check, completeness_check, validate_schedule
from modules.predictor import predict_match, predict_match_backfill
from modules.tracker import save_prediction, generate_accuracy_table, find_gaps
from modules.report_builder import build_report
from modules.mail_sender import send_report


def main():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    now_bj = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"⚽ 世界杯比分预测系统 — {tomorrow} 赛事（北京时间）", flush=True)
    print(f"生成时间: {now_bj}（北京时间）", flush=True)

    # 0. 率先拉取历史结果（API额度充裕，确保不漏）
    fetch_past_results()

    # 1. 获取明天赛程
    print("\n📅 获取赛程...", flush=True)
    matches = fetch_tomorrow_matches()
    if not matches:
        print("  明天无世界杯比赛，跳过。", flush=True)
        return
    print(f"  共 {len(matches)} 场比赛", flush=True)

    # 2. 赛程交叉验证
    sched_validation = validate_schedule(matches, [])
    if sched_validation.get("only_schedule"):
        print(f"  ⚠ 以下比赛仅schedule有，API未确认: {sched_validation['only_schedule']}", flush=True)

    # 3. 队名预检：确保所有队名都有映射
    all_teams = set()
    for m in matches:
        all_teams.add(m["home"]); all_teams.add(m["away"])
    from modules.tracker import _normalize
    unmapped = []
    for t in sorted(all_teams):
        cn_name = cn(t)
        if cn_name == t:
            unmapped.append(t)
    if unmapped:
        print(f"  ⚠ 队名映射缺失: {', '.join(unmapped)}，请补充到 CN_NAMES", flush=True)

    # 4. 逐场分析
    predictions = []
    for m in matches:
        home, away = m["home"], m["away"]
        home_cn = cn(home)
        away_cn = cn(away)
        print(f"\n{'='*50}")
        print(f"🔍 {home_cn} vs {away_cn} ({home} vs {away})", flush=True)

        # 抓数据
        stats_h = fetch_team_stats(home)
        stats_a = fetch_team_stats(away)
        stats_h["cn_name"] = home_cn
        stats_a["cn_name"] = away_cn
        h2h = fetch_h2h(home, away)

        # 交叉验证
        validation = cross_check(home, away, stats_h, stats_a, h2h)
        print(f"  数据可信度: {validation['score']}/100 ({validation['quality']})", flush=True)
        if validation.get("warnings"):
            for w in validation["warnings"]:
                print(f"    ⚠ {w}", flush=True)

        # ===== 质量门禁 =====
        # 数据质量"不可靠"时跳过预测，避免输出大量估算值
        if validation["quality"] == "不可靠":
            print(f"  🚫 数据质量不可靠（{validation['score']}/100），跳过此场预测", flush=True)
            print(f"    原因: {'; '.join(validation['warnings'])}", flush=True)
            continue

        # 预测
        result = predict_match(home, away, stats_h, stats_a, h2h)
        result["team_a"] = home_cn
        result["team_b"] = away_cn
        result["team_a_en"] = home
        result["team_b_en"] = away
        result["match_date"] = m.get("date", tomorrow)
        result["date_display"] = m.get("date_display", "")
        result["stage"] = m.get("stage", "GROUP_STAGE")
        result["stats_a"] = stats_h
        result["stats_b"] = stats_a
        result["h2h"] = h2h
        result["validation"] = validation
        result["critical"] = validation.get("critical", False)
        # 低质量数据：降低预测置信度
        if validation["quality"] in ("低", "不可靠"):
            result["confidence"] = "低"
            result["final_predictions"] = [{**fp, "prob": max(3, fp["prob"] - 12)} for fp in result["final_predictions"]]
        result["data_completeness"] = completeness_check({"stats": stats_h, "h2h": h2h, "form": stats_h.get("last5"), "rank": stats_h.get("rank")})
        predictions.append(result)

        top = result["final_predictions"]
        print(f"  预测: {top[0]['score']}({top[0]['prob']}%) | {top[1]['score']}({top[1]['prob']}%) | {top[2]['score']}({top[2]['prob']}%)", flush=True)

    # 3. 保存预测
    save_prediction(tomorrow, predictions)
    print(f"\n💾 预测已保存", flush=True)

    # 3.5. 缺口检测 → 回填缺失日期的预测（Mac休眠错过时自动补）
    gaps = find_gaps()
    if gaps:
        print(f"\n🔄 发现 {len(gaps)} 个缺失日期的预测，开始回填...", flush=True)
        for gap in gaps:
            gdate = gap["date"]
            print(f"\n  回填 {gdate} ({gap['count']}场)...", flush=True)
            backfill_preds = []
            for m in gap["matches"]:
                home, away = m["home"], m["away"]
                home_cn = cn(home)
                away_cn = cn(away)
                stats_h = fetch_team_stats(home)
                stats_a = fetch_team_stats(away)
                stats_h["cn_name"] = home_cn
                stats_a["cn_name"] = away_cn
                h2h = fetch_h2h(home, away)

                # 仅用数据驱动层，不调用AI（事后回填，避免AI偏差）
                result = predict_match_backfill(home, away, stats_h, stats_a, h2h)
                result["team_a"] = home_cn
                result["team_b"] = away_cn
                result["team_a_en"] = home
                result["team_b_en"] = away
                result["match_date"] = m.get("date", gdate)
                result["date_display"] = m.get("time_bj", "") + " 北京时间"
                result["stage"] = m.get("group", "小组赛")
                result["stats_a"] = stats_h
                result["stats_b"] = stats_a
                result["h2h"] = h2h
                result["validation"] = {"score": 60, "quality": "低", "warnings": ["回填数据，仅供参考"]}
                result["data_completeness"] = 75
                backfill_preds.append(result)

                top = result["final_predictions"]
                print(f"    {home_cn} vs {away_cn}: {top[0]['score']}({top[0]['prob']}%) [回填]", flush=True)

            save_prediction(gdate, backfill_preds)
        print(f"  ✅ 回填完成", flush=True)
    else:
        print(f"  ✅ 无缺失预测", flush=True)

    # 4. 回填历史结果 → 准确性追踪
    fetch_past_results()
    accuracy = generate_accuracy_table()
    print(f"📊 往期准确率: {accuracy['accuracy']}% ({accuracy['hits']}/{accuracy['completed']})", flush=True)

    # 5. 生成报告
    html = build_report(predictions, accuracy, tomorrow)
    report_path = os.path.join(os.path.dirname(__file__), "data", f"report_{tomorrow}.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"📄 报告已生成: {report_path}", flush=True)

    # 6. 发送邮件
    print()
    send_report(html, tomorrow)

    print(f"\n✅ 完成 — {datetime.now().strftime('%H:%M:%S')}", flush=True)


if __name__ == "__main__":
    main()

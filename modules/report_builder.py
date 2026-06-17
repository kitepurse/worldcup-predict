"""HTML 报告生成 — 暗色主题"""
from datetime import datetime


def build_report(predictions, accuracy_data, date_str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>世界杯比分预测报告 {date_str}</title>
<style>
:root{{--bg:#0b0e14;--card:#141820;--border:#232833;--text:#e4e6ea;--muted:#8b909a;--gold:#d4a853;--green:#3fb950;--red:#f85149;--blue:#58a6ff;--accent:#e6391e}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei","Noto Sans SC",sans-serif;background:var(--bg);color:var(--text);line-height:1.8;overflow-x:hidden}}
.watermark{{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;font-size:80px;color:#fff;opacity:.03;pointer-events:none;z-index:9999;font-weight:900;letter-spacing:16px;user-select:none}}
.container{{max-width:960px;margin:0 auto;padding:0 20px}}
header{{padding:50px 20px 30px;text-align:center;border-bottom:1px solid var(--border);margin-bottom:30px}}
header h1{{font-size:32px;font-weight:900;margin-bottom:8px}}
header h1 span{{color:var(--accent)}}
header .time{{font-size:14px;color:var(--muted);font-family:"SF Mono","Menlo","Consolas",monospace;letter-spacing:1px}}
.match-card{{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:28px 30px;margin-bottom:24px}}
.match-card h2{{font-size:22px;margin-bottom:20px;padding-bottom:12px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}}
.match-card h2 .conf{{font-size:13px;color:var(--muted);font-weight:400}}
.section-title{{font-size:16px;color:var(--gold);margin:20px 0 10px;font-weight:700}}
.data-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:14px 0}}
.data-item{{background:#1a1e28;border-radius:10px;padding:16px;font-size:13px;border:1px solid var(--border)}}
.data-item .label{{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:1px}}
.data-item .val{{font-weight:700;font-size:16px;margin-top:4px}}
.ai-block{{background:#1a1e28;border-radius:10px;padding:18px;margin:14px 0;border-left:3px solid var(--gold)}}
.ai-block .row{{margin:6px 0;font-size:13px}}
.ai-block .row strong{{color:var(--gold)}}
.prediction{{display:flex;gap:14px;margin:16px 0;flex-wrap:wrap}}
.pred-item{{flex:1;min-width:150px;background:#1a1e28;border-radius:12px;padding:20px 16px;text-align:center;border:2px solid var(--border);transition:all .2s}}
.pred-item.num1{{border-color:var(--green);background:rgba(63,185,80,.08)}}
.pred-item .rank{{font-size:11px;color:var(--muted);margin-bottom:6px}}
.pred-item .score{{font-size:30px;font-weight:900;margin:4px 0;font-variant-numeric:tabular-nums}}
.pred-item .prob{{font-size:14px;color:var(--gold);font-weight:700}}
.pred-item .note{{font-size:12px;color:var(--muted);margin-top:8px}}
.warn{{color:var(--red);font-size:12px;margin:4px 0}}
.table-section{{margin:40px 0}}
.table-section h2{{color:var(--gold);font-size:22px;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin:16px 0}}
th{{background:var(--card);padding:10px 12px;text-align:left;border-bottom:2px solid var(--gold);font-size:12px;text-transform:uppercase;letter-spacing:1px}}
td{{padding:10px 12px;border-bottom:1px solid var(--border)}}
tr:hover td{{background:rgba(255,255,255,.02)}}
.stats-box{{display:flex;justify-content:center;gap:24px;margin:24px 0;flex-wrap:wrap}}
.stats-box .stat{{background:var(--card);border-radius:12px;padding:20px 28px;text-align:center;border:1px solid var(--border);min-width:120px}}
.stats-box .stat .num{{font-size:28px;font-weight:900}}
.stats-box .stat .label{{font-size:11px;color:var(--muted);margin-top:4px}}
.up{{color:var(--green)}}.down{{color:var(--red)}}
footer{{text-align:center;padding:30px;color:var(--muted);font-size:11px;border-top:1px solid var(--border);margin-top:40px}}
@media(max-width:768px){{.data-grid{{grid-template-columns:1fr}}.pred-item{{min-width:100px}}}}
</style></head><body>
<div class="watermark">陈强</div>
<div class="container">
<header>
<h1>⚽ 世界杯比分<span>预测报告</span></h1>
<div class="time">预测日期: {date_str} | 生成时间: {now}（北京时间） | AI: DeepSeek V4 Pro</div>
</header>"""

    # 每场比赛
    for p in predictions:
        confidence = p.get("confidence", "中")
        conf_color = "var(--green)" if confidence == "高" else "var(--gold)" if confidence == "中" else "var(--red)"
        ai = p.get("ai_analysis", {})
        warnings = p.get("validation", {}).get("warnings", [])
        warn_html = "".join([f'<div class="warn">⚠ {w}</div>' for w in warnings]) if warnings else ""
        a = p.get("stats_a", {})
        b = p.get("stats_b", {})
        a10 = a.get("last10", {})
        b10 = b.get("last10", {})

        html += f"""<div class="match-card">
<h2>{p['team_a']} vs {p['team_b']} <span class="conf">{p.get('date_display','')} 北京时间 | {confidence} | {p.get('stage','小组赛')}</span></h2>
{warn_html}
<div class="data-grid">
<div class="data-item"><div class="label">{p['team_a']} · 近10场战绩</div>
<div class="val">{a10.get('wins',0)}胜 {a10.get('draws',0)}平 {a10.get('losses',0)}负 · 场均进{a10.get('avg_goals_for',0)}/失{a10.get('avg_goals_against',0)}</div></div>
<div class="data-item"><div class="label">{p['team_b']} · 近10场战绩</div>
<div class="val">{b10.get('wins',0)}胜 {b10.get('draws',0)}平 {b10.get('losses',0)}负 · 场均进{b10.get('avg_goals_for',0)}/失{b10.get('avg_goals_against',0)}</div></div>
<div class="data-item"><div class="label">🏅 {p['team_a']} · 世界排名 & 主场数据</div>
<div class="val">#{a.get('rank','?')} · 主场场均进{a.get('home',{}).get('avg_goals_for','?')}/失{a.get('home',{}).get('avg_goals_against','?')}</div></div>
<div class="data-item"><div class="label">🏅 {p['team_b']} · 世界排名 & 客场数据</div>
<div class="val">#{b.get('rank','?')} · 客场场均进{b.get('away',{}).get('avg_goals_for','?')}/失{b.get('away',{}).get('avg_goals_against','?')}</div></div>
</div>
<div class="section-title">🤖 AI 多角度分析</div>
<div class="ai-block">
<div class="row"><strong>战术预判：</strong>{ai.get('tactics',ai.get('style','分析中'))}</div>
<div class="row"><strong>核心对决：</strong>{ai.get('key_duel',ai.get('key_factor','分析中'))}</div>
<div class="row"><strong>胜负手：</strong>{ai.get('key_factor','分析中')}</div>
<div class="row"><strong>风险提示：</strong>{ai.get('risk','分析中')}</div>
<div class="row"><strong>比分区间：</strong>{ai.get('score_range','—')}</div>
</div>
<div class="section-title">🎯 比分预测</div><div class="prediction">"""

        for i, fp in enumerate(p.get("final_predictions", [])):
            cls = "num1" if i == 0 else ""
            html += f"""<div class="pred-item {cls}">
<div class="rank">{i+1}️⃣ 最可能</div>
<div class="score">{fp['score']}</div><div class="prob">{fp['prob']}%</div>
<div class="note">{fp.get('reason','')}</div></div>"""

        html += "</div></div>"

    # 准确性追踪表
    if accuracy_data.get("rows"):
        html += f"""<div class="table-section">
<h2>📊 往期预测准确性追踪</h2>
<div class="stats-box">
<div class="stat"><div class="num">{accuracy_data['total']}</div><div class="label">总预测场次</div></div>
<div class="stat"><div class="num">{accuracy_data['completed']}</div><div class="label">已完赛场次</div></div>
<div class="stat"><div class="num" style="color:var(--green)">{accuracy_data['hits']}</div><div class="label">命中场次</div></div>
<div class="stat"><div class="num" style="color:var(--gold)">{accuracy_data['accuracy']}%</div><div class="label">预测准确率</div></div>
</div>
<table><tr><th>日期</th><th>比赛</th><th>预测TOP3</th><th>实际比分</th><th>命中</th></tr>"""
        for r in accuracy_data["rows"]:
            hit_icon = "✅" if r["hit"] is True else "❌" if r["hit"] is False else "—"
            bf = " 🔄" if r.get("backfill") else ""
            html += f"<tr><td>{r['date']}{bf}</td><td>{r['match']}</td><td>{r['predicted_top3']}</td><td>{r['actual']}</td><td>{hit_icon}</td></tr>"
        html += "</table></div>"

    html += f"""<footer>数据来源: API-FOOTBALL / Football-Data.org / 公开爬虫 | AI: DeepSeek V4 Pro | 仅供参考，不构成投注建议<br>© 陈强的世界杯预测系统 · {date_str}</footer>
</div></body></html>"""
    return html

# 世界杯比分预测系统

全自动世界杯比赛比分预测 + 往期准确性追踪，每天 18:00 发送报告到邮箱。

## 快速开始

```bash
cd worldcup-predict
pip install -r requirements.txt
source ~/.finance-env             # 加载密钥
python3 run.py                    # 手动运行一次
```

## 定时任务

```bash
# 每天 18:00 执行
(crontab -l 2>/dev/null | grep -v worldcup; echo "55 17 * * * /usr/bin/python3 /Users/qiang/Desktop/claude\ code/worldcup-predict/run.py >> /Users/qiang/.worldcup-cron.log 2>&1") | crontab -
```

## 密钥配置

从 `~/.finance-env` 读取（与财经日报共用）：
- `DEEPSEEK_API_KEY` — DeepSeek API密钥
- `SMTP_USER` / `SMTP_PASS` — QQ邮箱SMTP
- `FOOTBALL_DATA_KEY`（可选）— football-data.org API
- `API_FOOTBALL_KEY`（可选）— api-football.com

## 文件结构

```
worldcup-predict/
├── run.py                 # 主入口
├── modules/
│   ├── data_fetcher.py    # 数据采集(多源+缓存)
│   ├── data_validator.py  # 交叉验证
│   ├── predictor.py       # 三层预测模型
│   ├── tracker.py         # 往期追踪
│   ├── report_builder.py  # HTML报告
│   └── mail_sender.py     # 邮件发送
└── data/
    ├── predictions/       # 预测记录JSON
    ├── results/           # 实际结果
    └── cache/             # API缓存
```

## 世界杯结束后

系统会在世界杯结束后自动无数据可预测（fetch_tomorrow_matches返回空），届时删除目录即可：
```bash
rm -rf ~/Desktop/claude\ code/worldcup-predict
crontab -l | grep -v worldcup | crontab -
```

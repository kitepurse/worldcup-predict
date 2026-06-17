"""SMTP 邮件发送"""
import smtplib, os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from datetime import datetime


def send_report(html_content, date_str):
    """发送预测报告邮件"""
    smtp_host = "smtp.qq.com"
    smtp_port = 465
    smtp_user = os.environ.get("SMTP_USER", "55283064@qq.com")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    to_email = "55283064@qq.com"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"⚽ 世界杯比分预测报告 {date_str}（北京时间）"
    msg["From"] = formataddr(["世界杯预测", smtp_user])
    msg["To"] = to_email
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    for attempt in range(3):
        try:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as s:
                s.login(smtp_user, smtp_pass)
                s.sendmail(smtp_user, [to_email], msg.as_string())
            print(f"  ✅ 邮件已发送到 {to_email}", flush=True)
            return True
        except Exception as e:
            if attempt < 2:
                print(f"  SMTP重试({attempt+1}/3): {e}", flush=True)
                import time
                time.sleep(3)
            else:
                print(f"  ❌ 邮件发送失败: {e}", flush=True)
                return False

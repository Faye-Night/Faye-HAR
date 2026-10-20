# -*- coding: utf-8 -*-
import json, sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://www.krene.com"
TOKEN = "<YOUR_TOKEN>"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0"

COMMON = [
    {"name": "Accept", "value": "application/json"},
    {"name": "K-Authorization", "value": "{{Authorization}}"},
    {"name": "krene_user", "value": "{{krene_user}}"},
    {"name": "X-Language", "value": "zh-CN"},
    {"name": "Origin", "value": BASE},
    {"name": "Referer", "value": BASE + "/design/dashboard/home"},
    {"name": "User-Agent", "value": UA},
]

tpl = [
  {
    "comment": "1. 获取活动列表（公开接口，无需登录）：顺带提取每日签到活动的 activityId",
    "request": {
      "method": "GET",
      "url": BASE + "/krene-backend-ts/api/member/activities",
      "headers": list(COMMON),
      "cookies": [],
    },
    "rule": {
      "success_asserts": [
        {"re": "\"success\":true", "from": "content"},
        {"re": "10000001", "from": "content"},
      ],
      "failed_asserts": [
        {"re": "\"code\":500", "from": "content"},
      ],
      "extract_variables": [
        {"name": "dailyActivityId",
         "re": "\"activityId\":\"(\\d+)\",\"name\":\"每日登录领水滴\"",
         "from": "content"},
      ],
    },
  },
  {
    "comment": "2. 查询会员信息：确认今日签到状态与水滴余额（status=claimed 表示今天已签）",
    "request": {
      "method": "GET",
      "url": BASE + "/krene-backend-ts/api/member/info",
      "headers": list(COMMON),
      "cookies": [],
    },
    "rule": {
      "success_asserts": [
        {"re": "\"success\":true", "from": "content"},
      ],
      "failed_asserts": [
        {"re": "Unauthorized", "from": "content"},
        {"re": "\"code\":401", "from": "content"},
      ],
      "extract_variables": [
        {"name": "flowingWater", "re": "\"flowingWater\":(\\d+)", "from": "content"},
        {"name": "registerDays", "re": "\"registerDays\":(\\d+)", "from": "content"},
        {"name": "dailyStatus",
         "re": "\"activityId\":\"10000001\".*?\"status\":\"(\\w+)\"",
         "from": "content"},
      ],
    },
  },
  {
    "comment": "3. 每日签到领水滴（activityId=10000001，每天 50 水滴；已领取也视为成功）",
    "request": {
      "method": "POST",
      "url": BASE + "/krene-backend-ts/api/member/claim-daily-reward",
      "headers": [{"name": "Content-Type", "value": "application/json"}] + list(COMMON),
      "cookies": [],
      "mimeType": "application/json",
      "data": "{\"activityId\":\"{{ dailyActivityId|default(\"10000001\") }}\"}",
    },
    "rule": {
      "success_asserts": [
        {"re": "\"success\":true", "from": "content"},
        {"re": "今日已领取", "from": "content"},
      ],
      "failed_asserts": [
        {"re": "Unauthorized", "from": "content"},
        {"re": "\"code\":401", "from": "content"},
        {"re": "缺少必填参数", "from": "content"},
      ],
      "extract_variables": [
        {"name": "rewardAmount", "re": "\"rewardAmount\":(\\d+)", "from": "content"},
        {"name": "claimMessage", "re": "\"message\":\"([^\"]*)\"", "from": "content"},
      ],
    },
  },
]

# fill the token as the default value of {{Authorization}} so it runs out of the box
for e in tpl:
    for h in e["request"]["headers"]:
        if h["name"] == "K-Authorization":
            h["value"] = '{{Authorization|default("Bearer ' + TOKEN + '")}}'

out = r"D:\Files\Code\HAR\krene-daily-checkin.qd.har"
with open(out, "w", encoding="utf-8") as f:
    json.dump(tpl, f, ensure_ascii=False, indent=2)
print("WROTE", out, os.path.getsize(out), "bytes,", len(tpl), "entries")
print(json.dumps(tpl[2]["request"]["data"], ensure_ascii=False))
print(tpl[2]["request"]["headers"][1]["value"][:70] + " ...")

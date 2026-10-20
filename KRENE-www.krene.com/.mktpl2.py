# -*- coding: utf-8 -*-
"""生成 Krene 每日签到 qd 模板（含 __log__ 水滴变化回报）"""
import json
import sys

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0")

# 真实凭据请勿写进仓库。需要「开箱即用版」时，临时在此填入自己的
# Bearer token 与手机号（或改用环境变量注入），生成完记得改回来。
REAL_TOKEN = "Bearer <YOUR_TOKEN>"
REAL_USER = "<YOUR_PHONE>"

BASE = "https://www.krene.com/krene-backend-ts/api/member"

# __log__ 文案：用 {% set %} + ~ 拼接，避免把含 {{ }} 的文本塞进字符串字面量。
# 注意：delta 必须用「单条 set + 内联三元」，不能用 {% if %} 分支里 set，
# 否则 jinja 的 find_undeclared_variables 会把 delta 当成未声明变量，
# qd 上传模板时会多出一个需要用户手填的变量。
LOG_URL = (
    "api://util/string/replace?r=text&p=%C2%A0&t=%C2%A0&s="
    "{% set wb = waterBefore|default(\"0\")|int %}"
    "{% set wa = waterAfter|default(\"0\")|int %}"
    "{% set d = wa - wb %}"
    "{% set delta = (\"+\" ~ d) if d > 0 else (\"无变化\" if d == 0 else (d|string)) %}"
    "{% set line = \"Krene 每日签到：\" ~ (claimMessage|default(\"签到成功\"))"
    " ~ \"\\n账号：\" ~ krene_user"
    " ~ \"\\n水滴：\" ~ (wb|string) ~ \" → \" ~ (wa|string) ~ \"（\" ~ delta ~ \"）\""
    " ~ \"\\n注册天数：\" ~ (registerDays|default(\"?\")) ~ \" 天\" %}"
    "{{ line|urlencode }}"
)


def auth_headers(token_expr, user_expr, with_content_type=False):
    h = []
    if with_content_type:
        h.append({"name": "Content-Type", "value": "application/json"})
    h += [
        {"name": "Accept", "value": "application/json"},
        {"name": "K-Authorization", "value": token_expr},
        {"name": "krene_user", "value": user_expr},
        {"name": "X-Language", "value": "zh-CN"},
        {"name": "Origin", "value": "https://www.krene.com"},
        {"name": "Referer", "value": "https://www.krene.com/design/dashboard/home"},
        {"name": "User-Agent", "value": UA},
    ]
    return h


def build(real):
    tok = ('{{Authorization|default("%s")}}' % REAL_TOKEN) if real else "{{Authorization}}"
    usr = ('{{krene_user|default("%s")}}' % REAL_USER) if real else "{{krene_user}}"

    return [
        {
            "comment": "1. 获取活动列表（公开接口）：提取每日签到活动的 activityId",
            "request": {
                "method": "GET",
                "url": BASE + "/activities",
                "headers": auth_headers(tok, usr),
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
            "comment": "2. 签到前查询会员信息：记录签到前水滴余额、注册天数、今日签到状态",
            "request": {
                "method": "GET",
                "url": BASE + "/info",
                "headers": auth_headers(tok, usr),
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
                    {"name": "waterBefore", "re": "\"flowingWater\":(\\d+)", "from": "content"},
                    {"name": "registerDays", "re": "\"registerDays\":(\\d+)", "from": "content"},
                    {"name": "dailyStatus",
                     "re": "\"activityId\":\"10000001\".*?\"status\":\"(\\w+)\"",
                     "from": "content"},
                ],
            },
        },
        {
            "comment": "3. 每日签到领水滴（每天 50 水滴；今日已领取也算成功）",
            "request": {
                "method": "POST",
                "url": BASE + "/claim-daily-reward",
                "headers": auth_headers(tok, usr, with_content_type=True),
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
        {
            "comment": "4. 签到后再次查询会员信息：记录签到后水滴余额，用于计算变化",
            "request": {
                "method": "GET",
                "url": BASE + "/info",
                "headers": auth_headers(tok, usr),
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
                    {"name": "waterAfter", "re": "\"flowingWater\":(\\d+)", "from": "content"},
                ],
            },
        },
        {
            "comment": "5. 拼装签到回报文案（写入 __log__，qd 任务日志会显示水滴变化）",
            "request": {
                "method": "GET",
                "url": LOG_URL,
                "headers": [],
                "cookies": [],
            },
            "rule": {
                "success_asserts": [
                    {"re": "200", "from": "status"},
                ],
                "failed_asserts": [],
                "extract_variables": [
                    {"name": "__log__", "re": "[\\s\\S]+", "from": "content"},
                ],
            },
        },
    ]


if __name__ == "__main__":
    for real, path in [
        (True, r"D:\Files\Code\HAR\krene-daily-checkin.qd.har"),
        (False, r"D:\Files\Code\HAR\krene-daily-checkin.qd.sanitized.har"),
    ]:
        tpl = build(real)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tpl, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("written", path, len(tpl), "entries")

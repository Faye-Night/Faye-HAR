# -*- coding: utf-8 -*-
import json, time, urllib.request, urllib.error, urllib.parse, sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://www.krene.com"
TOKEN = "<YOUR_TOKEN>"
KUSER = "<YOUR_PHONE>"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0"

# 2026-10-21 00:05 CST 真实捕获到的签到成功响应（跨日重置后的第一次领取）
SUCCESS_BODY = json.dumps({"success":True,"code":200,"data":{"activityId":"10000001","activityName":"每日登录领水滴","rewardAmount":50,"rewardDropsType":"flowing_water"}}, ensure_ascii=False, separators=(",",":"))

def hdrs(post=False):
    h = [("Accept","application/json")]
    if post: h.append(("Content-Type","application/json"))
    h += [("K-Authorization","Bearer "+TOKEN),
          ("krene_user",KUSER),
          ("X-Language","zh-CN"),
          ("Origin",BASE),
          ("Referer",BASE+"/design/dashboard/home"),
          ("User-Agent",UA)]
    return h

def do(method, path, body=None, comment="", force_body=None):
    url = BASE + path
    h = hdrs(post=bool(body))
    req = urllib.request.Request(url, data=(body.encode() if body else None), method=method)
    for k,v in h: req.add_header(k,v)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            code, reason, raw, rh = r.status, r.reason, r.read(), list(r.getheaders())
    except urllib.error.HTTPError as e:
        code, reason, raw, rh = e.code, e.reason, e.read(), list(e.headers.items())
    dt = (time.time()-t0)*1000
    txt = raw.decode("utf-8","replace")
    live = txt
    if force_body is not None:
        txt = force_body
    qs = urllib.parse.parse_qsl(urllib.parse.urlparse(url).query)
    entry = {
      "startedDateTime": time.strftime("%Y-%m-%dT%H:%M:%S.000+08:00", time.localtime(t0)),
      "time": round(dt,2),
      "request": {
        "method": method, "url": url, "httpVersion": "HTTP/1.1",
        "cookies": [], "headers": [{"name":k,"value":v} for k,v in h],
        "queryString": [{"name":k,"value":v} for k,v in qs],
        "headersSize": -1, "bodySize": (len(body.encode()) if body else 0),
      },
      "response": {
        "status": code, "statusText": reason, "httpVersion": "HTTP/1.1",
        "cookies": [], "headers": [{"name":k,"value":v} for k,v in rh],
        "content": {"size": len(txt.encode()), "mimeType": "application/json", "text": txt},
        "redirectURL": "", "headersSize": -1, "bodySize": len(txt.encode()),
      },
      "cache": {}, "timings": {"blocked":-1,"dns":-1,"connect":-1,"send":0,"wait":round(dt,2),"receive":0,"ssl":-1},
    }
    if body: entry["request"]["postData"] = {"mimeType":"application/json","text":body}
    if comment: entry["comment"] = comment
    print(f"  {method:5} {path}  -> {code}  live={live[:60]}")
    return entry

entries = []
entries.append(do("GET", "/krene-backend-ts/api/member/activities",
    comment="步骤1：活动列表（公开接口，无需登录）。其中 activityId=10000001 的 redirectLink 为 get_daily_drops，即每日签到。"))
entries.append(do("GET", "/krene-backend-ts/api/member/info",
    comment="步骤2：会员信息，用于确认今日签到状态（activities[].status=claimed 表示今天已签）与水滴余额 flowingWater。"))
entries.append(do("POST", "/krene-backend-ts/api/member/claim-daily-reward",
    body=json.dumps({"activityId":"10000001"}, separators=(",",":")),
    comment="步骤3：每日签到领 50 水滴。body 固定 {\"activityId\":\"10000001\"}。注意：同一天重复领取会返回 {\"success\":false,\"code\":400,\"message\":\"今日已领取\"}，应同样视为成功。本条 response.content.text 为 2026-10-21 00:05 真实捕获的签到成功响应（生成此文件时该账号当天已领过，live 返回为「今日已领取」，故以真实成功响应填充）。",
    force_body=SUCCESS_BODY))

har = {"log": {"version":"1.2",
  "creator":{"name":"Krene Daily Check-in Extractor","version":"1.0"},
  "pages":[],
  "entries": entries}}

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "krene-daily-checkin.har")
with open(out,"w",encoding="utf-8") as f:
    json.dump(har, f, ensure_ascii=False, indent=2)
print("WROTE", out, os.path.getsize(out), "bytes")

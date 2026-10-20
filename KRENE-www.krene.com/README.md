# Krene 每日签到 · qd（qiandao.today）模板

Krene（`https://www.krene.com`）的每日签到任务：**每日登录领水滴**，每天 50 水滴。
服务端按自然日 **00:00（CST）** 重置，每日可领一次。

本模板用于 [qd（qiandao.today）](https://github.com/qd-today/qd)，导入后填两个变量即可定时自动签到，并在任务日志里看到水滴变化。

---

## 文件说明

| 文件 | 格式 | 请求数 | 说明 |
| --- | --- | --- | --- |
| `krene-daily-checkin.qd.har` | qd 数组格式 | 5 | **推荐使用**。包含完整签到链路 + 水滴变化日志 |
| `krene-daily-checkin.har` | 标准 HAR 1.2 | 3 | 真实抓包记录，可导入 qd，也可用于分析/二次开发 |

两个文件里的账号凭据都已替换为占位符（`<YOUR_TOKEN>` / `<YOUR_PHONE>` / `<YOUR_EMAIL>` / `<YOUR_USER_UUID>`），**不含任何人的真实信息**，可以自由分发。

> 两份文件功能有差异：标准 HAR 是抓包得到的原始 3 条请求，签到能成功但日志里没有水滴变化；`.qd.har` 才是完整的 5 条版本。

---

## 快速开始

1. 登录 qd → **新建任务** → 上传 `krene-daily-checkin.qd.har`
2. 在变量里填 **`Authorization`** 和 **`krene_user`**（见下节，只有这两个要填）
3. 设置定时（建议 **每天 00:10 之后**），保存

搞定。之后每天会自动签到，日志里能看到水滴变化。

---

## 需要填写的变量

qd 上传模板后会自动识别出两个必填变量：

| 变量 | 是否必填 | 填什么 |
| --- | --- | --- |
| `Authorization` | ✅ 必填 | `Bearer ` + 你的 token（**注意有 `Bearer ` 前缀和一个空格**） |
| `krene_user` | ✅ 必填 | 你的手机号，例如 `13800138000` |
| `dailyActivityId` | ❌ **不用填** | 模板里已带默认值 `10000001`，且第 1 条请求会从服务端响应里重新提取真实值 |
| `waterBefore` / `waterAfter` / `claimMessage` / `registerDays` | ❌ 不用填 | 全部由模板运行时自动提取 |

**除 `Authorization` 和 `krene_user` 外，其他变量都不用手填**，qd 会自动用默认值填充并在执行过程中更新。

### 怎么获取 `Authorization`

1. 用浏览器打开 `https://www.krene.com/design/dashboard/home` 并确认已登录
2. 按 `F12` 打开开发者工具，切到 **Console（控制台）**
3. 执行：

```js
JSON.parse(localStorage.getItem("userInfo")).token
```

4. 复制输出的字符串（一长串以 `eyJ` 开头、用两个 `.` 分成三段的字符），前面加上 `Bearer ` 再填入 qd

也可以在 **Application（应用）→ Local Storage → https://www.krene.com** 里找到 `userInfo` 这一项，展开后复制 `token` 字段的值。

### 怎么获取 `krene_user`

同一个 `userInfo` 对象里的 `userName` 字段，就是你的手机号：

```js
JSON.parse(localStorage.getItem("userInfo")).userName
```

---

## 签到链路（5 个请求）

| # | 请求 | 作用 |
| --- | --- | --- |
| 1 | `GET /krene-backend-ts/api/member/activities` | 公开接口，取每日签到活动的 `activityId` |
| 2 | `GET /krene-backend-ts/api/member/info` | 记录**签到前**的 `flowingWater`、`registerDays`、今日状态 |
| 3 | `POST /krene-backend-ts/api/member/claim-daily-reward` | **真正的签到**，body `{"activityId":"10000001"}` |
| 4 | `GET /krene-backend-ts/api/member/info` | 记录**签到后**的 `flowingWater` |
| 5 | `GET api://util/string/replace?...` | 用 jinja 拼装回报文案写入 `__log__`，qd 日志显示水滴变化 |

第 5 条是 qd 自带的本地工具端点（`api://` 会被 qd 解析为 `http://localhost:<qd端口>`），不访问外网、不需要认证，用来把「水滴 50 → 100」这类信息写进任务日志。

---

## 任务日志示例

签到成功：

```
Krene 每日签到：签到成功
账号：13800138000
水滴：50 → 100（+50）
注册天数：3 天
```

今日已签过（重复执行，不算失败）：

```
Krene 每日签到：今日已领取
账号：13800138000
水滴：100 → 100（无变化）
注册天数：3 天
```

---

## 响应与判定

| 场景 | 响应体 |
| --- | --- |
| 领取成功 | `{"success":true,"code":200,"data":{"activityId":"10000001","activityName":"每日登录领水滴","rewardAmount":50,"rewardDropsType":"flowing_water"}}` |
| 今日已领 | `{"success":false,"code":400,"message":"今日已领取"}` |
| token 失效 | `{"success":false,"code":401,"message":"Unauthorized"}` |

模板的成功/失败断言：

- 第 1、2、4 条 — 成功：响应含 `"success":true`；失败：含 `Unauthorized` 或 `"code":401`
- 第 3 条 — 成功：含 `"success":true` **或** `今日已领取`（幂等，重复执行不算失败）；失败：含 `Unauthorized` / `"code":401` / `缺少必填参数`
- 第 5 条 — 成功：HTTP 状态码 `200`

> ⚠️ **重要**：Krene 的鉴权失败返回的是 **HTTP 200 + 业务错误码 401**，不是 HTTP 401。所以断言必须基于响应体内容，只看状态码会误判成成功。

---

## 常见问题

**Q：任务显示失败，日志是 `Unauthorized` / `code 401`？**
token 失效了。重新按上面「怎么获取 `Authorization`」的步骤取一个新 token 填进 qd。

**Q：token 多久过期？**
Krene 的 token（JWT）有效期 **30 天**。过期后 qd 会报 401，换新 token 即可。

**Q：日志显示「今日已领取」，是失败了吗？**
不是。说明今天已经签过（可能是你手动签的，或者定时任务跑了两次）。这种情况模板判定为成功，水滴显示「无变化」。

**Q：定时设在几点？**
服务端 00:00（CST）重置，建议设在 **00:10 之后**，避开跨日瞬间。

**Q：`dailyActivityId` 到底要不要填？**
不用。模板里写的是 `{{ dailyActivityId|default("10000001") }}`，qd 会自动带上默认值 `10000001`；同时第 1 条请求还会从活动列表接口里提取真实值覆盖它，双保险。

**Q：能领其他活动吗？**
本模板只做每日登录领水滴。账号里另外两个活动（「关注官号领水滴」「邀请新用户」）需要人工关注 + 后台审核 / 真实邀请注册，无法脚本化，未包含在内。

---

## 已验证

用 qd 官方引擎（`libs/fetcher.py` 的 `Fetcher.do_fetch`）跑过以下场景：

| 场景 | 方式 | 结果 |
| --- | --- | --- |
| 正常签到 | 本地 mock（未签到 → 领取 +50） | ✅ 5 条全过，日志 `水滴：0 → 50（+50）` |
| 今日已领 | 本地 mock（返回「今日已领取」） | ✅ 5 条全过，日志 `水滴：50 → 50（无变化）` |
| token 失效 | 本地 mock（返回 code 401） | ✅ 第 2 条被失败断言正确拦下 |
| 真实网络 | 打真 `www.krene.com` | ✅ 5 条全过，日志正常生成 |
| 真实 qd 部署 | 自建 qd 容器实际执行 | ✅ 签到成功，水滴 0 → 50，接口复查余额与活动状态一致 |

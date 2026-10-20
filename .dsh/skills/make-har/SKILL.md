---
name: make-har
description: 制作 qd（qiandao.today）可用的签到 HAR 模板，并按仓库规范搭建目录结构。当需要为某网站/APP 抓取或逆向签到请求、编写 qd 模板（success_asserts / extract_variables / __log__ 回报）、在本地验证模板、或新建 {网站名}-{网址} 目录时使用。Also for qd HAR authoring, sign-in API reverse engineering, and HAR template validation.
---

# 制作 qd 签到 HAR

目标产物：一个能被 qd 直接上传运行的 `.qd.har`（JSON 数组格式），外加同目录的生成脚本与说明文档。

**核心原则：不要凭猜测写模板。** 每一条断言、每一个正则都必须对照真实响应体验证过。签到接口通常一天只能成功一次，一旦浪费掉当天额度就再也抓不到 `success:true`，所以要先想清楚再发请求。

## 阶段一：侦察 —— 能抓包还是必须逆向

先判断浏览器是否可被控制，这决定后面走哪条路。

```powershell
# 是否有 CDP 调试端口
Get-CimInstance Win32_Process -Filter "Name='msedge.exe' OR Name='chrome.exe'" |
  Select-Object ProcessId, CommandLine | Where-Object { $_.CommandLine -match 'remote-debugging-port' }
```

- **有 `--remote-debugging-port=9222`** → 可连 CDP，用 `Network.getAllCookies` / `Network.enable` 直接抓真实请求，最省事。
- **没有** → CDP 不可用。注意：`Get-Process msedge` 拿到的 PID 往往是 **renderer 子进程**，不是浏览器本体，控制不了它。监听端口也未必是 DevTools（连 `/json/version` 会拒连）。

用户说"签到已完成"时不要放弃：先确认服务端是否按**自然日**重置。很多站点的每日奖励在 00:00 后立刻可再领，跨过零点就能抓到一次真实的 `success:true`。

详见 [references/recon.md](references/recon.md)（CDP 探测、SPA bundle 逆向、浏览器锁住数据库时如何读凭据）。

## 阶段二：拿到签到请求的真实结构

必须确认四件事，缺一不可：

| 要素 | 怎么确认 |
| --- | --- |
| 端点 URL 与 method | bundle 里 grep 接口前缀，或抓包 |
| 认证 header 名称与格式 | 逆向请求封装函数（常见 `K-Authorization: Bearer xxx`） |
| 请求体字段 | 看调用处的对象字面量 |
| **成功 / 失败的响应文本** | **必须实际请求一次**，逐字记录 |

最后一项最容易翻车：很多接口**鉴权失败也返回 HTTP 200**，只在 body 里放 `{"success":false,"code":401}`。只看状态码会把失效 token 当成功。

区分失败类型时，把无 token / 错 token / 参数缺失 / 今日已领 各跑一次，记下各自 body 的差异文本，后面写断言全靠这些字面量。

## 阶段三：写 qd 模板

模板是**顶层 JSON 数组**，每个元素：

```json
{
  "comment": "人类可读的步骤说明",
  "request": {
    "method": "POST",
    "url": "https://example.com/api/claim",
    "headers": [{ "name": "K-Authorization", "value": "{{Authorization}}" }],
    "cookies": [],
    "mimeType": "application/json",
    "data": "{\"activityId\":\"{{ dailyActivityId|default(\"10000001\") }}\"}"
  },
  "rule": {
    "success_asserts": [{ "re": "\"success\":true", "from": "content" }],
    "failed_asserts": [{ "re": "Unauthorized", "from": "content" }],
    "extract_variables": [{ "name": "rewardAmount", "re": "\"rewardAmount\":(\\d+)", "from": "content" }]
  }
}
```

推荐的 5 段式链路（让任务日志能报出"变化"而不只是"成功"）：

1. 取配置/活动列表（往往免认证）→ 提取目标 ID
2. 执行前查询状态 → 记录「前」值
3. 执行签到
4. 执行后再次查询 → 记录「后」值
5. `api://util/string/replace` 拼装文案写入 `__log__`

**`__log__` 是唯一能进 qd 任务日志的通道**：某条请求的 `extract_variables` 里 `name` 写 `__log__`，它的值就是日志正文。第 5 条用 qd 自带的 `api://util/string/replace?r=text&p=&t=&s=<urlencode 文案>`，把整段文案 URL 编码后塞进 `s` 参数，`extract_variables` 用 `{"name":"__log__","re":"[\\s\\S]+","from":"content"}` 接住。

### 变量：让用户少填

- `{{ x|default("v") }}` → qd 上传时**自动**把 `v` 写进 init_env，用户不用填。
- `{{ x }}`（无 default）→ 必须用户手填。
- 想让用户只填 token，就把能推导出来的值全加上 `|default()`，并且靠上一步 `extract_variables` 覆盖它——双重保险。

### 断言：优先级与常见坑

- `success_asserts` **任一命中即判成功**（首个命中就 break）。
- `failed_asserts` **优先级更高**，任一命中立刻判失败。所以别把 `"code":401` 之类只写进 success 的排除项，要显式写进 failed。
- 「今日已领取」通常应算**成功**（说明签到动作有效），放进 `success_asserts`；token 失效放进 `failed_asserts`。
- 正则里的 `"success":true` 依赖**紧凑 JSON**（无空格）。用 mock 服务器验证时务必 `json.dumps(..., separators=(",", ":"))`，否则会莫名失败。
- `extract_variables` 的 `re` 支持 `/pattern/flags`（flags 限 `gimsu`）；**用捕获组**比用整体匹配稳，无捕获组时取 `group(0)`。

### jinja 陷阱（踩过，务必避开）

- **不要把含 `{{ }}` 的文本塞进字符串字面量**：`{{ ("账号：{{ x }}")|urlencode }}` 会 `TemplateSyntaxError: expected token ')'`。改用 `{% set %}` + `~` 拼接。
- **不要用 `{% if %}...{% set v = ... %}...{% endif %}` 分支赋值**：qd 用 `jinja2.meta.find_undeclared_variables` 抽变量，分支里 set 的 `v` 会被当成未声明变量，导致上传时凭空多出一个必填项。改成单条内联三元：`{% set v = ("+" ~ d) if d > 0 else "无变化" %}`。
- `add` / `sub` 过滤器返回 6 位小数字符串（`"50.000000"`），要接 `|int`。
- **url 和 data 不做中文引号转义**，header 和 cookie 的 value 会过 `quote_chinese`。文案放 URL 查询串时必须自己 `|urlencode`。

引擎细节（断言求值顺序、过滤器清单、`api://` 解析、日志落库路径）见 [references/qd-engine.md](references/qd-engine.md)。

## 阶段四：本地验证

**不要在真实站点上调试模板。** 本地起一个 mock 服务器扮演目标 API，把模板 URL 里的域名替换成 `http://localhost:<qd端口>` 后跑 qd 官方引擎。

`api://` 会被解析成 `http://<bind>:<port>`（`0.0.0.0` → `localhost`），所以 mock 要监听**和 qd 配置相同的端口**，第 5 条才能落到 mock 上。

至少要跑通四个场景：

| 场景 | 期望 |
| --- | --- |
| 正常执行 | 全部通过，`__log__` 显示正确的变化量 |
| 今日已完成（幂等） | 仍判成功，`__log__` 显示「无变化」 |
| 凭据失效 | 在查询/执行那一步被 `failed_asserts` 拦下 |
| 真实网络 | 打真实域名跑一遍，确认断言与真实响应体匹配 |

用 qd 的 `Fetcher().do_fetch(tpl, env)` 跑，`env` 用空变量环境模拟真实 qd 的渲染路径。四个场景全绿再交付。

## 阶段五：落盘

目录位置与命名规则以仓库根 [AGENTS.md](../../../AGENTS.md) 为准，**此处不重复**——那份文件是强制规范，本 skill 只管"怎么做"。落盘前先读它。

下面只讲 skill 侧的做法。每个站点目录建议包含：

```
{网站名}-{网址}/
├── readme_{网站名}.md          # 变量怎么填、请求链路、响应判定、重制步骤
├── *.qd.har                    # qd 模板（推荐用户上传这个）
├── *.har                       # 标准 HAR 1.2（分析/调试用，可选）
├── make_qd_har.py              # 生成 qd 模板的脚本
└── make_har.py                 # 生成标准 HAR 的脚本（可选）
```

**脚本而不是手写 JSON**：模板里的断言正则会反复调整，用脚本生成才能保证可复现、可审查、可 diff。脚本里凭据一律用占位符常量，输出路径用 `os.path.dirname(os.path.abspath(__file__))` 而不是硬编码绝对路径。

**凭据处理**：脱敏要求见 AGENTS.md 规则三。skill 侧的额外要求是——**生成脚本也不要默认写出含真实凭据的版本**，`build(real=True)` 这类调试分支保留但不落盘；`readme_{网站名}.md` 里必须写清每个变量怎么获取（如浏览器控制台 `JSON.parse(localStorage.getItem("userInfo")).token`）。

## 交付前检查

- [ ] 四类响应（成功 / 幂等 / 失效 / 参数错误）的断言都对照过真实 body
- [ ] 本地四场景全过，`__log__` 文案正确
- [ ] 变量清单只剩用户真正必须填的（`get_variables` 输出核对）
- [ ] 真实网络跑通过一次
- [ ] 全仓敏感串扫描为 0
- [ ] 目录命名、说明文档命名符合 AGENTS.md

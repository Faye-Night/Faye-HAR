# 侦察参考：CDP 探测、SPA 逆向、浏览器锁库时的凭据提取

## 一、判断浏览器能否被控制

### 检查调试端口

```powershell
Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" |
  Select-Object ProcessId, ParentProcessId, CommandLine |
  Where-Object { $_.CommandLine -match 'remote-debugging-port' }
```

有输出 → CDP 可用，直接用 `http://127.0.0.1:<port>/json/list` 拿 target，走 `Network.enable` 抓包。

无输出 → 再确认端口是否真死了：

```powershell
foreach ($p in 9222,9223,9229) {
  try { Invoke-RestMethod "http://127.0.0.1:$p/json/version" -TimeoutSec 2 } catch { "$p 无响应" }
}
```

`/json/version` 拒连 = 不是 DevTools 端口。仅凭「msedge 进程在监听某端口」不能推断 CDP 可用。

### PID 陷阱

`Get-Process msedge` 或用户给的 PID 常常是 **renderer / gpu / network service 子进程**。判断方法：

```powershell
Get-CimInstance Win32_Process -Filter "ProcessId=34876" |
  Select-Object ProcessId, ParentProcessId, CommandLine
```

若命令行含 `--type=renderer` 或 `--type=utility`，它就不是浏览器本体，无法通过它控制浏览器。往上找 `ParentProcessId` 直到命令行不含 `--type=` 的那个才是主进程。

### 没有 CDP 时的出路

1. 让用户手动开：关闭 Edge，用 `msedge.exe --remote-debugging-port=9222 --user-data-dir=<新目录>` 启动（注意新 user-data-dir 会丢登录态，需要重新登录）。
2. 让用户从控制台取值：`JSON.parse(localStorage.getItem("userInfo")).token` 之类。
3. 离线读浏览器存储（见第三节）。

## 二、SPA 逆向：从 bundle 里挖接口

站点是 CRA / Vite SPA 时，直接 GET 深层路由会 404（服务端无该路径），必须走浏览器渲染或直接读 JS。

```powershell
# 1. 拿 HTML，找主 bundle 与构建版本
$h = Invoke-WebRequest "https://example.com/app/" -UseBasicParsing
$h.Content | Select-String -Pattern 'static/js/main\.[a-f0-9]+\.js|<meta name="build-version"'

# 2. 下载 bundle
Invoke-WebRequest "https://example.com/app/static/js/main.<hash>.js" -OutFile ".main.js"

# 3. 挖 API 前缀与端点
Select-String -Path ".main.js" -Pattern '/api/[a-zA-Z0-9/_-]+' -AllMatches |
  ForEach-Object { $_.Matches.Value } | Sort-Object -Unique
```

### 定位请求封装函数

签到请求一般走统一的 fetch 封装，找到它就能一次性拿到 header 结构：

```powershell
Select-String -Path ".main.js" -Pattern 'K-Authorization|Authorization.*Bearer|Content-Type.*application/json' |
  Select-Object -First 5 LineNumber, Line
```

典型封装形态（真实案例）：

```js
async function ce(e, t, n) {
  const o = n ? e : "".concat(re).concat(e)
  return fetch(o, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "K-Authorization": "Bearer ".concat(oe()),
      krene_user: ie(),
      "X-Language": b(),
    },
    body: JSON.stringify(t),
  })
}
```

然后追 `oe()` / `ie()` 的定义，就知道 token 和用户标识从哪来：

```js
oe = () => { const e = v("userInfo"), t = e ? JSON.parse(e) : null; return t ? t.token : "" }
ie = () => { const e = v("userInfo"), t = e ? JSON.parse(e) : null; return t ? encodeURIComponent(t.userName) : "" }
```

### 定位签到调用点

```powershell
Select-String -Path ".main.js" -Pattern 'claim|checkin|signin|daily|reward' -AllMatches |
  ForEach-Object { "$($_.LineNumber): $($_.Line.Substring(0, [Math]::Min(300, $_.Line.Length)))" }
```

真实案例的判定分支（能直接看出状态枚举与请求体）：

```js
if ("get_daily_drops" === e) {
  if ("claimable" !== r) return
  const t = { activityId: e }
  await ce("/krene-backend-ts/api/member/claim-daily-reward", t, true)
}
// 状态枚举：{ claimable: 0, pending: 1, claimed: 2 }
```

UI 文案也能佐证语义：`"daily_drops_description":"每日打开应用获取 50 水滴"` → 每日签到 = 领 50 水滴。

## 三、浏览器锁住数据库时如何取凭据

Edge/Chrome 运行时会独占 `Cookies` SQLite 文件。以下**全部会失败**，别浪费时间：

| 尝试 | 报错 |
| --- | --- |
| `[System.IO.File]::Open(...,'Read','ReadWrite')` | The process cannot access the file because it is being used by another process |
| `esentutl /y` | `JET_errFileAccessDenied (-1032)` |
| `robocopy /B` | You do not have the Backup and Restore Files user rights（非管理员） |
| sqlite `mode=ro&immutable=1` | unable to open database file |

**但 `Local Storage\leveldb` 不锁**，可以整目录复制后离线读：

```powershell
Copy-Item "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Local Storage\leveldb" -Destination ".ls" -Recurse
```

leveldb 里键是 `_<origin>\x00\x01<key>` 编码，值可能是 UTF-16LE 混杂二进制，**不要按 UTF-16 解码**，直接对原始字节做正则：

```powershell
# 找 JWT
$bytes = [System.IO.File]::ReadAllBytes(".ls\012829.ldb")
$text = [System.Text.Encoding]::Latin1.GetString($bytes)
[regex]::Matches($text, 'eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}') |
  ForEach-Object { $_.Value }
```

按已知键名逐文件计数能快速缩小范围：

```powershell
foreach ($f in Get-ChildItem ".ls\*.ldb") {
  $t = [System.Text.Encoding]::Latin1.GetString([System.IO.File]::ReadAllBytes($f.FullName))
  $hits = @()
  foreach ($k in 'userInfo','token','krene','VisitorId','__sak') {
    if ($t.Contains($k)) { $hits += $k }
  }
  if ($hits) { "$($f.Name): $($hits -join ', ')" }
}
```

注意：**不同站点的 JWT 会同时躺在多个 `.ldb` 文件里**，必须靠键名或上下文（`userInfo` 的 JSON 值里 `"token":"..."`）确认归属，不能见到 JWT 就认。

JWT payload 可直接 base64url 解码确认身份与有效期：

```powershell
$jwt = "eyJ..."
$p = $jwt.Split('.')[1].Replace('-','+').Replace('_','/')
$p += '=' * ((4 - $p.Length % 4) % 4)
[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($p))
```

关注 `exp` 字段——token 过期后模板必然失效，要在说明文档里写清有效期和续期方式。

## 四、接口免认证探测

确定端点后，逐个试无 token / 空 token / 错 token，记下响应差异：

```powershell
$urls = @(
  "https://example.com/api/activities",
  "https://example.com/api/info",
  "https://example.com/api/claim"
)
foreach ($u in $urls) {
  try {
    $r = Invoke-WebRequest $u -Method GET -TimeoutSec 15 -ErrorAction Stop
    "[$($r.StatusCode)] $u => $($r.Content.Substring(0,[Math]::Min(200,$r.Content.Length)))"
  } catch { "[ERR] $u => $($_.Exception.Message)" }
}
```

重点看**HTTP 状态码与 body 是否一致**。大量接口鉴权失败也返回 200，此时断言只能基于 body 文本。

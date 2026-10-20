# qd 引擎行为参考

基于 qd 官方仓库 `libs/fetcher.py`、`libs/utils.py`、`web/handlers/har.py` 逐行确认。行号可能随版本漂移，行为相对稳定。

## 请求构建（`libs/fetcher.py`）

- `:120` `headers = dict((e["name"], e["value"]) for e in request["headers"])` —— 同名 header 后写覆盖前写，不要写重复名。
- `:121` cookies 同样转 dict。
- `:122-126` `data = request.get("data")`；`method == "GET"` 时**强制** `data = None`；POST 取 `request.get("data", "")`。
- `:117-118` `api://` 协议：

  ```python
  if str(url).startswith("api://"):
      url = str(url).replace("api:/", local_host, 1)
  ```

  `local_host` 定义在 `:44`：

  ```python
  local_host = f"http://{config.bind}:{config.port}".replace("0.0.0.0", "localhost")
  ```

  所以 `api://util/string/replace?...` → `http://localhost:<port>/util/string/replace?...`，由 qd 自身 web 服务处理，**无需认证**。

## 渲染（`libs/fetcher.py:61-97`）

```python
self.jinja_env.from_string(...).render(_cookies=_cookies, **env)
```

依次渲染 `method` / `url` / `headers[name,value]` / `cookies` / `data`。

- header 与 cookie 的 value 会过 `utils.quote_chinese`（中文引号转义）。
- **url 与 data 不做**该转义 → 文案放 URL 查询串时必须自己 `|urlencode`。

## 断言求值（`libs/fetcher.py:324 run_rule`）

```python
:399-408  success_asserts：任一命中即 break，判 success=True
          若全部未命中且 success_asserts 非空 → success=False
:410-415  failed_asserts：任一命中 → success=False 并 break
```

**优先级**：`failed_asserts` 高于 `success_asserts`。同一条文本既命中 success 又命中 failed 时判失败。

`from` 支持：`content` / `status` / `header` / `header-<name>`。

## 变量提取（`libs/fetcher.py:429-462`）

- `re` 支持 `/pattern/flags` 写法，flags ∈ `gimsu`。
- `g` 模式走 `re.findall`，其余用 `re.search`。
- **有捕获组时取 `groups()[0]`，否则取 `group(0)`** → 提取一律用捕获组。

## 模板格式

顶层是 **JSON 数组**（不是标准 HAR 对象）：

```json
[{"comment": "...", "request": {...}, "rule": {...}}]
```

`tpl2har()`（`libs/fetcher.py:467-541`）把该数组转标准 HAR，`mimeType` 从 `request["mimeType"]` 读。

前端上传 `web/static/coffee/har/upload_ctrl.coffee`：JSON 里有 `.log` 走 `analysis.analyze`，否则走 `utils.tpl2har(data)` → **两种格式都能吃**。

## 变量发现（`web/handlers/har.py:362-459`）

```python
meta.find_undeclared_variables(jinja_env.parse(...))
```

- 扫描出所有未声明变量 → 成为用户手填项。
- 额外扫描 `Filter` 节点名为 `default` 的 `{{ x|default("v") }}` → 把 `v` 写进 `init_env`（自动填，用户不用管）。

**推论**：`{% if %}...{% set v = ... %}...{% endif %}` 分支赋值会让 `v` 被判定为未声明变量。必须改成单条内联三元。

## jinja 可用过滤器（`libs/utils.py:895-956` `jinja_globals`）

```
int float bool utf8 unicode urlencode quote_chinese format
b64encode b64decode md5 sha1 timestamp date_time
is_num add sub multiply divide
regex_replace regex_search regex_findall
ternary random mandatory type_debug
```

inner globals：`dict` `lipsum` `range`（`libs/utils.py:958`）。

**注意** `add` / `sub`（`libs/utils.py:729/742`）返回 `f"{result:f}"` → 6 位小数字符串（如 `"50.000000"`），需接 `|int`。

## `__log__` 落库链

```python
worker.py:248  await self.db.tasklog.add(task['id'], success=True,
                    msg=new_env['variables'].get('__log__'), sql_session=sql_session)
worker.py:261  content = new_env['variables'].get('__log__')
qd.py:122      CLI 同样读 __log__
```

失败分支：`tasklog.add(..., False, msg=str(e))`（即 failed_asserts 命中的文本）。

**结论**：想让任务日志显示自定义内容，必须有一条请求把文案写进环境变量 `__log__`。

## 官方模板的两种 `__log__` 写法

**写法 A**（萌幻之乡模板，推荐——不依赖 JSON 转义）：

```
GET api://util/string/replace?r=text&p=%C2%A0&t=%C2%A0&s=<urlencode 文案>
rule: {"success_asserts":[{"re":"200","from":"status"}],
       "failed_asserts":[],
       "extract_variables":[{"name":"__log__","re":".+","from":"content"}]}
```

**写法 B**（2Libra 模板）：

```
POST api://util/unicode
data: html_unescape=false&content=...
extract: {"name":"__log__","re":"\"转换后\": \"(.*)\"","from":"content"}
```

## qd 内置 util 端点（`web/handlers/util.py`，均无需认证）

| 路由 | 参数 | 返回 |
| --- | --- | --- |
| `/util/string/replace` | `s` `p` `t` `r` | `r=="text"` 时返回 `html.escape(re.sub(p, t, s))` 纯文本；否则 JSON `{"原始字符串","处理后字符串","状态"}` |
| `/util/unicode` | `content` `html_unescape` | JSON `{"转换后":..., "状态":"200"}` |
| `/util/timestamp` | — | 北京时间/时间戳 JSON |
| `/util/regex` `/util/urldecode` `/util/gb2312` `/util/rsa` `/util/dddd/*` | — | 各自处理 |

注意 `r=text` 时会 `html.escape` 转义 `& < > " '`——文案里含这些字符会被转义，属正常现象。

## `fetch()` 调用形状（`libs/fetcher.py:672-718`）

```python
obj = {
  "request": {"method","url","headers":[{"name","value"}],"cookies":[],"data"},
  "rule": {"success_asserts","failed_asserts","extract_variables"},
  "env": {"variables": {...}, "session": {...}},
}
result = await Fetcher().fetch(obj)
# → {"success", "response", "env", "msg"}
```

`do_fetch(tpl, env)`（`:804`）循环执行整个 tpl，任一 entry 失败即 raise。

## 本地验证脚手架

```python
from libs.fetcher import Fetcher

tpl = json.load(open("xxx.qd.har", encoding="utf-8"))
# 把真实域名替换成 mock 地址
for e in tpl:
    e["request"]["url"] = e["request"]["url"].replace("https://real.site", "http://localhost:8923")

env = {"variables": {}, "session": {}}
result = await Fetcher().do_fetch(tpl, env)
print(result["env"]["variables"].get("__log__"))
```

mock 服务器必须监听 **qd 配置里的同一个端口**（`config.port`），否则 `api://` 解析不到。`config.py:19-22`：

```python
bind = os.getenv("BIND", "0.0.0.0")
port = int(os.getenv("PORT", "8923"))
```

mock 返回 JSON 必须用 `json.dumps(..., separators=(",", ":"))` 输出紧凑格式，否则 `"success":true` 这类断言匹配不上。

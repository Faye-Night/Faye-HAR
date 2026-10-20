# Faye-HAR

一个签到脚本（HAR）集合仓库，主要面向 [qd（qiandao.today）](https://github.com/qd-today/qd)。

每个网站占一个独立子目录，目录内包含该站点的 HAR 文件、配套生成脚本与说明文档。

## HAR 列表

| 序号 | 网站 | 网址 | HAR-qd | HAR |
| --- | --- | --- | --- | --- |
| 1 | KRENE | <https://www.krene.com> | [krene-daily-checkin.qd.har](KRENE-www.krene.com/krene-daily-checkin.qd.har) | [krene-daily-checkin.har](KRENE-www.krene.com/krene-daily-checkin.har) |

> **推荐使用 `HAR-qd` 列的文件。**
>
> `HAR-qd` 是 qd 专用格式，包含完整的签到链路、成功/失败断言、变量提取，以及任务日志文案；上传后填好变量即可直接运行。
> `HAR` 列是标准 HAR 1.2 抓包记录，请求条数较少，主要用于分析、调试或二次开发。

## 说明文档

各站点目录下均有独立说明文档，命名为 `readme_网站名.md`，包含该站点的变量填写方式、请求链路、响应判定与常见问题。使用某个 HAR 之前请先阅读对应目录的说明。

- [KRENE](KRENE-www.krene.com/readme_KRENE.md)

## 目录结构

```
.
├── README.md                      # 本文件：总目录
├── AGENTS.md                      # 项目级规则
├── .dsh/skills/make-har/          # 项目级 skill：制作 HAR 的完整流程
└── {网站名}-{网址}/                # 每个站点一个目录
    ├── readme_{网站名}.md          # 该站点的使用说明
    ├── *.qd.har                   # qd 专用模板（推荐）
    └── *.har                      # 标准 HAR 抓包记录
```

## 制作新 HAR

本仓库自带项目级 skill `make-har`（位于 `.dsh/skills/make-har/`），在 DSH 会话中可直接调用，涵盖：

- 侦察阶段：CDP 探测、SPA bundle 逆向、浏览器锁库时如何提取凭据
- 模板编写：qd 数组格式、断言优先级、变量 `default` 技巧、`__log__` 日志回报
- 本地验证：mock 服务器 + qd 官方引擎跑四类场景
- 落盘规范：目录命名、生成脚本、凭据占位

配套参考资料在 `references/` 下（`recon.md` 侦察、`qd-engine.md` 引擎行为）。

## 安全说明

本仓库所有 HAR 文件中的账号凭据（token、手机号、邮箱、用户 ID 等）均已替换为占位符（如 `<YOUR_TOKEN>`、`<YOUR_PHONE>`），**不包含任何真实账号信息**。使用时请填入自己的凭据，并注意不要将自己的凭据提交回仓库。

## 贡献约定

新增 HAR 请遵守 [AGENTS.md](AGENTS.md) 中的项目规则（目录结构、命名大小写等）。

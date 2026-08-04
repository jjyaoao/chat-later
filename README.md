# 后来呢？ / Chat Later

把一年聊天整理成一份**可以点回原文的关系年鉴**。

它不判断谁更爱谁，也不做简单的正负面情绪打分。它沿着时间寻找一件事的起点与后来：一句约定有没有落地，一次反馈之后有没有行动，那些隔了几个月才出现的回应。

![后来呢？上传与模型入口](article/assets/09-BYOK上传入口.png)

## 它能看到什么

- **跨月约定**：从提出、等待、重新排期到最终发生；
- **互动转折**：把一次反馈与后续行为放回同一条时间线；
- **未完成事项**：找回被新消息淹没的“下次再说”；
- **证据回看**：每个事实结论绑定 `E00001` 形式的原始消息编号；
- **视觉年鉴**：自动生成聊天词云、年度活跃热力图和趣味数据卡片；
- **判断边界**：观察与推断分开，证据不足时明确写“无法判断”。

![聊天词云与趣味数据](article/assets/10-词云与趣味数据.png)

![年度聊天活跃热力图](article/assets/11-年度活跃热力图.png)

![真实报告总览](article/assets/04-真实报告总览.png)

点击报告中的证据编号，可以回到化名后的原文：

![证据回看](article/assets/05-证据回溯弹窗.png)

## 一条线索如何跨过 27 天

```text
03 / 09  “周末要不要去江边骑车？”
03 / 28  “必须，四月第一个周六。”
04 / 05  “我到地铁口了，今天风有点大。”
```

「后来呢？」关注的不是“骑车”出现了几次，而是这个约定如何从邀约变成行动。

![一条约定跨过 27 天](article/assets/07-跨月线索卡片.png)

## 快速体验

只需要 Python 3.10+，不依赖第三方包：

```powershell
python app.py
```

打开 `http://127.0.0.1:8765`，点击“载入虚构样例”，然后开始分析。

没有配置 API 时，页面会明确显示 `LOCAL PREVIEW · 未调用模型`。本地预览可以体验解析、脱敏、报告结构和证据交互，不会伪装成模型结果。

## 接入 Doubao-Seed-Evolving

页面支持两种模型接入方式：

1. **使用自己的 Key（BYOK）**：在页面的模型入口粘贴 `ARK_API_KEY`。Key 只进入本次请求，不写入浏览器存储、日志、缓存或报告；服务端固定只调用火山方舟北京区 Responses API 和 `doubao-seed-evolving`。
2. **站点统一配置**：部署者通过环境变量提供 Key，访客可以直接分析；公开部署前应自行增加登录、限流与额度控制，不建议无保护地暴露共享 Key。

环境变量配置方式：

```powershell
$env:ARK_API_KEY="你的火山方舟 API Key"
$env:ARK_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"
$env:ARK_MODEL="doubao-seed-evolving"
$env:ARK_API_STYLE="responses"
python app.py
```

页面中填写的 Key 会经过当前部署实例转发给火山方舟。不要在不信任的第三方部署中填写真实 Key；处理敏感聊天时，推荐克隆仓库后在本地运行。

## 部署成公开入口

项目附带容器配置，可部署到任意支持 Docker 的 HTTPS 服务：

```powershell
docker build -t chat-later .
docker run --rm -p 8765:8765 chat-later
```

公开入口默认推荐 BYOK：访客填写自己的 Ark Key，站点不承担模型额度。若要配置共享 `ARK_API_KEY`，请先在网关增加登录、请求频率限制和用量上限。由于聊天记录和 API Key 都属于敏感数据，公开部署必须使用 HTTPS，并关闭请求体日志。

## 三阶段 Agent

```text
聊天文本
  → 本地解析、证据编号与敏感信息遮盖
  → Seed Evolving 制定本次分析计划
  → 读取完整记录生成结构化报告
  → 带着报告重读原文，审计每条证据
  → 可视化关系年鉴
```

![三阶段 Agent](article/assets/02-Agent三阶段流程.png)

第一阶段决定这份记录应该关注什么；第二阶段建立完整叙事；第三阶段收紧过度推断、检查引用，并删除证据不足的结论。

## 支持的输入

推荐文本格式：

```text
[2025-01-03 23:27] 林舟: 辛苦啦，先喝水，想吐槽我就听着
[2025-01-03 23:42] 南星: 讲完好多了，谢谢你没急着给建议
```

也支持：

- TXT / Markdown 多行消息；
- `timestamp/sender/content` CSV；
- `date/time/name/message` 等常见中英文 CSV 表头。

项目不抓取微信数据，也不绕过客户端安全机制。页面只接受用户主动上传或粘贴的文本，并在调用模型前完成姓名化名和常见敏感号码遮盖。请只使用自己有权处理、并已获得相关参与者同意的导出文本。

## 项目结构

```text
relationship_archaeology/
  parser.py       # 解析聊天并分配证据编号
  privacy.py      # 姓名化名与敏感字段遮盖
  prompts.py      # 计划、分析、审计 Prompt
  seed_client.py  # Responses API、限流退避与可选缓存
  service.py      # 三阶段任务编排
static/           # 零依赖 Web 界面
sample_data/      # 公开虚构聊天样例
tests/            # 核心解析与证据链测试
article/assets/   # README 与文章展示图
```

## 核心检查

```powershell
python -m unittest discover -s tests -v
```

公开样例与截图全部为虚构内容。`warmth` / `friction` 是帮助阅读时间变化的叙事指标，不是心理量表；报告不构成心理评估、医疗建议或关系裁决。

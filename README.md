# feishu-daily-logger

本项目服务于[P 人的自我管理：大语言模型辅助的自我认知实验](https://itpyi.site/blog/posts/LLM-assist-self-awareness/)。目前仅配置了数据采集部分。实现一个低门槛的自我观察的数据收集：用飞书群聊 + GitHub Actions 自动收集每日消息，每天零点，GitHub Actions 自动调用飞书开放平台 API，拉取前一天在**记录群聊**里发送的所有消息，格式化为 JSONL 存入仓库。录入无摩擦，整理完全自动，无经济负担。GitHub 私有仓库中 GitHub Actions 额度为每月 2000 分钟，参见[官方文档](https://docs.github.com/en/actions/reference/limits)，本项目数据采集运行一次少于 20 秒，每天自动运行一次。

> **输入方式**：在飞书中建一个只有你和 bot 的群聊，平时向这个群发消息即可。

---

## 目录结构

```
.
├── .github/
│   └── workflows/
│       └── daily_collect.yml   # 定时任务：每日零点拉取消息
├── json/                       # 输出目录：每日 JSONL 文件（纳入 git）
├── raw/                        # 手动导出的原始 txt（已加入 .gitignore）
├── convert_record.py           # 手动转换脚本（txt → jsonl，备用）
├── fetch_feishu.py             # 自动拉取脚本（飞书 API → jsonl）
├── .gitignore
└── README.md
```

---

## 一、创建飞书自建应用

> 如果已有用于记录的 bot 应用，可跳至 [获取 App ID / App Secret](#获取-app-id--app-secret)。

1. 打开 [飞书开放平台](https://open.feishu.cn/app) → **创建企业自建应用**
2. 填写名称（如 `认知节律记录 Bot`）、描述，上传图标
3. 进入应用详情页

### 获取 App ID / App Secret

**基础信息** → **凭证与基础信息** → 复制 `App ID` 和 `App Secret`

### 配置权限

**开发配置** → **权限管理** → 搜索并开通以下**全部**权限：

| 权限标识 | 用途 |
|---------|------|
| `im:message:readonly` | 获取 bot 所在会话的消息（基础读取权限）|
| `im:message.group_msg:readonly` | 读取群组消息内容（群聊专用）|
| `im:chat:readonly` | 获取群组信息，用于通过 chat_id 确认群组状态 |

> **注意**：三个权限均需开通。

### 发布应用

**应用发布** → **版本管理与发布** → 创建版本 → 提交审核（自建应用在本企业内审核通常秒过）→ 发布

---

## 二、建立记录群聊

飞书个人版/小团队版中，直接与 bot 的 P2P 对话框可能没有输入框（系统限制）。
**解决方案：建一个只有你 + bot 的群聊**，在群里发消息即可正常使用。

### 操作步骤

1. 飞书 → **消息** → 左上角 **✏️ 新建对话** → 选择**创建群组**
2. 群名随意（如 `认知节律`），**成员**搜索并添加你的 bot 名称
3. 点击完成，群聊创建成功
4. 此后每次记录，在这个群里发消息即可

> **注意**：飞书免费版创建群组可能有路径差异，也可以从**通讯录 → 应用**找到 bot，点击后选择"邀请进群"。

---

## 三、获取 CHAT_ID

CHAT_ID 是上面那个群聊的 ID，格式类似 `oc_xxxxxxxxxxxxxxxx`，可以直接从飞书 GUI 复制：

在飞书中打开记录群聊 → 点击右上角 **群设置（···）** → **群信息** → 找到"群 ID"一栏，点击复制即可。

---

## 四、配置 GitHub 仓库

### Fork 本仓库

1. 点击右上角 **Fork** → 将仓库 fork 到你的账号下
2. 进入你 fork 后的仓库 → **Settings** → 将 **Visibility** 改为 **Private**（推荐，避免个人记录公开）
3. 在 `.gitignore` 中删除最后一段 `json/*.jsonl` 的注释行，让 Actions 能够 commit 你的记录

### 设置 Secrets

进入你的仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，依次添加：

| Name | Value |
|------|-------|
| `FEISHU_APP_ID` | 飞书自建应用的 App ID |
| `FEISHU_APP_SECRET` | 飞书自建应用的 App Secret |
| `FEISHU_CHAT_ID` | 上一步获取的群聊 ID（`oc_` 开头） |

> `FEISHU_CHAT_TYPE` 无需设置，默认值 `chat` 对应群聊。

---

## 五、验证自动化流程

### 本地测试（可选）

```bash
pip install requests

export FEISHU_APP_ID="your_app_id"
export FEISHU_APP_SECRET="your_app_secret"
export FEISHU_CHAT_ID="oc_xxxxxxxx"
# FEISHU_CHAT_TYPE 默认 chat（群聊），无需设置

# 如果本地使用了 Clash/V2Ray 等代理，需加上此变量绕过 SSL 验证问题
# export FEISHU_SSL_VERIFY=0

# 拉取昨天的消息（dry-run，只打印不写文件）
python fetch_feishu.py --dry-run

# 拉取指定日期
python fetch_feishu.py --date 20260309 --dry-run

# 实际写入 json/ 目录
python fetch_feishu.py --date 20260309
```

### 手动触发 GitHub Actions

仓库 → **Actions** → **Daily Feishu Collect** → **Run workflow**
- 可选填 `date`（YYYYMMDD），留空则拉取昨天

### 确认定时执行

Actions 设置了每天 UTC 16:00（= 北京时间 00:00）自动运行。
首次 push 后，等到次日零点即可在 Actions 页面看到执行记录，`json/` 目录中会出现新的 `.jsonl` 文件。

---

## 六、输出格式

每条消息一行 JSON，与 `convert_record.py` 输出格式完全一致：

```jsonl
{"time": "2026/03/09 22:27", "message": "到宿舍了"}
{"time": "2026/03/09 23:54", "message": "搞完了，准备洗漱睡觉"}
```

文件命名规则：`json/YYMMDD.jsonl`（如 `260309.jsonl`）

---

## 七、常见问题

**Q: 飞书 bot 对话框没有输入框，无法发消息**
- 原因：飞书个人版/小团队版中，系统限制 P2P bot 对话（"开发者小助手"通知页面是单向的）
- 解决：按[第二节](#二建立记录群聊)建一个群聊，把 bot 加进来，在群里发消息即可
- 不需要配置"事件与回调"，我们是主动拉取消息，不需要 bot 实时响应

**Q: API 返回 `99991663` 或 error code `230027`（消息权限不足）**
- 错误示例：`Lack of necessary permissions, ext=need scope: im:message.group_msg`
- 解决：确认已在飞书开放平台为应用开通全部三个权限（`im:message:readonly`、`im:message.group_msg:readonly`、`im:chat:readonly`），**重新发布应用**后再试

**Q: 拉到的消息为空，但当天确实发过消息**
- 确认 `FEISHU_CHAT_ID` 是群聊 ID（不是 P2P）
- 检查时区：脚本默认按北京时间计算"昨天"

**Q: 本地运行时出现 SSL 握手失败（`UNEXPECTED_EOF_WHILE_READING`）**
- 原因：本地使用了 Clash/V2Ray 等代理，HTTPS CONNECT 隧道偶发 SSL 握手异常
- 解决：运行前设置 `export FEISHU_SSL_VERIFY=0`，GitHub Actions 环境无此问题

**Q: GitHub Actions 没有自动触发**
- GitHub 对不活跃仓库会暂停 cron，需要手动触发一次激活
- 确认 `.github/workflows/daily_collect.yml` 已成功 push 到 `main` 分支

**Q: 想保留手动导出的 txt 作为备份**
- `raw/` 已加入 `.gitignore`，不会被 commit，本地保留即可
- `convert_record.py` 依然可用作手动补录



# TOMO Taste Lab — API 设置指南

## 最快上手（5 分钟）

只需要一个 Anthropic API Key 就能跑。其他模型可选。

---

## Step 1: 获取 Anthropic API Key（必须）

1. 打开 [console.anthropic.com](https://console.anthropic.com)
2. 注册/登录（支持 Google 账号）
3. 左侧菜单 → "API Keys" → "Create Key"
4. 复制 Key（格式：`sk-ant-api03-...`）
5. 充值 $5（左侧 "Billing" → "Add Credits"）— 够跑 50+ 次模拟

## Step 2: 设置环境变量

**Mac / Linux：**
```bash
# 临时设置（当前终端窗口有效）
export ANTHROPIC_API_KEY=sk-ant-api03-你的key

# 永久设置（加到 ~/.zshrc 或 ~/.bashrc）
echo 'export ANTHROPIC_API_KEY=sk-ant-api03-你的key' >> ~/.zshrc
source ~/.zshrc
```

**Windows (PowerShell)：**
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-api03-你的key"
```

**Windows (CMD)：**
```cmd
set ANTHROPIC_API_KEY=sk-ant-api03-你的key
```

## Step 3: 安装依赖

```bash
pip install anthropic
```

## Step 4: 运行

```bash
cd tomo_taste_lab
python agent_simulation.py --product both --n 500
```

看到 `模式: 🟢 真实 LLM Agent` 就说明 API 接通了。

---

## 可选：增加模型多样性（推荐）

v3.0 的核心升级是**多模型差异化**——不同 Agent 使用不同的 AI 模型，避免"同一个大脑扮演所有人"。

### 添加 OpenAI（GPT-4o-mini）

1. 打开 [platform.openai.com](https://platform.openai.com)
2. API Keys → Create → 复制
3. 充值 $5
4. 设置：
```bash
export OPENAI_API_KEY=sk-你的key
pip install openai
```

### 添加 DeepSeek

1. 打开 [platform.deepseek.com](https://platform.deepseek.com)
2. API Keys → 创建 → 复制
3. 充值 ¥10
4. 设置：
```bash
export DEEPSEEK_API_KEY=sk-你的key
# DeepSeek 使用 OpenAI 兼容 API，不需要额外安装
```

### 模型分配逻辑

设置了多个 Key 后，引擎会自动轮流分配：

```
Agent #0 → Claude Haiku
Agent #1 → Claude Sonnet
Agent #2 → GPT-4o-mini
Agent #3 → DeepSeek
Agent #4 → Claude Haiku
Agent #5 → Claude Sonnet
...
```

500 个 Agent，4 个模型 → 每个模型约 125 个 Agent。

报告会自动生成**模型间对比表**，显示不同 AI 模型是否给出一致预测。

---

## 成本估算

| 配置 | 500人 × 1 产品 | 500人 × 2 产品 |
|------|----------------|----------------|
| 仅 Claude Haiku | ¥3-5 | ¥6-10 |
| Claude Haiku + Sonnet | ¥8-12 | ¥16-24 |
| 全部 4 模型 | ¥10-15 | ¥20-30 |
| Claude Haiku only（200人） | ¥1-2 | ¥2-4 |

> Batch API（批量模式）可再降 50%，但需要额外代码支持。当前版本用实时 API。

---

## 常见问题

**Q: 我只有 Anthropic Key，能跑吗？**
A: 完全可以。默认用 Claude Haiku + Sonnet 两个模型。`--models claude-only` 参数可以只用 Claude。

**Q: 提示 "rate limit" 怎么办？**
A: 引擎内置了限速（每 10 个请求暂停 0.5 秒）。如果还报错，把 `--n` 调低到 200，或者等几分钟再跑。

**Q: Key 会不会泄露？**
A: Key 只存在你本地的环境变量里。代码里没有 hardcode 任何 Key。推 GitHub 时，`.gitignore` 会自动排除 `.env` 文件。

**Q: 怎么确认在用真实 API 而不是 Mock？**
A: 看启动输出。`🟢 真实 LLM Agent` = API 接通。`🟡 模拟模式（MOCK）` = 没接通，检查 Key。

**Q: 500 人太多/太慢，可以减少吗？**
A: 可以。`--n 200` 跑 200 人，约 2-3 分钟。但低于 100 会自动调整到 100（统计最低门槛）。

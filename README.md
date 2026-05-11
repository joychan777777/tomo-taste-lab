# TOMO Taste Lab 🧪

**Can AI understand what Chinese consumers actually want to drink?**

用 AI 模拟 500 个中国消费者，预测 F&B 新品成败。成本 ¥15，耗时 48 小时。

---

## The Problem

A brand launches a new product and wants to know: will consumers buy it?

Traditional approach: spend ¥300K-500K, recruit 300 people for a CLT (Central Location Test), wait 6-8 weeks. By the time the report arrives, competitors have launched three new products.

**TOMO Taste Lab** is a ¥15, 48-hour pre-screening tool — an X-ray before the CT scan.

---

## How It Works

```
500 AI Consumers (7 dimensions each)
        ↓
Multiple LLM Models (Claude / DeepSeek / GPT)
        ↓
Independent Evaluation (temperature randomized)
        ↓
Statistical Aggregation (by age, city, income, etc.)
        ↓
Prediction Report (with baseline comparison)
```

### Key Design Decisions

1. **Multi-model diversity** — If all 500 agents use the same LLM, you have 1 brain playing 500 roles. We distribute agents across Claude Haiku, Claude Sonnet, DeepSeek V4 Flash, and GPT-4o-mini. When models agree, confidence is higher. When they disagree, that's a signal worth investigating.

2. **7-dimension personas** — Each consumer has: age, gender, city tier, income, coffee habit, social media preference, novelty attitude. Distributions match China population data + Luckin user profiles.

3. **Baseline comparison** — Every simulation auto-generates a "just ask the LLM directly" benchmark. If 500 agents say the same thing as a single prompt, the multi-agent approach adds no value.

4. **Temperature randomization** — Each agent gets a random temperature (0.7-1.0), creating variation even within the same model.

---

## Prediction Record

### Backtests (post-hoc, designer knew outcomes)

| Product | Prediction | Actual Result | Hit? |
|---------|------------|---------------|------|
| 褚橙拿铁 (2024.1) | SUCCESS | 695万杯/首周 | ✅ |
| 龙年酱香巧克力 (2024.1) | FAILURE | 首日部分门店仅3杯 | ✅ |

### Blind Tests (predictions locked before outcome)

| Product | Prediction | Score | Actual Result | Commit Hash |
|---------|------------|-------|---------------|-------------|
| 牛油果羽衣酸奶昔 | FAILURE | 5.0/10 | ⏳ Pending | `7e052c8f` |
| 瓦尔登蓝芒果酸奶昔 | FAILURE | 5.4/10 | ⏳ Pending | `3004e026` |

> ⚠️ **Backtests are open-book exams** — they only prove the pipeline runs. Blind tests are the real validation.

### Backtest Library (v3.1, ready to run)

| Code | Product | Known Outcome | Data |
|------|---------|---------------|------|
| `chucheng` | 褚橙拿铁 | SUCCESS | 首周695万杯 |
| `dragon` | 龙年酱香巧克力 | FAILURE | 首日部分门店仅3杯 |
| `butter` | 小黄油拿铁 (黄油小熊联名) | SUCCESS | 首周1333万杯 |
| `duolingo` | 绿沙沙拿铁 (多邻国联名) | SUCCESS | 首周900万杯 |
| `lichee` | 长安荔果冰萃 | SUCCESS | 首周850万杯 |
| `bitter_melon` | 苦瓜轻体果蔬茶 | MODERATE | 话题热但无官方销量 |

---

## Quick Start

### Minimum Setup (Claude only)

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-xxx

# Run blind tests (2 products, 500 agents)
python agent_simulation.py --product both --n 500

# Run a single backtest
python agent_simulation.py --product butter --n 200

# Run all backtests
python agent_simulation.py --product all-backtest --n 200
```

### Full Multi-Model Setup (recommended)

```bash
pip install anthropic openai

export ANTHROPIC_API_KEY=sk-ant-xxx    # Claude Haiku + Sonnet
export OPENAI_API_KEY=sk-xxx            # GPT-4o-mini
export DEEPSEEK_API_KEY=sk-xxx          # DeepSeek V4 Flash

python agent_simulation.py --product both --n 500 --models multi
```

### CLI Options

| Flag | Options | Default | Description |
|------|---------|---------|-------------|
| `--product` | `avocado`, `mango`, `both`, `chucheng`, `dragon`, `butter`, `duolingo`, `lichee`, `bitter_melon`, `all-backtest` | `both` | Product to simulate |
| `--n` | 100-1000 | 500 | Number of AI consumers |
| `--output` | path | `./reports` | Output directory |
| `--models` | `multi`, `claude-only` | `multi` | Model selection mode |

### Output

Each run produces:
- `report_[产品名].md` — Human-readable prediction report
- `data_[产品名].json` — Raw data with all agent responses

---

## Cost

| Setup | Cost per run (500 agents × 1 product) |
|-------|---------------------------------------|
| Claude Haiku only | ~¥3 |
| Claude Haiku + Sonnet | ~¥8 |
| All 4 models | ~¥10-15 |

---

## Project Structure

```
tomo-taste-lab/
├── agent_simulation.py     # Core engine (all-in-one, ~900 lines)
├── quick_run.py             # Lightweight test runner
├── API_设置指南.md           # API key setup guide (Chinese)
├── FAQ_技术质疑回应.md       # Technical FAQ / challenges
├── RED_TEAM_全面审查.md      # Self-audit / known weaknesses
├── reports/                 # Blind test reports (500 agents)
│   ├── report_牛油果羽衣酸奶昔.md
│   ├── data_牛油果羽衣酸奶昔.json
│   ├── report_瓦尔登蓝芒果酸奶昔.md
│   └── data_瓦尔登蓝芒果酸奶昔.json
└── 盲测验证跫踪.md           # Blind test verification tracker
```

---

## Limitations (please read)

1. **LLM agents are not real consumers.** They simulate language patterns, not purchase behavior. A simulated consumer saying "I'd try this" is not the same as someone actually buying it.

2. **500 agents ≠ 500 independent samples.** Agents using the same LLM share knowledge and biases. If all models have a positive impression of "褚橙" as a brand, the prediction will skew positive regardless of persona assignment.

3. **Post-hoc backtests prove very little.** The designer knew the outcomes when designing the simulation. Cognitive bias cannot be fully eliminated. Only blind tests with locked commits count.

4. **China-specific.** Personas, demographics, and product contexts are calibrated for the Chinese F&B market. Using this for other markets requires re-calibration.

5. **No social contagion.** Agents don't influence each other. Real purchase decisions are heavily social — word of mouth, social media virality, and FOMO are not modeled.

6. **Model bias is systematic.** In our tests, Claude Sonnet is consistently more pessimistic than Haiku. This is a systematic bias, not genuine diversity of opinion.

7. **The hardest products to predict are in the middle.** Extreme hits and extreme failures are easy to call. The real test is moderate products — and this tool's accuracy on those is unvalidated.

---

## Methodology

### v3.0 vs v2.0

| Feature | v2.0 | v3.0 |
|---------|------|------|
| Models | 1 (Claude Haiku) | 2-4 (Claude + DeepSeek + GPT) |
| Persona dimensions | 4 | 7 |
| Temperature | Fixed | Randomized 0.7-1.0 |
| Baseline comparison | None | Auto-generated |
| Default sample size | 200 | 500 |

### Prediction Criteria

| Prediction | Condition |
|------------|-----------|
| SUCCESS | avg_score ≥ 7.0 AND try_rate ≥ 60% |
| MODERATE | avg_score ≥ 5.5 AND try_rate ≥ 40% |
| FAILURE | Everything else |

---

## FAQ

**Q: How is this different from just asking ChatGPT "will this product succeed?"**

Asking ChatGPT directly gives you one omniscient answer with no confidence interval, no demographic breakdown, and no "why." 500 agents with different personas can tell you: 25-year-old women in tier-1 cities react completely differently from 40-year-old men in tier-3 cities. And when Claude, GPT, and DeepSeek agree, that's more credible than any single model.

**Q: Can I use this for non-Luckin products?**

Yes. Edit the product definition in `agent_simulation.py` — change name, price, description, category. The persona distribution is calibrated for Chinese F&B broadly, not just Luckin.

**Q: Why Python? Why not a web app?**

Because the core value is in the methodology and domain expertise, not the UI. A script that anyone can read, understand, and modify in 10 minutes is more useful than a polished dashboard that hides how things work.

---

## Who Built This

**Joy Chan** — Brand strategist with years of F&B marketing experience. Not an engineer — the code was written with Claude's help.

The contribution breakdown: **domain expertise** (which products to test, how to design personas, how to interpret results) is the hard part. **Code** is the easy part.

Building [TOMO](https://github.com/joychan777777/tomo-taste-lab) — a taste AI platform exploring whether AI can understand consumer preferences at scale.

**Contact:** joy.chan777@gmail.com

---

## Contributing

Fork it, question it, file issues. If you run it on a product and get interesting results (right or wrong), I want to hear about it.

Serious criticism is 10,000× more valuable than a star.

---

## License

MIT — Use it, fork it, improve it.

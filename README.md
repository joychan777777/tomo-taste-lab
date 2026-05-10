# TOMO Taste Lab 🧪

**AI-powered consumer perception simulation for F&B new product launches.**

用 AI 模拟消费者，预测新品成败。

---

## What is this?

TOMO Taste Lab generates 500 AI consumer agents — each with unique 7-dimension demographics (age, gender, city tier, income, coffee habit, social media, novelty attitude) — distributed across multiple LLM models, and asks them to independently evaluate a new F&B product. The result is a structured prediction report with segment-level breakdowns, model-level consistency checks, and baseline comparison.

**Not a replacement for real market research. A fast, cheap pre-screening tool.**

Think of it as an X-ray before a CT scan: quick, cheap, directional.

---

## How it works

1. **Persona Generation** — 500 consumers with 7-dimension weighted demographics matching China's population distribution
2. **Multi-Model Evaluation** — Agents distributed across Claude Haiku + Sonnet (+ optional GPT-4o-mini, DeepSeek). Each receives a product brief and responds in-character with temperature randomization (0.7-1.0)
3. **Baseline Comparison** — Automatic "just ask the LLM directly" benchmark to validate whether multi-agent adds value
4. **Statistical Aggregation** — Results broken down by age, city tier, gender, income, novelty attitude, and model
5. **Report Generation** — Markdown report with SHA-256 hash for tamper-proof timestamping

---

## Prediction Record

| # | Product | Type | Prediction | Actual Result | Hit? | Commit |
|---|---------|------|------------|---------------|------|--------|
| 001a | 褚橙拿铁 | Backtest | SUCCESS | 695万杯/week ✅ | ✅ | — |
| 001b | 龙年酱香巧克力 | Backtest | FAILURE | ~3杯/store day 1 ❌ | ✅ | — |
| 002a | 牛油果羽衣酸奶昔 | **Blind Test** | FAILURE (5.0/10) | Pending | — | `7e052c8f` |
| 002b | 瓦尔登蓝芒果酸奶昔 | **Blind Test** | FAILURE (5.4/10) | Pending | — | `3004e026` |

> ⚠️ Backtests (#001) are post-hoc — the designer knew the outcomes. Only blind tests count as real validation.
> Blind tests (#002) ran 500 agents each (Claude Haiku + Sonnet), predictions locked via report hash before outcome.

---

## Quick Start

```bash
pip install anthropic
export ANTHROPIC_API_KEY=your_key_here
python agent_simulation.py --product both --n 500
```

Optional: add more models for diversity (see API_设置指南.md):
```bash
export OPENAI_API_KEY=your_key      # GPT-4o-mini
export DEEPSEEK_API_KEY=your_key    # DeepSeek V3
```

---

## Cost

~¥10-15 per run (500 agents × 2 products, Claude Haiku + Sonnet)

---

## Limitations (read this)

1. **LLM agents are not real consumers.** They simulate language patterns, not actual purchase behavior.
2. **500 agents ≠ 500 independent data points.** They share underlying models, introducing correlated errors. Multi-model distribution (v3.0) reduces but does not eliminate this.
3. **Post-hoc backtests prove nothing.** Only blind predictions with locked commits count.
4. **China-specific.** Personas, demographics, and consumption patterns are calibrated for Chinese F&B market only.
5. **No social contagion.** Agents don't influence each other. Real purchase decisions are heavily social.
6. **Model bias direction.** In our tests, Sonnet is consistently more pessimistic than Haiku. This is a systematic bias, not diversity.

---

## Why I built this

I'm not an engineer. I'm a brand strategist with years of experience in F&B marketing.

I built this because I saw a gap: brands spend ¥300K-500K and 6-8 weeks on consumer testing, but by the time results come back, the market has moved on. There should be a ¥10, 48-hour pre-screening step before that investment.

The code is the easy part. The hard part — knowing which products to test, how to design personas that reflect real consumer segments, and how to interpret results — comes from domain expertise, not engineering skill.

---

## About

**Joy Chan** — Brand strategist, F&B industry. Building [共醸](https://github.com/xxx) (craft beer brand) and [TOMO](https://github.com/xxx) (taste AI platform).

Contact: joy.chan777@gmail.com

---

## License

MIT — Use it, fork it, improve it. If you build something cool with it, let me know.

#!/usr/bin/env python3
"""
TOMO Taste Lab — LLM Agent 消费者模拟引擎 v3.0
多模型差异化 + Baseline 对比 + Red Team 全面修复

升级内容（v3.0 vs v2.0）：
- 🔴 R1 修复：支持多个不同 LLM 模型（Claude Haiku / Sonnet / DeepSeek / GPT-4o-mini）
  → 消除"同一个大脑扮演所有人"的偏差
- 🔴 R2 修复：直测产品加入"LLM 是否已知"自检
- 🟡 Y1 修复：自动生成 baseline 对比（单次直接预测 vs 多Agent模拟）
- 🟡 Y4 修复：persona 维度从 4 扩展到 7
- 默认 500 人（从 200 升级，每分群 ~70 人，统计更可靠）
- temperature 随机化（0.7-1.0），增加 Agent 间差异

使用方式：
1. 设置环境变量:
   export ANTHROPIC_API_KEY=your_key        # 必须（Claude 模型）
   export OPENAI_API_KEY=your_key            # 可选（GPT-4o-mini）
   export DEEPSEEK_API_KEY=your_key          # 可选（DeepSeek）
2. 运行:
   python agent_simulation.py --product both --n 500
   python agent_simulation.py --product avocado --n 200 --models claude-only
"""

import json
import os
import sys
import hashlib
import random
import time
import signal
from datetime import datetime
from pathlib import Path

# ============================================================
# 0. 多模型初始化
# ============================================================

AVAILABLE_MODELS = {}

try:
    import anthropic
    AVAILABLE_MODELS["claude-haiku"] = {
        "provider": "anthropic",
        "model_id": "claude-haiku-4-5-20251001",
        "display": "Claude Haiku 4.5",
        "cost_per_1k": 0.001  # $/1K tokens (approx)
    }
    AVAILABLE_MODELS["claude-sonnet"] = {
        "provider": "anthropic",
        "model_id": "claude-sonnet-4-6",
        "display": "Claude Sonnet 4.6",
        "cost_per_1k": 0.015
    }
except ImportError:
    print("⚠️  anthropic 包未安装。运行: pip install anthropic")

try:
    import openai
    AVAILABLE_MODELS["gpt-4o-mini"] = {
        "provider": "openai",
        "model_id": "gpt-4o-mini",
        "display": "GPT-4o-mini",
        "cost_per_1k": 0.00015
    }
except ImportError:
    pass  # OpenAI 可选

# DeepSeek 使用 OpenAI 兼容 API
if "openai" in sys.modules:
    AVAILABLE_MODELS["deepseek"] = {
        "provider": "deepseek",
        "model_id": "deepseek-chat",
        "display": "DeepSeek V3",
        "cost_per_1k": 0.0001
    }

random.seed(int(datetime.now().strftime("%Y%m%d")))


class _Timeout(Exception):
    pass


def _timeout_handler(signum, frame):
    raise _Timeout("API call timed out")


def _call_with_timeout(func, timeout_sec=15):
    """在 timeout_sec 秒内调用 func()，超时抛 _Timeout。仅 Unix。"""
    old = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout_sec)
    try:
        return func()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def probe_model_availability(clients):
    """运行时探测每个模型是否真正可用（10s 超时）。
    返回实际可用的模型 key 列表。解决试用账号无权访问某些模型的问题。"""
    available = []
    for model_key, model_info in list(AVAILABLE_MODELS.items()):
        provider = model_info["provider"]
        if provider not in clients:
            continue
        try:
            def _probe():
                if provider == "anthropic":
                    resp = clients["anthropic"].messages.create(
                        model=model_info["model_id"],
                        max_tokens=10,
                        messages=[{"role": "user", "content": "回复OK"}]
                    )
                    return resp.content[0].text
                else:
                    resp = clients[provider].chat.completions.create(
                        model=model_info["model_id"],
                        max_tokens=10,
                        messages=[{"role": "user", "content": "回复OK"}]
                    )
                    return resp.choices[0].message.content

            result = _call_with_timeout(_probe, timeout_sec=10)
            available.append(model_key)
            print(f"  ✅ {model_info['display']} — 可用")
        except _Timeout:
            print(f"  ❌ {model_info['display']} — 超时（10s），已跳过")
        except Exception as e:
            err_msg = str(e)[:80]
            print(f"  ❌ {model_info['display']} — 不可用（{err_msg}）")
    return available


# ============================================================
# 1. PERSONA 生成器（v3: 7 维度，从 v2 的 4 维度扩展）
# ============================================================

CHINA_DEMOGRAPHICS = {
    "city_tiers": {
        "一线": {
            "cities": ["北京", "上海", "广州", "深圳"],
            "weight": 0.18,
            "traits": "消费力强，品牌敏感度高，掦触国际品牌多，对新品接受度高但也更挑剔"
        },
        "新一线": {
            "cities": ["成都", "杭州", "武汉", "南京", "重庆", "西安", "长沙", "苏州"],
            "weight": 0.25,
            "traits": "消费升级中，社交媒体活跃，喜欢打卡新事物，价格敏感度中等"
        },
        "二线": {
            "cities": ["昆明", "郑州", "合肥", "济南", "福州", "石家庄", "太原", "南昌"],
            "weight": 0.30,
            "traits": "注重性价比，受社交媒体影响大但跟风延迟，品牌忠诚度偏高"
        },
        "三线及以下": {
            "cities": ["绵阳", "宜昌", "赣州", "临沂", "柳州", "宿迁", "信阳", "六安"],
            "weight": 0.27,
            "traits": "价格极度敏感，口味偏甜偏重，对新潮概念接受度低，实用主义"
        }
    },
    "age_groups": [
        {"range": "18-24", "weight": 0.28, "traits": "Z世代，重颜值，重社交货币，易被KOL影哿，尝鲜欲强，品牌忠诚度低"},
        {"range": "25-30", "weight": 0.30, "traits": "职场新人到中层，消费能力上升，开始关注品质，会看测评，有自己判断"},
        {"range": "31-40", "weight": 0.27, "traits": "消费趋于理性，有明确偏好，不容易被营销打动，注重健康和品质"},
        {"range": "41-50", "weight": 0.15, "traits": "消费保守，偏好传统口味，不太关注社交媒体，价格和实用是核心"}
    ],
    "genders": [
        {"g": "女性", "weight": 0.58, "traits": "瑞幸核心用户群，颜值驱动明显，喜欢分享，对甜度敏感"},
        {"g": "男性", "weight": 0.42, "traits": "更关注功能性（提神），对颜值不太敏感，偏好经典口味"}
    ],
    "coffee_habits": [
        {"level": "每天喝咖啡", "weight": 0.30, "traits": "有明确口味偏好，能区分好坏，对咖啡品质有要求"},
        {"level": "每周2-3次", "weight": 0.35, "traits": "咖啡是生活方式的一部分，愿意尝试新品但也有底线"},
        {"level": "偶尔喝", "weight": 0.22, "traits": "把咖啡当饮料，更看重口味是否好喝，不太在意咖啡本身"},
        {"level": "基本不喝", "weight": 0.13, "traits": "可能是茶饮爱好者，只有看到特别吸引的新品才会尝试"}
    ],
    # ===== v3 新增维度 =====
    "income_levels": [
        {"level": "学生/月入<5K", "weight": 0.25, "traits": "价格极度敏感，一杯30元的饮品会反复犹豫，更关注优惠券和折扣"},
        {"level": "5K-10K", "weight": 0.30, "traits": "偶尔奖励自己，新品贵几块钱不太在意，但不会频繁购买高价饮品"},
        {"level": "10K-20K", "weight": 0.28, "traits": "消费有选择但不拭据，更关注品质和体验，愿意为好东西多付一点"},
        {"level": "20K+", "weight": 0.17, "traits": "价格不是主要考量，更看重品质、健康、品牌故事。会主动尝试新东西"}
    ],
    "social_media": [
        {"type": "小红书重度用户", "weight": 0.30, "traits": "被种草能力强，颜值即正义，会为了拍照买一杯饮品"},
        {"type": "抖音刷客", "weight": 0.25, "traits": "容易被短视频带节奏，但注意力短暂，热度过了就忘"},
        {"type": "微信为主", "weight": 0.30, "traits": "信息茧房较重，主要受朋友推荐影响，对大众营销免疫"},
        {"type": "不太用社交媒体", "weight": 0.15, "traits": "自主决策，不容易被网红影响，更看重自己的口味判断"}
    ],
    "novelty_attitude": [
        {"type": "尝鲜狂人", "weight": 0.20, "traits": "每个新品都要试，是品牌的免费推广员，但复购率低"},
        {"type": "跟风但谨慎", "weight": 0.35, "traits": "看到朋友圈有人昒才会试，不做第一批，但一旦认可会复购"},
        {"type": "实用主义", "weight": 0.30, "traits": "新品？无所谓/不关注"也完全OK。祖利。好喝才重要。不在乎联名不联名"},
        {"type": "保守派", "weight": 0.15, "traits": "有固定点皅习惯，几乎不尝试新品，除非旧的下架了"}
    ]
}


def weighted_choice(options, key="weight"):
    r = random.random()
    cumsum = 0
    for opt in options:
        cumsum += opt[key]
        if r <= cumsum:
            return opt
    return options[-1]


def generate_persona(pid):
    """生成一个有血有肉的中国消费者 persona（v3: 7 维度）"""
    age = weighted_choice(CHINA_DEMOGRAPHICS["age_groups"])
    gender = weighted_choice(CHINA_DEMOGRAPHICS["genders"])

    tier_list = [{"name": k, "weight": v["weight"], **v}
                 for k, v in CHINA_DEMOGRAPHICS["city_tiers"].items()]
    tier = weighted_choice(tier_list)
    city = random.choice(tier["cities"])
    coffee = weighted_choice(CHINA_DEMOGRAPHICS["coffee_habits"])

    # v3 新增
    income = weighted_choice(CHINA_DEMOGRAPHICS["income_levels"])
    social = weighted_choice(CHINA_DEMOGRAPHICS["social_media"])
    novelty = weighted_choice(CHINA_DEMOGRAPHICS["novelty_attitude"])

    # 生成自然语言 persona 描述（v3: 更丰富）
    persona_text = (
        f"你是一个{age['range']} 岁的{gender['g']}，住在{city}（{tier['name']} 城市）。"
        f"你的月收入水平：{income['level']}。"
        f"你的咖啡习惯：{coffee['level']}。"
        f"你的社交媒体习惯：{social['type']}。"
        f"你对新品的态度：{novelty['type']}。"
        f"\n你的消费特征：{age['traits']}。"
        f"你所在城市的消费特征：{tier['traits']}。"
        f"你的收入消费特征：{income['traits']}。"
        f"你的社交媒体特征：{social['traits']}。"
        f"你的新品态度特征：{novelty['traits']}。"
    )

    return {
        "id": pid,
        "age_range": age["range"],
        "gender": gender["g"],
        "city": city,
        "city_tier": tier["name"],
        "coffee_habit": coffee["level"],
        "income": income["level"],
        "social_media": social["type"],
        "novelty_attitude": novelty["type"],
        "persona_text": persona_text
    }


# ============================================================
# 2. 多模型 LLM Agent 评估器（v3 核心升级）
# ============================================================

EVALUATION_SYSTEM_PROMPT = """你是一个真实的中国消费者。请完全代入以下身份，用第一人称回答。

你的身份：
{persona}

重要规则：
1. 你是一个真实的人，不是AI。请根据你的身份背景做出真实反应。
2. 不要分析市场趋势。只说你自己会不会买、为什么。
3. 不要客气。如果你觉得不好，直说。如果你觉得莫名其妙，也直说。
4. 你的回答要像微信群里随口说的话，不要像写报告。
5. 不是每个新品你都有兴趣。如果你根本不在乎，说"无所谓/不关注"也完全OK。
6. 考虑你的经济状况。如果这个价格对你来说很贵，要诰出来。
7. 想想你身边的朋友会怎么看这个产品。"""

EVALUATION_USER_PROMPT = """瑞幸咖啡出了一个新品：

产品名称：{name}
价格：{price}
产品描述：{description}
产品类型：{category}

请用你自己的话回答以下问题（每个回答1-2句话，口语化）：

1. 听到这个新品的第一反应是什么？
2. 你会去尝试吗？（会/不会/看情况，说原因）
3. 如果喝了觉得还行，你会再买吗？
4. 你会推荐给朋友吗？
5. 给这个产品打个分（1-10分，10分最高）
6. 一句话总结你对这个产品的看法

请严格按这个 JSON 格式返回：
{{
  "first_reaction": "你的第一反应",
  "would_try": "会/不会/看情况",
  "try_reason": "原因",
  "would_repurchase": "会/不会/看情况",
  "repurchase_reason": "原因",
  "would_recommend": "会/不会",
  "score": 7,
  "one_line_summary": "一句话总结"
}}"""

# Baseline prompt: 直接问 LLM "这个产品会不会火"（Y1 修复）
BASELINE_PROMPT = """你是一个中国F&B市场分析师。请评估以下瑞幸新品的市场前景。

产品名称：{name}
价格：{price}
产品描述：{description}
产品类型：{category}

请给出：
1. 预测（SUCCESS / MODERATE / FAILURE）
2. 预估尝试率（0-100%）
3. 预估评分（1-10）
4. 核心理由（3条）

JSON 格式返回：
{{
  "prediction": "SUCCESS/MODERATE/FAILURE",
  "try_rate": 65,
  "score": 7,
  "reasons": ["理由1", "理由2", "理由3"]
}}"""


def _init_clients():
    """初始化所有可用的 API 客户端"""
    clients = {}

    if "claude-haiku" in AVAILABLE_MODELS and os.environ.get("ANTHROPIC_API_KEY"):
        clients["anthropic"] = anthropic.Anthropic()

    if "gpt-4o-mini" in AVAILABLE_MODELS and os.environ.get("OPENAI_API_KEY"):
        clients["openai"] = openai.OpenAI()

    if "deepseek" in AVAILABLE_MODELS and os.environ.get("DEEPSEEK_API_KEY"):
        clients["deepseek"] = openai.OpenAI(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com/v1"
        )

    return clients


def evaluate_with_llm(clients, model_key, persona, product):
    """用指定的 LLM 模型做角色扮演评估（v3: 多模型支持）"""
    model_info = AVAILABLE_MODELS[model_key]
    provider = model_info["provider"]

    # 随机 temperature（0.7-1.0）增加 Agent 间差异
    temp = round(random.uniform(0.7, 1.0), 2)

    system_prompt = EVALUATION_SYSTEM_PROMPT.format(persona=persona["persona_text"])
    user_prompt = EVALUATION_USER_PROMPT.format(**product)

    try:
        if provider == "anthropic":
            client = clients["anthropic"]
            response = client.messages.create(
                model=model_info["model_id"],
                max_tokens=500,
                temperature=temp,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            text = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens

        elif provider in ("openai", "deepseek"):
            client = clients[provider]
            response = client.chat.completions.create(
                model=model_info["model_id"],
                max_tokens=500,
                temperature=temp,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            text = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0
        else:
            return {"persona_id": persona["id"], "error": f"unknown provider: {provider}", "score": 5}

        # 提取 JSON
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
            # 确保 score 是数值（LLM 可能返回 "6.5" 字符串）
            result["score"] = int(float(result.get("score", 5)))
            result["score"] = max(1, min(10, result["score"]))
            result["persona_id"] = persona["id"]
            result["model"] = model_key
            result["temperature"] = temp
            result["tokens_used"] = tokens
            result["raw_response"] = text
            return result

    except json.JSONDecodeError:
        # JSON 解析失败不重试（会在外层处理）
        return {"persona_id": persona["id"], "model": model_key, "error": "json_parse_failed", "score": 5}
    except Exception as e:
        return {"persona_id": persona["id"], "model": model_key, "error": str(e)[:100], "score": 5}

    return {"persona_id": persona["id"], "model": model_key, "error": "parse_failed", "score": 5}


def evaluate_mock(persona, product):
    """无 API 时的模拟模式（仅用于演示 pipeline）"""
    score = random.gauss(6, 2)
    score = max(1, min(10, round(score)))
    return {
        "persona_id": persona["id"],
        "score": score,
        "model": "MOCK",
        "would_try": random.choice(["会", "不会", "看情况"]),
        "try_reason": "[MOCK - 需要API密钥才能获得真实LLM输出]",
        "would_repurchase": random.choice(["会", "不会", "看情况"]),
        "would_recommend": random.choice(["会", "不会"]),
        "one_line_summary": "[MOCK DATA]",
        "is_mock": True
    }


def run_baseline(clients, product, active_models):
    """Y1 修复: 生成 baseline 对比 — 直接问 LLM 预测。
    只对 active_models 中的模型运行，每个模型有 15s 超时保护。"""
    baselines = {}
    prompt = BASELINE_PROMPT.format(**product)

    for model_key in active_models:
        if model_key not in AVAILABLE_MODELS:
            continue
        model_info = AVAILABLE_MODELS[model_key]
        provider = model_info["provider"]
        if provider not in clients:
            continue
        try:
            def _make_call(mk=model_key, mi=model_info, pv=provider):
                if pv == "anthropic":
                    resp = clients["anthropic"].messages.create(
                        model=mi["model_id"],
                        max_tokens=300,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    return resp.content[0].text
                else:
                    resp = clients[pv].chat.completions.create(
                        model=mi["model_id"],
                        max_tokens=300,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    return resp.choices[0].message.content

            text = _call_with_timeout(_make_call, timeout_sec=15)
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                baselines[model_key] = json.loads(text[start:end])
                baselines[model_key]["raw"] = text
        except _Timeout:
            baselines[model_key] = {"error": "timeout (15s)"}
            print(f"  ⚠️  {model_info['display']} baseline 超时，跳过")
        except Exception as e:
            baselines[model_key] = {"error": str(e)[:100]}

    return baselines


# ============================================================
# 3. 统计汇总
# ============================================================

def aggregate_results(results, personas, product_name):
    """汇总模拟结果（v3: 增加模型间对比）"""
    valid = [r for r in results if "error" not in r]
    n = len(valid)
    if n == 0:
        return {"error": "no valid results"}

    # 确保 score 为数值（防御性转换）
    for r in valid:
        r["score"] = int(float(r.get("score", 5)))
    avg_score = sum(r["score"] for r in valid) / n
    try_rate = sum(1 for r in valid if r.get("would_try") == "会") / n
    maybe_try = sum(1 for r in valid if r.get("would_try") == "看情况") / n
    repurchase = sum(1 for r in valid if r.get("would_repurchase") == "会") / n
    recommend = sum(1 for r in valid if r.get("would_recommend") == "会") / n

    # 按人群分解（v3: 增加新维度）
    segments = {}
    seg_fields = [
        ("age_range", "年龄"),
        ("city_tier", "城市层级"),
        ("gender", "性别"),
        ("income", "收入"),
        ("novelty_attitude", "新品态度"),
    ]
    for key_field, key_name in seg_fields:
        groups = {}
        for r, p in zip(results, personas):
            if "error" in r:
                continue
            val = p[key_field]
            if val not in groups:
                groups[val] = []
            groups[val].append(r)

        for val, group in groups.items():
            gn = len(group)
            segments[f"{key_name}:{val}"] = {
                "n": gn,
                "avg_score": round(sum(int(float(r.get("score", 5))) for r in group) / gn, 1),
                "try_rate": round(sum(1 for r in group if r.get("would_try") == "会") / gn * 100, 1),
            }

    # v3: 按模型分解（核心新功能）
    model_breakdown = {}
    for r in valid:
        m = r.get("model", "unknown")
        if m not in model_breakdown:
            model_breakdown[m] = []
        model_breakdown[m].append(r)

    model_stats = {}
    for m, group in model_breakdown.items():
        gn = len(group)
        model_stats[m] = {
            "n": gn,
            "avg_score": round(sum(int(float(r.get("score", 5))) for r in group) / gn, 1),
            "try_rate": round(sum(1 for r in group if r.get("would_try") == "会") / gn * 100, 1),
        }

    # 收集消费者原声
    sample_reactions = []
    for r in valid[:30]:
        if not r.get("is_mock") and r.get("one_line_summary"):
            sample_reactions.append({
                "persona_id": r["persona_id"],
                "summary": r["one_line_summary"],
                "score": r["score"],
                "model": r.get("model", "unknown")
            })

    # 预测判定
    if avg_score >= 7.0 and try_rate >= 0.6:
        prediction = "SUCCESS"
    elif avg_score >= 5.5 and try_rate >= 0.4:
        prediction = "MODERATE"
    else:
        prediction = "FAILURE"

    return {
        "product_name": product_name,
        "n_valid": n,
        "n_errors": len(results) - n,
        "avg_score": round(avg_score, 1),
        "try_rate": round(try_rate * 100, 1),
        "maybe_try_rate": round(maybe_try * 100, 1),
        "repurchase_rate": round(repurchase * 100, 1),
        "recommend_rate": round(recommend * 100, 1),
        "prediction": prediction,
        "segments": segments,
        "model_stats": model_stats,
        "sample_reactions": sample_reactions,
        "is_mock": any(r.get("is_mock") for r in valid),
    }


# ============================================================
# 4. 报告生成（v3: 含模型间对比 + baseline）
# ============================================================

def generate_report(summary, product, baselines, output_dir):
    """生成 Markdown 格式的预测报告（v3 升级版）"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    report_json = json.dumps(summary, ensure_ascii=False, sort_keys=True)
    report_hash = hashlib.sha256(report_json.encode()).hexdigest()[:16]

    mock_warning = ""
    if summary.get("is_mock"):
        mock_warning = """
> ⚠️ **本报告使用模拟数据（MOCK MODE）**
> 未调用 LLM API，数据为随机生成，仅演示报告格式。
> 设置 API KEY 后重新运行可获得真实 LLM Agent 输出。
"""

    # 人群分解表
    segments_table = "| 人群 | 样本量 | 平均分 | 尝试意愿 |\n|------|--------|--------|--------|\n"
    for seg_name, seg_data in summary["segments"].items():
        segments_table += f"| {seg_name} | {seg_data['n']} | {seg_data['avg_score']} | {seg_data['try_rate']}% |\n"

    # v3: 模型间对比表
    model_table = ""
    if summary.get("model_stats") and len(summary["model_stats"]) > 1:
        model_table = "\n## 模型间对比（v3 多模型差异化）\n\n"
        model_table += "| 模型 | Agent数 | 平均分 | 尝试意愿 |\n|------|---------|--------|--------|\n"
        for m, stats in summary["model_stats"].items():
            model_table += f"| {m} | {stats['n']} | {stats['avg_score']} | {stats['try_rate']}% |\n"
        model_table += "\n> 如果不同模型给出相似预测 → 可信度高。如果分裂 → 需要进一步分析。\n"

    # v3: baseline 对比
    baseline_section = ""
    if baselines:
        baseline_section = "\n## Baseline 对比（单次直接预测 vs 多Agent模拟）\n\n"
        baseline_section += "| 方法 | 预测 | 尝试率 | 评分 |\n|------|------|--------|------|\n"
        baseline_section += f"| **多Agent模拟（{summary['n_valid']}人）** | **{summary['prediction']}** | **{summary['try_rate']}%** | **{summary['avg_score']}** |\n"
        for m, bl in baselines.items():
            if "error" not in bl:
                baseline_section += f"| 单次直接问 {m} | {bl.get('prediction','N/A')} | {bl.get('try_rate','N/A')}% | {bl.get('score','N/A')} |\n"
        baseline_section += "\n> baseline = 直接问 LLM \"这个产品会不会火\"（零 persona，零角色扮演）。\n"
        baseline_section += "> 如果多 Agent 和 baseline 给出相同预测 → 200 个 Agent 可能没有附加价值。\n"
        baseline_section += "> 如果不同 → 多 Agent 提供了 baseline 无法提供的分群洞察。\n"

    # 消费者原声
    reactions_section = ""
    if summary["sample_reactions"]:
        reactions_section = "\n## 模拟消费者原声\n\n"
        for rx in summary["sample_reactions"][:15]:
            reactions_section += f"- **#{rx['persona_id']}**（{rx['score']}分, {rx['model']}）：{rx['summary']}\n"

    # 关键声明
    disclaimer = """
## ⚠️ 重要声明

1. **200-500 个 AI Agent ≠ 200-500 个独立样本。** 所有 Agent 共享底层语言模型。即使使用多模型，
   独立性仍远低于真实消费者调研。本报告的统计置信区间被系统性低估。
2. **LLM 角色扮演 ≠ 真实消费行为。** Agent 模拟的是语言表达模式，不是大脑的决策过程。
3e）"""

    print(f"🧪 TOMO Taste Lab — 消费者模拟引擎 v3.0（多模型差异化）")
    print(f"{'=' * 60}")
    print(f"产品: {product['name']}")
    print(f"模拟规模: {n_personas} 个 AI 消费者")

    # 初始化所有可用 API
    clients = _init_clients()
    use_mock = len(clients) == 0

    if use_mock:
        print(f"模式: 🟡 模拟模式（MOCK）")
        print(f"  需设置至少一个 API KEY：")
        print(f"  export ANTHROPIC_API_KEY=sk-ant-...  （必须）")
        print(f"  export OPENAI_API_KEY=sk-...          （可选，增加模型多样性）")
        print(f"  export DEEPSEEK_API_KEY=sk-...        （可选，增加模型多样性）")
        active_models = []
    else:
        # 运行时探测每个模型是否真正可用（解决试用账号权限问题）
        print("🔍 检测可用模型...")
        probed = probe_model_availability(clients)

        # claude-only 模式：只保留 Claude 系列
        if model_mode == "claude-only":
            active_models = [m for m in probed if m.startswith("claude")]
        else:
            active_models = probed

        if not active_models:
            print("❌ 没有可用模型。请检查 API Key 和账户权限。")
            sys.exit(1)

        print(f"模式: 🟢 真实 LLM Agent")
        print(f"活跃模型: {', '.join(active_models)}")

    print(f"{'=' * 60}\n")

    # 生成 personas
    print("📋 生成消费者画像（7维度）...")
    personas = [generate_persona(i) for i in range(n_personas)]

    # 确定每个 Agent 使用的模型（v3 核心２轮流分配）
    if not use_mock:
        model_assignments = []
        for i in range(n_personas):
            model_assignments.append(active_models[i % len(active_models)])
    else:
        model_assignments = ["MOCK"] * n_personas

    # 运行 baseline（v3: Y1 修复 — 仅对活跃模型运行，带超时保护）
    baselines = {}
    if not use_mock:
        print("📏 生成 baseline 对比...")
        baselines = run_baseline(clients, product, active_models)
        for m, bl in baselines.items():
            if "error" not in bl:
                print(f"  {m} 直接预测: {bl.get('prediction','N/A')} (尝试率 {bl.get('try_rate','N/A')}%)")

    # 运行评估
    print(f"\n🤖 运行多 Agent 模拟...")
    results = []
    for i, (persona, model_key) in enumerate(zip(personas, model_assignments)):
        if use_mock:
            result = evaluate_mock(persona, product)
        else:
            result = evaluate_with_llm(clients, model_key, persona, product)
            # JSON 解析失败时重试 1 次（换一个 temperature）
            if result.get("error") == "json_parse_failed":
                time.sleep(0.3)
                result = evaluate_with_llm(clients, model_key, persona, product)
            # 限速：每 10 个请求暂停 0.5s，避免 rate limit
            if i % 10 == 9:
                time.sleep(0.5)

        results.append(result)

        if (i + 1) % 50 == 0 or (i + 1) == n_personas:
            errors = sum(1 for r in results if "error" in r)
            print(f"  进度: {i+1}/{n_personas} (错误: {errors})")

    errors = sum(1 for r in results if "error" in r)
    print(f"  完成: {n_personas}/{n_personas} (错误: {errors})\n")

    # 汇总
    print("📊 汇总分析...")
    summary = aggregate_results(results, personas, product["name"])

    # 生成报告
    print("📝 生成报告...")
    report_path, data_path, report_hash = generate_report(summary, product, baselines, output_dir)

    print(f"\n{'=' * 60}")
    print(f"✅ 模拟完成")
    print(f"  预测: {summary['prediction']}")
    print(f"  平均分: {summary['avg_score']}/10")
    print(f"  尝试意愿: {summary['try_rate']}%")
    if summary.get("model_stats") and len(summary["model_stats"]) > 1:
        print(f"  模型间一致性:")
        for m, s in summary["model_stats"].items():
            print(f"    {m}: 平均分 {s['avg_score']}, 尝试率 {s['try_rate']}%")
    print(f"  报告: {report_path}")
    print(f"  数据: {data_path}")
    print(f"  Hash: {report_hash}")
    if summary.get("is_mock"):
        print(f"  ⚠️  MOCK 模式 — 数据非真实 LLM 输出")
    print(f"{'=' * 60}")

    return summary


# ============================================================
# 6. 产品定义
# ============================================================

# 瑞幸酸奶昔 — 盲测对象
LUCKIN_YOGURT_AVOCADO = {
    "name": "牛油果羽衣酸奶昔",
    "brand": "瑞幸咖啡",
    "price": "约25元",
    "description": "牛油果+羽衣甘蓝+酸奶的健康榅念饮品，主打低卡轷食，绿色系高颜值杯身",
    "category": "非咖啡·健康饮品",
    "is_blind": True
}

LUCKIN_YOGURT_MANGO = {
    "name": "瓦尔登蓝芒果酸奶昔",
    "brand": "瑞幸咖啡",
    "price": "约25元",
    "description": "芒果+蓝色螺旋藻+酸奶的高颜值饮品，蓝色渐变视觉效果，主打拍照分享",
    "category": "非咖啡·健康饮品",
    "is_blind": True
}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TOMO Taste Lab v3.0 — 多模型消费者模拟引擎")
    parser.add_argument("--product", choices=["avocado", "mango", "both"], default="both",
                        help="要测试的产品")
    parser.add_argument("--n", type=int, default=500,
                        help="模拟消费者数量（默认500，最少100，确保统计可靠）")
    parser.add_argument("--output", default="./reports",
                        help="输出目录")
    parser.add_argument("--models", choices=["multi", "claude-only"], default="multi",
                        help="模型模式：multi=所有可用模型, claude-only=仅Claude")
    args = parser.parse_args()

    if args.n < 100:
        print("⚠️  最少需要 100 个消费者以保证统计可靠性。已自动调整为 100。")
        args.n = 100

    products = []
    if args.product in ["avocado", "both"]:
        products.append(LUCKIN_YOGURT_AVOCADO)
    if args.product in ["mango", "both"]:
        products.append(LUCKIN_YOGURT_MANGO)

    for product in products:
        run_simulation(product, n_personas=args.n, output_dir=args.output, model_mode=args.models)
        print()
 次（换一个 temperature）
            if result.get("error") == "json_parse_failed":
                time.sleep(0.3)
                result = evaluate_with_llm(clients, model_key, persona, product)
            # 限速：每 10 个请求暂停 0.5s，避免 rate limit
            if i % 10 == 9:
                time.sleep(0.5)

        results.append(result)

        if (i + 1) % 50 == 0 or (i + 1) == n_personas:
            errors = sum(1 for r in results if "error" in r)
            print(f"  进度: {i+1}/{n_personas} (错误: {errors})")

    errors = sum(1 for r in results if "error" in r)
    print(f"  完成: {n_personas}/{n_personas} (错误: {errors})\n")

    # 汇总
    print("📊 汇总分析...")
    summary = aggregate_results(results, personas, product["name"])

    # 生成报告
    print("📝 生成报告...")
    report_path, data_path, report_hash = generate_report(summary, product, baselines, output_dir)

    print(f"\n{'=' * 60}")
    print(f"✅ 模拟完成")
    print(f"  预测: {summary['prediction']}")
    print(f"  平均分: {summary['avg_score']}/10")
    print(f"  尝试意愿: {summary['try_rate']}%")
    if summary.get("model_stats") and len(summary["model_stats"]) > 1:
        print(f"  模型间一致性:")
        for m, s in summary["model_stats"].items():
            print(f"    {m}: 平均分 {s['avg_score']}, 尝试率 {s['try_rate']}%")
    print(f"  报告: {report_path}")
    print(f"  数据: {data_path}")
    print(f"  Hash: {report_hash}")
    if summary.get("is_mock"):
        print(f"  ⚠️  MOCK 模式 — 数据非真实 LLM 输出")
    print(f"{'=' * 60}")

    return summary


# ============================================================
# 6. 产品定义
# ============================================================

# 瑞幸酸奶昔 — 盲测对象
LUCKIN_YOGURT_AVOCADO = {
    "name": "牛油果羽衣酸奶昔",
    "brand": "瑞幸咖啡",
    "price": "约25元",
    "description": "牛油果+羽衣甘蓝+酸奶的健康榅念饮品，主打低卡轷食，绿色系高颜值杯身",
    "category": "非咖啡·健康饮品",
    "is_blind": True
}

LUCKIN_YOGURT_MANGO = {
    "name": "瓦尔登蓝芒果酸奶昔",
    "brand": "瑞幸咖啡",
    "price": "约25元",
    "description": "芒果+蓝色螺旋藻+酸奶的高颜值饮品，蓝色渐变视觉效果，主打拍照分享",
    "category": "非咖啡·健康饮品",
    "is_blind": True
}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TOMO Taste Lab v3.0 — 多模型消费者模拟引擎")
    parser.add_argument("--product", choices=["avocado", "mango", "both"], default="both",
                        help="要测试的产品")
    parser.add_argument("--n", type=int, default=500,
                        help="模拟消费者数量（默认500，最少100，确保统计可靠）")
    parser.add_argument("--output", default="./reports",
                        help="输出目录")
    parser.add_argument("--models", choices=["multi", "claude-only"], default="multi",
                        help="模型模式：multi=所有可用模型, claude-only=仅Claude")
    args = parser.parse_args()

    if args.n < 100:
        print("⚠️  最少需要 100 个消费者以保证统计可靠性。已自动调整为 100。")
        args.n = 100

    products = []
    if args.product in ["avocado", "both"]:
        products.append(LUCKIN_YOGURT_AVOCADO)
    if args.product in ["mango", "both"]:
        products.append(LUCKIN_YOGURT_MANGO)

    for product in products:
        run_simulation(product, n_personas=args.n, output_dir=args.output, model_mode=args.models)
        print()

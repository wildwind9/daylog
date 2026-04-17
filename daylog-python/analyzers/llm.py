"""LLM-based emotion and event tag extraction."""
import json
import os
import re
from typing import Iterable

from openai import AsyncOpenAI

from analyzers.local import extract_tags as local_extract

_client: AsyncOpenAI | None = None

EMOTION_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("开心", ("开心", "高兴", "快乐", "开心了", "笑死", "爽", "惊喜", "满足")),
    ("平静", ("平静", "安静", "舒服", "放松", "悠闲", "惬意")),
    ("期待", ("期待", "希望", "准备", "盼", "想要", "计划")),
    ("感动", ("感动", "温暖", "感谢", "谢谢", "治愈")),
    ("疲惫", ("累", "疲惫", "困", "熬夜", "加班", "忙到", "崩溃")),
    ("焦虑", ("焦虑", "紧张", "担心", "压力", "不安", "慌")),
    ("难过", ("难过", "伤心", "失落", "委屈", "想哭", "emo")),
    ("生气", ("生气", "愤怒", "气死", "无语", "烦", "讨厌")),
)

EVENT_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("工作", ("工作", "项目", "需求", "会议", "同事", "老板", "加班", "上线", "部署")),
    ("学习", ("学习", "课程", "考试", "读书", "论文", "作业", "复习")),
    ("家庭", ("家人", "爸", "妈", "父母", "孩子", "亲戚", "家庭")),
    ("朋友", ("朋友", "聚会", "聊天", "同学", "见面")),
    ("旅行", ("旅行", "出差", "酒店", "机场", "高铁", "火车", "景点", "路上")),
    ("美食", ("吃", "饭", "餐厅", "咖啡", "奶茶", "火锅", "早餐", "午餐", "晚餐")),
    ("运动", ("运动", "跑步", "健身", "游泳", "骑行", "散步")),
    ("健康", ("医院", "医生", "感冒", "发烧", "生病", "药", "体检")),
    ("娱乐", ("电影", "音乐", "演出", "游戏", "直播", "综艺")),
    ("生活", ("购物", "整理", "打扫", "搬家", "快递", "日常")),
)

MOOD_TAGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("😍", ("开心", "高兴", "快乐", "满足", "感动", "温暖", "治愈")),
    ("🤩", ("惊喜", "期待", "希望", "兴奋", "爽")),
    ("😊", ("平静", "安静", "舒服", "放松", "悠闲", "惬意")),
    ("😌", ("疲惫", "累", "困", "忙碌", "压力")),
    ("😢", ("焦虑", "紧张", "担心", "难过", "伤心", "失落", "委屈", "生气", "愤怒", "烦")),
)


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        )
    return _client


async def extract_tags(text: str, top_k: int = 4) -> list[str]:
    """Extract short tags focused on emotion and events.

    The LLM is the primary extractor. If it fails or returns unusable data, the
    local fallback still tries to produce emotion/event-oriented tags before
    falling back to general keywords.
    """
    if not text or not text.strip():
        return []

    cleaned_text = _clean_text(text)
    candidates = local_extract(cleaned_text, top_k=top_k + 4)

    try:
        tags = await _extract_with_llm(cleaned_text, candidates, top_k)
        if tags:
            return tags
    except Exception:
        pass

    return _fallback_extract(cleaned_text, candidates, top_k)


def infer_mood_from_tags(tags: Iterable[object]) -> str | None:
    """Map LLM emotion tags to the UI mood scale."""
    normalized_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
    for mood, keywords in MOOD_TAGS:
        if any(keyword in tag for tag in normalized_tags for keyword in keywords):
            return mood
    return None


async def _extract_with_llm(text: str, candidates: list[str], top_k: int) -> list[str]:
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    prompt = (
        "请从下面这段个人日记或社交平台内容中抽取标签。\n"
        "目标：标签要帮助用户回忆“当时的情绪”和“发生的事件”。\n"
        "规则：\n"
        f"1. 输出 {top_k} 个以内的中文短标签。\n"
        "2. 优先包含情绪或状态标签，例如：开心、疲惫、焦虑、平静、期待、难过。\n"
        "3. 同时包含事件或主题标签，例如：工作、朋友、美食、旅行、家庭、健康、学习。\n"
        "4. 不要输出人名、完整句子、标点符号、解释文字或英文分类前缀。\n"
        "5. 每个标签 2-4 个中文字符，不能重复。\n"
        f"候选关键词仅供参考，可不选择：{', '.join(candidates)}\n"
        f"内容：{text[:1200]}\n\n"
        '只输出 JSON 数组，例如：["疲惫", "工作", "朋友", "美食"]'
    )

    response = await _get_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一个严谨的个人日记标签抽取器，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=120,
    )

    raw = response.choices[0].message.content or ""
    return _normalize_tags(_parse_json_array(raw), top_k)


def _parse_json_array(raw: str) -> list[str]:
    start = raw.find("[")
    end = raw.rfind("]") + 1
    if start < 0 or end <= start:
        return []
    parsed = json.loads(raw[start:end])
    return parsed if isinstance(parsed, list) else []


def _fallback_extract(text: str, candidates: list[str], top_k: int) -> list[str]:
    hint_tags: list[str] = []
    for label, keywords in (*EMOTION_HINTS, *EVENT_HINTS):
        if any(keyword in text for keyword in keywords):
            hint_tags.append(label)
    return _normalize_tags([*hint_tags, *candidates], top_k)


def _normalize_tags(tags: Iterable[object], top_k: int) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        text = str(tag).strip()
        text = re.sub(r"^(情绪|事件|状态|主题|标签)\s*[:：]\s*", "", text)
        text = re.sub(r"[\s#，。、“”《》【】\[\]（）()：:；;,.!?！？/\\|]+", "", text)
        if not text or text in seen:
            continue
        if not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", text):
            continue
        seen.add(text)
        normalized.append(text)
        if len(normalized) >= top_k:
            break
    return normalized


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

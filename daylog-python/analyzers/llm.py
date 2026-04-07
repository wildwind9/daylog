"""LLM 标签提取：主力方案，兼容 OpenAI 协议（DeepSeek / 通义千问等）"""
import json
import os
from openai import AsyncOpenAI

from analyzers.local import extract_tags as local_extract

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=os.getenv("LLM_API_KEY", ""),
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        )
    return _client


async def extract_tags(text: str, top_k: int = 3) -> list[str]:
    """双引擎提取标签：LLM 优先，失败时降级到 jieba。

    Returns:
        标签列表，例如 ["工作", "美食", "心情"]
    """
    if not text or not text.strip():
        return []

    # 先用 jieba 获取候选词，给 LLM 作参考
    candidates = local_extract(text, top_k=top_k + 2)

    try:
        model = os.getenv("LLM_MODEL", "deepseek-chat")
        prompt = (
            f"请从以下内容中提取 {top_k} 个简洁的中文标签（每个标签 2-4 个字）。\n"
            f"候选词（供参考，可不选）：{', '.join(candidates)}\n"
            f"内容：{text[:500]}\n\n"
            f"只输出 JSON 数组格式，例如：[\"工作\", \"美食\", \"旅行\"]"
        )

        response = await _get_client().chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=100,
        )

        raw = response.choices[0].message.content.strip()
        # 提取 JSON 数组
        start = raw.find("[")
        end = raw.rfind("]") + 1
        tags = json.loads(raw[start:end])
        return [str(t) for t in tags[:top_k]]

    except Exception:
        # LLM 失败，降级到本地 jieba
        return candidates[:top_k]

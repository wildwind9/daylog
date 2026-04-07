"""本地 jieba 分词兜底方案：当 LLM 调用失败时使用"""
import jieba
import jieba.analyse


def extract_tags(text: str, top_k: int = 3) -> list[str]:
    """使用 TF-IDF 提取关键词作为标签候选"""
    if not text or not text.strip():
        return []
    keywords = jieba.analyse.extract_tags(text, topK=top_k, withWeight=False)
    return [kw for kw in keywords if len(kw) > 1]  # 过滤单字

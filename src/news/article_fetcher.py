"""
Background article text enrichment — NOT on the critical path.
The LLM verifier in matching/llm_verifier.py can operate on title + lede alone.
Full text enrichment improves match quality but its absence does not block the pipeline.
"""

import asyncio

import trafilatura
import newspaper

from src.schemas import Article
from src.utils import DiskCache, get_logger


class ArticleFetcher:
    def __init__(
        self,
        cache_dir: str = "data/.cache/articles",
        max_concurrent: int = 10,
    ) -> None:
        self._cache = DiskCache(cache_dir)
        self._sem = asyncio.Semaphore(max_concurrent)
        self._log = get_logger(__name__)

    def _fetch_sync(self, url: str) -> str | None:
        # Primary: trafilatura
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded)
                if text:
                    return text
        except Exception:
            pass
        # Fallback: newspaper3k
        try:
            art = newspaper.Article(url)
            art.download()
            art.parse()
            if art.text:
                return art.text
        except Exception:
            pass
        return None

    async def fetch_text(self, url: str) -> tuple[str | None, bool]:
        cache_key = f"article_text:{url}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            text = cached.decode() or None
            return text, text is not None

        loop = asyncio.get_running_loop()
        async with self._sem:
            text = await loop.run_in_executor(None, self._fetch_sync, url)

        self._cache.set(cache_key, (text or "").encode())
        return text, text is not None

    async def enrich_batch(self, articles: list[Article]) -> list[Article]:
        async def _one(article: Article) -> Article:
            if article.text_available:
                return article
            text, success = await self.fetch_text(article.url)
            lede = article.lede
            if lede is None and text:
                lede = " ".join(text.split()[:150])
            return article.model_copy(update={
                "body_text": text,
                "lede": lede,
                "text_available": success,
            })

        return list(await asyncio.gather(*[_one(a) for a in articles]))

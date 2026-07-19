import json
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def load_gdelt_articles(gdelt_dir: str) -> pd.DataFrame:
    paths = list(Path(gdelt_dir).rglob("*.parquet"))
    if not paths:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)


def load_feed_articles(feeds_dir: str) -> pd.DataFrame:
    paths = list(Path(feeds_dir).rglob("*.parquet"))
    if not paths:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)


def _build_gdelt_titles_vectorized(sub: pd.DataFrame) -> pd.Series:
    """Vectorized GDELT title construction from entities+themes.

    For each GDELT article whose 'title' is just a URL, builds a semantic snippet:
    source-domain + entity names (up to 20) + GDELT theme names (up to 10).
    Returns a Series of strings aligned to sub's index.
    """
    import numpy as np

    # Start with source domain
    sources = sub["source"].fillna("").astype(str)

    def _join_list_col(col: pd.Series, limit: int, transform=None) -> pd.Series:
        def _proc(val):
            if val is None:
                return ""
            if isinstance(val, (list, np.ndarray)):
                items = [str(x) for x in val[:limit]]
            elif isinstance(val, str):
                return ""
            else:
                try:
                    items = [str(x) for x in list(val)[:limit]]
                except Exception:
                    return ""
            if transform:
                items = [transform(x) for x in items]
            return " ".join(items)
        return col.map(_proc)

    entity_text = _join_list_col(sub.get("entities", pd.Series(index=sub.index)), limit=20)
    theme_text = _join_list_col(
        sub.get("themes", pd.Series(index=sub.index)),
        limit=10,
        transform=lambda t: t.split(",")[0].replace("_", " ").lower(),
    )

    combined = (sources + " " + entity_text + " " + theme_text).str.strip().str.slice(0, 512)
    return combined


def normalize_and_deduplicate(
    gdelt_df: pd.DataFrame, feed_df: pd.DataFrame
) -> pd.DataFrame:
    if gdelt_df.empty and feed_df.empty:
        return pd.DataFrame()
    elif gdelt_df.empty:
        combined = feed_df.copy()
    elif feed_df.empty:
        combined = gdelt_df.copy()
    else:
        # feeds first → feed version survives drop_duplicates(keep="first")
        combined = pd.concat([feed_df, gdelt_df], ignore_index=True)

    deduped = combined.drop_duplicates(subset=["article_id"], keep="first").reset_index(drop=True)

    # For GDELT articles where title == url (no real title), replace with entity+theme text
    if "title" in deduped.columns and "url" in deduped.columns:
        is_gdelt_no_title = deduped["title"].fillna("") == deduped["url"].fillna("")
        if is_gdelt_no_title.any():
            gdelt_sub = deduped[is_gdelt_no_title]
            deduped.loc[is_gdelt_no_title, "title"] = _build_gdelt_titles_vectorized(gdelt_sub).values

    bad = (deduped["timestamp_precision"] == "minute") & deduped["published_at"].isna()
    if bad.any():
        raise ValueError(
            f"Found {bad.sum()} article(s) with timestamp_precision='minute' and published_at=None"
        )

    return deduped


def _partition_key(row) -> tuple[int | None, int | None]:
    if pd.notna(row.get("published_at")):
        dt = pd.Timestamp(row["published_at"])
        return dt.year, dt.month
    try:
        meta = json.loads(row.get("raw_metadata_json", "{}"))
        date_int = str(meta.get("date_int", ""))
        if len(date_int) >= 6:
            return int(date_int[:4]), int(date_int[4:6])
    except Exception:
        pass
    return None, None


def write_unified_corpus(df: pd.DataFrame, out_dir: str) -> None:
    out_root = Path(out_dir)
    groups: dict[tuple, list] = defaultdict(list)
    for _, row in df.iterrows():
        groups[_partition_key(row)].append(row.to_dict())

    for (year, month), records in groups.items():
        if year is None:
            part_dir = out_root / "year=unknown" / "month=unknown"
        else:
            part_dir = out_root / f"year={year}" / f"month={month:02d}"
        part_dir.mkdir(parents=True, exist_ok=True)
        pq.write_table(
            pa.Table.from_pandas(pd.DataFrame(records)),
            part_dir / "part-0.parquet",
        )

from pathlib import Path

import duckdb
import pandas as pd


def get_connection(db_path: str = ":memory:") -> duckdb.DuckDBPyConnection:
    return duckdb.connect(db_path)


_VIEW_MAP = {
    "trades":        ("polymarket", "trades"),
    "bars_1min":     ("polymarket", "bars_1min"),
    "gdelt_gkg":     ("news", "gdelt_gkg"),
    "feed_articles": ("news", "feeds"),
}


def register_parquet_views(
    conn: duckdb.DuckDBPyConnection,
    paths_config: dict,
) -> None:
    for view_name, (section, key) in _VIEW_MAP.items():
        raw_path = paths_config.get(section, {}).get(key)
        if raw_path is None:
            continue
        path = Path(raw_path)
        if not path.exists():
            continue
        glob = str(path / "**" / "*.parquet")
        conn.execute(
            f"CREATE OR REPLACE VIEW {view_name} AS "
            f"SELECT * FROM read_parquet('{glob}', hive_partitioning=True)"
        )


def query_to_df(conn: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return conn.execute(sql).df()

import numpy as np
import faiss


def build_index(embeddings: np.ndarray) -> faiss.IndexFlatIP:
    vecs = embeddings.astype(np.float32)
    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(vecs)
    return index


def save_index(index: faiss.IndexFlatIP, path: str) -> None:
    faiss.write_index(index, path)


def load_index(path: str) -> faiss.IndexFlatIP:
    return faiss.read_index(path)


def search(
    index: faiss.IndexFlatIP, query: np.ndarray, k: int
) -> tuple[np.ndarray, np.ndarray]:
    q = query.astype(np.float32)
    if q.ndim == 1:
        q = q[None, :]
    return index.search(q, k)

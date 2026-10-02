import re
import zlib

import numpy as np
import pytest

DIM = 256


def embed_falso(textos: list[str], tipo: str = "documento") -> np.ndarray:
    """Bolsa de palabras con hashing: determinista y sin red."""
    m = np.zeros((len(textos), DIM), dtype="float32")
    for i, t in enumerate(textos):
        for w in re.findall(r"\w+", t.lower()):
            m[i, zlib.crc32(w.encode()) % DIM] += 1
    return m


@pytest.fixture
def embed():
    return embed_falso

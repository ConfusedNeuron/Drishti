from __future__ import annotations
import math

import numpy as np


def clean_json(obj):
    if isinstance(obj, float):
        return None if not math.isfinite(obj) else obj
    if isinstance(obj, dict):
        return {k: clean_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_json(v) for v in obj]
    # numpy scalars leak through dataclasses.asdict() and break FastAPI's
    # encoder (np.int64 is not an int subclass; np.float64 is a float subclass
    # so non-finite numpy floats also need the math.isfinite guard).
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return None if not math.isfinite(v) else v
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return [clean_json(v) for v in obj.tolist()]
    return obj

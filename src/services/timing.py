# src/services/timing.py
from contextlib import contextmanager
from time import perf_counter

@contextmanager
def stage(timings: dict, name: str):
    t0 = perf_counter()
    try:
        yield
    finally:
        timings[name] = round(timings.get(name, 0.0) + (perf_counter() - t0), 3)

# src/services/rate_limit.py
from __future__ import annotations
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from fastapi import HTTPException

try:
    import redis  # type: ignore
except Exception:
    redis = None  # fallback se não estiver instalado

def _seconds_until_midnight_utc(now: Optional[datetime] = None) -> Tuple[int, int]:
    now = now or datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).date()
    reset_dt = datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc)
    return int((reset_dt - now).total_seconds()), int(reset_dt.timestamp())

class RateLimiter:
    """
    - Contador diário por usuário (reseta no UTC midnight).
    - Redis em produção; fallback em memória para dev.
    """
    def __init__(self, redis_url: Optional[str] = None):
        self.client = None
        if redis_url and redis is not None:
            self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._mem = {}  # key -> (count, exp_ts)

    def hit(self, user_id: str, limit: int) -> Tuple[int, int]:
        """Incrementa a cota; lança 429 se passar. Retorna (remaining, reset_ts)."""
        ttl, reset_ts = _seconds_until_midnight_utc()
        key = f"rate:{user_id}:{datetime.now(timezone.utc):%Y%m%d}"

        if self.client:
            new_val = self.client.incr(key)
            if new_val == 1:
                self.client.expire(key, ttl)  # define TTL no primeiro hit do dia
            if new_val > limit:
                # volta 1 para não contaminar o contador
                try:
                    self.client.decr(key)
                except Exception:
                    pass
                raise HTTPException(status_code=429, detail="Limite diário atingido. Tente novamente após o reset.")
            remaining = max(0, limit - new_val)
            return remaining, reset_ts

        # Fallback em memória (dev)
        now = time.time()
        count, exp = self._mem.get(key, (0, now + ttl))
        if exp < now:  # expirado -> reinicia
            count, exp = 0, now + ttl
        count += 1
        if count > limit:
            # regrava sem o incremento excedente
            self._mem[key] = (count - 1, exp)
            raise HTTPException(status_code=429, detail="Limite diário atingido. Tente novamente após o reset.")
        self._mem[key] = (count, exp)
        remaining = limit - count
        return remaining, int(exp)

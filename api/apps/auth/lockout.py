"""Progressive lock of password logins per email: after LOCK_AFTER failures in a row the email
waits 1, then 5, then 15 minutes (counting locks of the last 24 h), whatever IP the attempts come
from. Unknown emails are locked the same way so the answer does not reveal which ones exist. The
owner gets an email on the first lock."""

from apps.users.models import User
from apps.users.tasks import send_templated_email
from kuulis.core.exceptions import AppError
from kuulis.core.redis import redis_client
from kuulis.settings import settings

LOCK_AFTER = 5
LOCK_MINUTES = (1, 5, 15)
FAILURE_WINDOW_SECONDS = 15 * 60
LEVEL_WINDOW_SECONDS = 24 * 3600
_PREFIX = f"{settings.APP_ENV}:auth:login"


class LoginLockedError(AppError):
    status_code = 429
    code = "login_locked"
    message = "Too many failed attempts, try again later"


def _locked(seconds: int) -> LoginLockedError:
    return LoginLockedError(details={"retry_after": seconds, "minutes": -(-seconds // 60)})


def _keys(email: str) -> tuple[str, str, str]:
    email = email.strip().lower()
    return f"{_PREFIX}:fails:{email}", f"{_PREFIX}:lock:{email}", f"{_PREFIX}:level:{email}"


async def ensure_not_locked(email: str) -> None:
    _, lock, _ = _keys(email)
    seconds = await redis_client.ttl(lock)
    if seconds > 0:
        raise _locked(seconds)


async def record_failure(email: str, user: User | None) -> None:
    fails, lock, level = _keys(email)
    count = await redis_client.incr(fails)
    if count == 1:
        await redis_client.expire(fails, FAILURE_WINDOW_SECONDS)
    if count < LOCK_AFTER:
        return
    step = await redis_client.incr(level)
    await redis_client.expire(level, LEVEL_WINDOW_SECONDS)
    seconds = LOCK_MINUTES[min(step, len(LOCK_MINUTES)) - 1] * 60
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.set(lock, "1", ex=seconds)
        pipe.delete(fails)
        await pipe.execute()
    if user is not None and step == 1:
        await send_templated_email.kiq(
            user.email, "login_locked", user.locale, user.full_name, settings.FRONTEND_URL
        )
    raise _locked(seconds)


async def record_success(email: str) -> None:
    fails, _, level = _keys(email)
    await redis_client.delete(fails, level)

import time
import logging
from functools import wraps
from typing import Callable, Type, Tuple


def retry_on_exception(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    logger: logging.Logger = None
):
    """
    Decorator to retry a function on exception with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exception types to catch and retry
        logger: Logger instance for logging retry attempts

    Returns:
        Decorated function that retries on specified exceptions
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        if logger:
                            logger.error(
                                f"Function {func.__name__} failed after {max_retries} retries",
                                extra={"error": str(e)}
                            )
                        raise

                    if logger:
                        logger.warning(
                            f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries}), "
                            f"retrying in {current_delay}s...",
                            extra={"error": str(e)}
                        )

                    time.sleep(current_delay)
                    current_delay *= backoff

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


class RateLimiter:
    """
    Simple rate limiter to prevent hitting API rate limits.
    """

    def __init__(self, max_calls: int = 10, period: float = 1.0):
        """
        Initialize rate limiter.

        Args:
            max_calls: Maximum number of calls allowed in the period
            period: Time period in seconds
        """
        self.max_calls = max_calls
        self.period = period
        self.calls = []

    def __call__(self, func: Callable):
        """Decorator to rate limit a function."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()

            # Remove old calls outside the time window
            self.calls = [call_time for call_time in self.calls if now - call_time < self.period]

            if len(self.calls) >= self.max_calls:
                # Calculate how long to wait
                oldest_call = self.calls[0]
                sleep_time = self.period - (now - oldest_call)

                if sleep_time > 0:
                    time.sleep(sleep_time)

                # Remove the oldest call
                self.calls.pop(0)

            # Record this call
            self.calls.append(time.time())

            return func(*args, **kwargs)

        return wrapper

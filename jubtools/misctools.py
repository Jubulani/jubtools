import time


# Timer class. Use like:
#    with misctools.Timer() as timer:
#        some_task()
#    logger.info(f"Time taken: {timer.elapsed:.2f}ms")
class Timer:
    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = (time.time() - self._start) * 1000  # Value in ms

import time

import pytest

from jubtools.misctools import Timer


def test_timer_elapsed():
    with Timer() as timer:
        # Simulate some task
        time.sleep(0.01)
    elapsed_time = timer.elapsed
    assert elapsed_time == pytest.approx(1, abs=10)

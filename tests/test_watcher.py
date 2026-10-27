import asyncio
import dataclasses
from datetime import datetime, timedelta, timezone

from app.watcher import Watcher


class SequenceHA:
    def __init__(self, states):
        self.states = list(states)

    async def live(self):
        soc, charging = self.states.pop(0)
        return {"available": True, "values": {"soc": soc}, "raw": {"charging": charging}, "units": {}}


class FakeSync:
    def __init__(self):
        self.bursts = 0

    def trigger_burst(self):
        self.bursts += 1


def run(settings, db, states):
    sync = FakeSync()
    watcher = Watcher(dataclasses.replace(settings, charging_value="charging"), db, SequenceHA(states), sync)
    start = datetime(2026, 10, 1, 8, tzinfo=timezone.utc)

    async def go():
        for i in range(len(states)):
            await watcher.poll_once(now=start + timedelta(minutes=i))

    asyncio.run(go())
    return sync


def test_end_of_charging_triggers_one_burst(settings, db):
    sync = run(settings, db, [(40, "charging"), (55, "charging"), (70, "complete"), (70, "complete")])
    assert sync.bursts == 1


def test_offline_in_between_still_detected(settings, db):
    sync = run(settings, db, [(40, "charging"), (None, "unavailable"), (70, "stopped")])
    assert sync.bursts == 1


def test_no_burst_without_charging(settings, db):
    sync = run(settings, db, [(60, "disconnected"), (58, "disconnected")])
    assert sync.bursts == 0


def test_readings_only_on_change(settings, db):
    run(settings, db, [(40, "disconnected"), (40, "disconnected"), (39.5, "disconnected"), (38, "disconnected")])
    values = [v for _, v in db.readings_since("soc", datetime(2026, 1, 1, tzinfo=timezone.utc))]
    assert values == [40, 38]

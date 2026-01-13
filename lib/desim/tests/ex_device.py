from desim.event import EventTime, EventValue
from desim.signal import SIG_UNDEFINED
from desim.device import Device


class TrialDevice(Device):
    def __init__(self, name: str, delay: float = 1.5):
        super().__init__(name)
        self.delay = delay
        self.add_output("out1")

    @Device.input
    def in1(self, time: EventTime, value: EventValue):  # type: ignore
        if self.state == "idle":
            self.out1.update(time, SIG_UNDEFINED)  # type: ignore
        self.state = "changing"
        self._time_change_complete = time.time + self.delay
        self._latest_value = value
        self.act(self._time_change_complete, "new_output")

    @Device.action
    def new_output(self, time: EventTime, value: EventValue, context=None):  # type: ignore
        assert self.state == "changing"
        if time.time >= self._time_change_complete:
            self.out1.update(time, self._latest_value)  # type: ignore
            self.state = "idle"


def run():
    dev = TrialDevice("test")
    dev.trace("in1")
    dev.trace("out1")
    dev.trace("new_output")
    print("\ncalling..")
    events = dev.in1(1.0, 1)
    events += dev.in1(1.3, 2)
    while events:
        event, events = events[0], events[1:]
        print("Next", event)
        new_events = event.action()
        if new_events:
            events += new_events
    print("Done")


run()

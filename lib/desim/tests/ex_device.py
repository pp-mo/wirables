from desim.event import Event
from desim.signal import SIG_UNDEFINED, Signal
from desim.device import Device


class TrialDevice(Device):
    def __init__(self, name: str, delay: float = 1.5):
        super().__init__(name)
        self.delay = delay
        self.out1 = self.add_output("out1")

    @Device.input
    def in1(self, time, value):
        if self.state == "idle":
            self.out("out1", SIG_UNDEFINED)
        self.state = "changing"
        self._time_change_complete = time.time + self.delay
        self._latest_value = value
        self.act(self._time_change_complete, "new_output")

    @Device.action
    def new_output(self, time):
        assert self.state == "changing"
        if time.time >= self._time_change_complete:
            self.out("out1", self._latest_value)
            self.state = "idle"


def run():
    dev = TrialDevice("test")
    print("\ncalling..")

    sig = Signal("s1")
    sig.connect(dev.in1)

    sig_out = Signal("sig_out")
    dev.out1.connect(sig_out.update)

    events = []
    events += [Event(1.0, dev.in1, 1)]

    sig.trace()
    dev.trace("in1")
    dev.trace("out1")
    dev.trace("new_output")
    dev.trace("act")
    dev.trace("update")
    sig_out.trace()

    # A different way of providing a second input action : direct Event construction
    # NB **also** calls via the signal interface, instead of the device input
    events += [Event(1.3, sig.update, 2)]
    while events:
        events = sorted(events, key=lambda e: e.time)
        event, events = events[0], events[1:]
        print("\nNEXT:", event)
        new_events = event.action()
        if new_events:
            events += new_events
            print("resulting: ")
            for event in new_events:
                print("  - ", event)

    print("Done")


run()

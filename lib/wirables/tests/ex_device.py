from wirables import Device, Event, SIG_UNDEFINED, Signal, Sequencer


class TrialDevice(Device):
    STATES = ["idle", "changing"]
    TIMINGS = {"t_delay": 1.5}

    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)
        self.out1 = self.add_output("out1")

    @Device.input
    def in1(self, time, value):
        if self.state == "idle":
            self.out("out1", SIG_UNDEFINED)
        self.xto("idle", "changing")
        self._time_change_complete = time.time + self.t_delay
        self._latest_value = value
        self.act("newdata", self._time_change_complete)

    @Device.action
    def act_newdata(self, time):
        self.xto("changing")
        if time.time >= self._time_change_complete:
            self.out("out1", self._latest_value)
            self.xto("changing", "idle")


def run():
    dev = TrialDevice("test")
    print("\ncalling..")

    sig = Signal("s1")
    sig.connect(dev.in1)

    sig_out = Signal("sig_out")
    dev.out1.connect(sig_out.update)

    events = []
    events += [Event(1.0, dev.in1, 1)]

    # sig.trace()
    dev.trace("*")
    # dev.trace("act")
    # dev.trace("act_value_out")
    # dev.trace("out")
    # dev.trace("xto")
    # dev.trace("in1")
    # dev.trace("out1")
    # dev.trace("act_newdata")
    # dev.trace("act")
    # dev.trace("update")
    # sig_out.trace()

    seq = Sequencer()
    seq.add(events)
    seq.verbose = True
    # seq.run()
    seq.interact()

    # # A different way of providing a second input action : direct Event construction
    # # NB **also** calls via the signal interface, instead of the device input
    # events += [Event(1.3, sig.update, 2)]
    # while events:
    #     events = sorted(events, key=lambda e: e.time)
    #     event, events = events[0], events[1:]
    #     print("\nNEXT:", event)
    #     new_events = event.action()
    #     if new_events:
    #         events += new_events
    #         print("resulting: ")
    #         for event in new_events:
    #             print("  - ", event)

    print("Done")


run()

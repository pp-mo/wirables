from wirables import Event, EventTime
from wirables.signal import TimeTypes


__all__ = ["Sequencer"]


class Sequencer:
    def __init__(self, events: list[Event] | None = None):
        self._events = events or []
        self.time: EventTime = EventTime(0.0)
        self.verbose = False

    def _sort(self):
        self._events = sorted(self._events, key=lambda event: event.time)

    @property
    def events(self) -> list[Event]:
        self._sort()
        return self._events

    def add(self, event_or_events: Event | list[Event]):
        match event_or_events:
            case Event():
                events = [event_or_events]
            case _:
                events = event_or_events
        self._events.extend(events)

    def run(
        self,
        steps: int | None = None,
        *,
        period: TimeTypes | None = None,
        stop: TimeTypes | None = None,
        verbose=False,
    ):
        verbose |= self.verbose
        if steps is None:
            halt_steps = -1
        else:
            halt_steps = int(steps)
        if period is not None:
            stop = self.time + EventTime(period)
        while self._events:
            self._sort()
            events = self._events
            event, events = events[0], events[1:]
            next_time = event.time
            if next_time < self.time:
                msg = f"Unexpected backwards step : time {self.time} --> {next_time}."
                raise ValueError(msg)
            self.time = next_time
            if stop is not None:
                stop_time = EventTime(stop)
                # TODO: work out why MyPy still doesn't like this?
                if self.time >= stop_time:  # type: ignore[operator]
                    if verbose:
                        print(f"Halted at set time: {self.time} >= {stop_time}.")
                    break
            if halt_steps >= 0:
                halt_steps -= 1
                if halt_steps < 0:
                    if verbose:
                        print(f"Halted after {steps} steps.")
                    break
            if verbose:
                print("\nNEXT:", event)

            new_events = event.action()

            if new_events:
                events += new_events
                if verbose:
                    print("resulting: ")
                    for event in new_events:
                        print("  - ", event)

            self._events = events
            if not self._events:
                print("Halted with no more events.")
                break

    def step(self, steps: int = 1, verbose: bool = False):
        self.run(steps=steps, verbose=verbose)

    def until(self, time: TimeTypes, verbose: bool = False):
        self.run(stop=time, verbose=verbose)

    def awhile(self, time: TimeTypes, verbose: bool = False):
        self.run(period=time, verbose=verbose)

    def interact(self):
        while True:
            prompt = "\n n=steps / t.t=for / -t.t=until / *=all / ?\n: "
            ask = input(prompt).lower().strip()
            if ask == "":
                # Default is single step
                ask = "1"
            if ask[0] == "q":
                break
            elif ask[0] == "*":
                self.run()
            elif ask[0].isdigit():
                if "." in ask:
                    ask = float(ask)
                    if ask < 0.0:
                        self.run(stop=-ask)
                    else:
                        self.run(period=ask)
                else:
                    self.run(int(ask))
            else:
                print("Options:\n  Q=quit ''=1 n=steps  f.f=period -f.f=until")
            if not self._events:
                break

"""
Fundamental simulation event classes.

EventTime and EventValue are types used for fundamental signalling concepts.

The EventClient defines the basic type of callback function used to implement event
passing, which can also return further Events to be actioned.

An Event describes a callback operation to be performed, at a given associated
EventTime with an associated EventValue.
"""

from typing import Callable, Any


class EventTime:
    time: float = 0.0
    priority: int = 0

    def __init__(self, time: int | float | "EventTime" = 0, priority: int = 0):
        if isinstance(time, EventTime):
            self.time, self.priority = time.time, time.priority
        else:
            self.time = float(time)
            self.priority = int(priority)

    def __repr__(self):
        result = f"EventTime({self.time}"
        if self.priority != 0:
            result += f", priority={self.priority}"
        result += ")"
        return result

    def __str__(self):
        result = str(self.time)
        if self.priority != 0:
            result += f"(priority={self.priority})"
        return result

    def __eq__(self, other):
        return self.time == other.time and self.priority == other.priority

    def __lt__(self, other):
        if not isinstance(other, EventTime):
            other = EventTime(other)
        t1, t2 = self.time, other.time
        p1, p2 = self.priority, other.priority
        return t1 < t2 or (t1 == t2 and p1 > p2)


class EventValue:
    value: int | float | str = 0

    def __init__(self, value: "EventValue" | int | float | str = 0):
        if isinstance(value, EventValue):
            self.value = value.value
        else:
            self.value = value

    def __str__(self):
        return repr(self.value)

    def __eq__(self, other: Any):
        if not isinstance(other, EventValue):
            other = EventValue(other)
        return self.value == other.value


EventClient = Callable[[EventTime, EventValue, Any], list["Event"] | None]


class Event:
    time: EventTime
    value: EventValue
    call: EventClient
    context: Any = None
    # TODO: a suitable constructor will be wanted.

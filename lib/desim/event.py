"""
Fundamental simulation event classes.

EventTime and EventValue are types used for fundamental signalling concepts.

The EventClient defines the basic type of callback function used to implement event
passing, which can also return further Events to be actioned.

An Event describes a callback operation to be performed, at a given associated
EventTime with an associated EventValue.
"""

from __future__ import annotations
from functools import total_ordering
from typing import Any, Callable

type TimeTypes = EventTime | int | float


@total_ordering
class EventTime:
    """Class to define event times.

    This ensures consistent typing of EventTimes, assists in converting basic float/int
    to an EventTime, and also defines how the optional 'priority' affects ordering.

    We also enable EventTimes comparison and combination with int/float,
    and print like a plain number (except when priority != 0).
    """

    time: float = 0.0
    priority: int = 0

    def __init__(self, time: TimeTypes, priority: int = 0):
        match time:
            case EventTime():
                self.time, self.priority = time.time, time.priority
            case int() | float():
                self.time = float(time)
                self.priority = int(priority)
            case _:
                raise TypeError(f"Argument 'time', {time!r} has unsupported type.")

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
        if not isinstance(other, EventTime):
            other = EventTime(other)
        return self.time == other.time and self.priority == other.priority

    def __lt__(self, other):
        if not isinstance(other, EventTime):
            other = EventTime(other)
        t1, t2 = self.time, other.time
        p1, p2 = self.priority, other.priority
        return t1 < t2 or (t1 == t2 and p1 > p2)

    # TODO: implement addition with ordinary numbers  (not yet used/tested)
    def __add__(self, other):
        if isinstance(other, EventTime):
            offset = other.time
        else:
            offset = other
        return EventTime(time=self.time + offset, priority=0)

    def __radd__(self, other):
        return self.__add__(other)


type ValueTypes = EventValue | int | float | str


class EventValue:
    """Class to ensure uniform representation of event values.

    These are comparable with the original int / float / str values contained, and print
    in a similar way (but strings in quotes).
    Arithmetic is *not* defined.
    """

    value: int | float | str = 0

    def __init__(self, value: ValueTypes):
        match value:
            case EventValue():
                self.value = value.value
            case int() | float() | str():
                self.value = value
            case _:
                raise TypeError(f"Argument 'value', {value!r} has unsupported type.")

    def __repr__(self):
        return f"EventValue({self.value!r})"

    def __str__(self):
        return repr(self.value)

    def __eq__(self, other):
        if not isinstance(other, EventValue):
            other = EventValue(other)
        return self.value == other.value


EventClient = Callable[[EventTime, EventValue | None, Any], list["Event"] | None]


class Event:
    time: EventTime
    callback: EventClient
    value: EventValue | None
    context: Any = None

    def __init__(
        self,
        time: TimeTypes,
        call: EventClient,
        value: ValueTypes | None = None,
        context: Any = None,
    ):
        self.time = EventTime(time)
        self.callback = call
        if value is None:
            self.value = None
        else:
            self.value = EventValue(value)
        self.context = context

    def __repr__(self):
        return f"Event(time={self.time}, value={self.value}, call={self.callback!r})"

    def action(self):
        # As for hook callbacks, we are working with a generalised call description,
        # but the actual called function may not support all the potential args.
        # So only pass the args which are positively defined (not None)
        args = (self.time,)
        if self.context is not None or self.value is not None:
            args += (self.value,)
        if self.context is not None:
            args += (self.context,)
        results = self.callback(*args)
        return results


PostEventTypes = Event | list[Event] | None

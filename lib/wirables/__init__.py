"""
Discrete Event Simulation

Provides Devices, with inputs, outputs and internal state, and which communicate via
Signals.

A Signal has an EventValue state, and communicates changes to this at given EventTime-s.

A device's "input"s can be connected to signals, and their "output"s *are* Signals.
A device can also have 'actions', which are internal changes occurring at a scheduled
EventTime.

An Event specifies a particular operation (a function call) at a particular EventTime,
also with optional associated EventValue and user 'context' values.

A Sequencer maintains a list of Events and executes them in sequence.
All Event calls can return additional (future) events, to be added to the sequencer.
A sequencer can run: for ever; for a number of steps; or to a certain time.
It can also be controlled interactively with keyboard input.

In practice, events are calls to: a signal "update", a device "input" or a device "action"
method.
Signal update calls only ever call their connections (e.g. device inputs or trace
routines), but device event-triggered calls ("input"s and "action"s) may also call one of
three standard methods:
  * 'out' changes a device output (which is a Signal.update call)
  * 'xto' changes the device "state"
  * 'act' schedules a future "action" callback on the (same) device.

"""

# Import the major commonly used definitions into the root module.
from .signal import Signal, SIG_ZERO, SIG_START_DEFAULT, SIG_UNDEFINED
from .event import Event, EventTime, EventValue
from .device import Device
from .sequencer import Sequencer

__all__ = [
    "Device",
    "Event",
    "EventTime",
    "EventValue",
    "SIG_START_DEFAULT",
    "SIG_UNDEFINED",
    "SIG_ZERO",
    "Sequencer",
    "Signal",
]

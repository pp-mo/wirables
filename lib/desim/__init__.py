"""
Discrete Event Simulation.

Proposed:
    * a device output is a signal
    * a device input is an EventClient -- but see below...
    * an Event is a (time, value, call, context)
        -- but the time can have (optional) priority, in addition to a float value
    * an EventClient is Callable[[EventTime, EventValue, context], None]

To trigger stuff, either Signal.update() or Device.<input>().
A Signal.update()
  performs connection calls, which may include Device.<input> calls,
  so it *could* return new events.

A Device.<input>() will likewise return List[Event]

??queries??
    - an input call input(time, value) definitely does *not* have context.
    - likewise, an action(time) doesn't need value OR context.


Basic classes:

A Device is an object with :
    its own name (instance)
    a parent scheduler
    various internal state variables (private + arbitrary)
    self.inputs :: Dict[str, callable]
        are named instance methods with the general signature (time, value)
        are decorated with @Device.input for common behaviour
        can be connected, for a specific instance, to an input Signal
            with Device.connect_input(name, signal)
                [[==convenience for signal.connect(Device.input_name)]]
    self.outputs :: Dict[str, Signal]
        are Signals
        are created in the init with Device.define_output(name, start_value=None)
        are accessible as named properties of the object.
    self.actions :: Dict[str, callable]
        are named event methods encoding a device state transition
        have a generic signature (time)
        are decorated with @Device.action for common behaviour
        can be scheduled with Device.act(time, action_name)
            [[==convenience for device.scheduler.add(Event(time, device.action)]]

Device.connect_input(name, signal)
Device.act(time, action_name)

Device inputs, outputs and action calls, can all be "hooked" by adding a hook to a named
component with Device.hook(component_name, hook_client, **kwargs)  [[and Device.unhook]]
The hook_client generic signature is (time, **kwargs) for actions,
    and (time, value, **kwargs) for inputs/outputs

Again, tracing can be defined as a "standard operation", using hooking..

Device.trace(name)  --> Device._trace_input/output/action(name)
(and Device.untrace)
def Device.trace(name):
    hooks = self.__dict__.setdefault("_hooks", [])
    if name in self.inputs
        def _inner_call(time, value):
            print(f"time={time} INPUT UPDATE {self.name}{name} = {state}")
    if name in self.outputs:
        def _inner_call(time, signal):
            print(f"time={time} OUTPUT UPDATE {self.name}{name} : {signal.previous_state} -> {signal.state}")
        getattr(self,
    elif name in self.actions:
        def _inner_call(time, signal):
            print(f"time={time} ACTION {self.name}{name}")
    hooks.append(_inner_call)

An Event specifies a Call to happen at a given time + priority.
Event(time: float | (float, int), call: callable, **kwargs)
    .call(time) -> List[Event] | None

 # ??? when called, of 'call' returns further events **these are scheduled**
 # ??? not really necessary ???
    - most events are device actions, which call Device.act

A Scheduler contains a list of Events, which are executed in (time, priority) order.
    Each (the call can schedule further events)
Scheduler(events)
  .add_event(Event | (time: float | (float, int), call: callable, **kwargs)))
  .run(start=0, end=-1)
"""

from .signal import Signal, SIG_ZERO, SIG_UNDEFINED

__all__ = [
    "SIG_UNDEFINED",
    "SIG_ZERO",
    "Signal",
]

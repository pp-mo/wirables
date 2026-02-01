from contextlib import contextmanager
from functools import wraps
import inspect
from typing import Any, Callable

from wirables import (
    SIG_UNDEFINED,
    SIG_START_DEFAULT,
    Signal,
    Event,
    EventTime,
    EventValue,
)
from wirables.signal import EventClient, SignalConnection, TimeTypes, ValueTypes


InputAndActionClassCallsType = Callable[
    ["Device", EventTime, EventValue | None, Any], list[Event] | None
]

InputAndActionInstanceCallsType = Callable[
    [EventTime, EventValue | None, Any], list[Event] | None
]

__all__ = ["Device"]


class Device:
    """
    Object to simulate an entity with state, behaviour and connections.

    Device.inputs are EventClients which can be connected to Signals.
    Device.outputs are Signals.
    Device.actions are EventClients which represent delayed internal activities,
        typically involving state transitions, and typically invoked by scheduled Events.
    Both input and action methods can also call :
        * 'act' to schedule action callbacks (i.e. timer triggered behaviour)
        * 'out' to change a device output
        * 'xto' to change device state
    """

    STATES: list[str] = ["idle"]
    TIMINGS: dict[str, float] = {}

    def __init__(self, name: str, *args, **kwargs):
        self.name = name
        self._prehooks: dict[str, list[SignalConnection]] = {}
        self._posthooks: dict[str, list[SignalConnection]] = {}
        self._output_hooks: dict[str, list[SignalConnection]] = {}
        self.outputs: dict[str, Signal] = {}
        self._further_acts: list[Event] = []
        self._current_time: EventTime | None = None  # set during input/action callbacks
        self.timings = self.TIMINGS.copy()
        for name, time in self.timings.items():
            if not name.startswith("t_"):
                raise ValueError(f"Timing name {name!r} does not begin 't_'.")
            time_arg = kwargs.pop(name, None)
            if time_arg is not None:
                time = float(time_arg)
                self.timings[name] = time
            setattr(self, name, time)
        self.state = self.STATES[0]

    # Device inputs, actions and outputs.
    # All are subclass-specific.
    # inputs + actions are methods, wrapped with common behaviours
    #  - they are mostly the same, except actions normally don't take a value argument.
    # outputs are just Signals.

    @staticmethod
    def _wrap_functype(inner_func, label: str) -> InputAndActionClassCallsType:
        """
        A basic decorator for wrapping input+action functions.

        Provides common behaviours, including "hooks" and labelling.
        Expects signatures like input(time, value) and action(time[, value[, context]]).
        Converts the wrapped function into an EventClient instance.
        """
        name = inner_func.__name__

        @wraps(inner_func)
        def wrapper_call(
            self,
            time: TimeTypes,
            value: ValueTypes | None = None,
            context=None,
        ):
            time = EventTime(time)
            # Set a 'latest time' record: This enables update() to have a default time,
            #  and means we can test if update/act are called from an input/action.
            assert self._current_time is None
            self._current_time = EventTime(time)
            match value:
                case None:
                    value = None
                case EventValue() | int() | float() | str():
                    value = EventValue(value)
                case _:
                    msg = f"'value' {value!r} has unsupported type."
                    raise TypeError(msg)
            args: tuple = (time,)
            if context is not None:
                args += (value, context)
            elif value is not None:
                args += (value,)
            with self._run_with_hooks(name, time, value, context):
                inner_results = inner_func(
                    self, *args
                )  # NB explicit self is needed here
            if inner_results:
                if not isinstance(inner_results, (list, tuple)):
                    inner_results = [inner_results]
                self._further_acts.extend(list(inner_results))
            # Unset the current time, to catch any spurious calls to act() or update(),
            #  which are supposed to only be invoked from an input/action call.
            self._current_time = None
            # **Remove** newly added events from the current pending list + return them.
            #  (these will normally have been created by act/update calls).
            results = self._further_acts
            self._further_acts = []
            return results

        setattr(wrapper_call, label, True)
        # TODO: typing this seems tricky.  Possibly needs more control over @wraps() ?
        return wrapper_call

    @staticmethod
    def action(inner_func) -> InputAndActionClassCallsType:
        """Decorator to make an action function."""
        return Device._wrap_functype(inner_func, "_label_action")

    @staticmethod
    def input(inner_func) -> InputAndActionClassCallsType:
        """Decorator to make an input function."""
        return Device._wrap_functype(inner_func, "_label_input")

    # Properties providing name: method maps of all the device inputs + actions.
    # NOTE: these are calculated dynamically, instead of in the "@action/input"
    # decorators, because we want *instance* methods (so, not available at class
    # definition time).
    # TODO: they could be cached, though ?

    def _map_labelled_funcs(
        self, label: str
    ) -> dict[str, InputAndActionInstanceCallsType]:
        """Return a dict of the device's inputs with a particular label.

        This enables us to identify inputs + actions.
        Doing it this way to avoid using a metaclass.
        """
        cls = self.__class__
        all_attrs = {name: getattr(cls, name) for name in dir(cls)}
        wanted_calls = {
            name: getattr(self, name)  # get the INSTANCE method
            for name, call in all_attrs.items()
            if callable(call) and hasattr(call, label)
        }
        return wanted_calls

    @property
    def actions(self) -> dict[str, InputAndActionInstanceCallsType]:
        """Return a dict of the device's actions."""
        return self._map_labelled_funcs("_label_action")

    @property
    def inputs(self) -> dict[str, InputAndActionInstanceCallsType]:
        """Return a dict of the device's inputs."""
        return self._map_labelled_funcs("_label_input")

    def add_output(
        self, name_or_signal: str | Signal, start_value: ValueTypes = SIG_START_DEFAULT
    ):
        """Create an output signal.

        Outputs are normally created in init.  They are automatically assigned to the
        'self.outputs' dict, and also as a named instance property.

        Examples
        --------
        >>> self.add_output("out1", start_value=0)
        >>> out = <device>.outputs["out1"]
        >>> <device>.out1.out(2.0, 2)
        """
        match name_or_signal:
            case str():
                output_signal = Signal(name=name_or_signal, start_value=start_value)
                name = name_or_signal
            case Signal():
                output_signal = name_or_signal
                name = output_signal.name
            case _:
                msg = (
                    f"Unexpected type {type(name_or_signal)} for 'name_or_signal':"
                    f" {name_or_signal}."
                )
                raise ValueError(msg)
        self.outputs[name] = output_signal
        setattr(self, name, output_signal)
        return output_signal

    # @action methods are called by an Event to implement a delayed operation.
    # These events are themselves usually created by a Device.act() call in an @input or
    # other @action method.

    def act(
        self,
        action_or_name: str | EventClient,
        time: TimeTypes,
        value: ValueTypes | None = None,
        context=None,
    ):
        """
        Schedule a subsequent action.

        This creates + schedules a future call (with a later simulation time) to one of
        this device's @action methods.

        This creates a new Event and records it, from where it is eventually returned to
        the caller of the device function (input or action), as a standard behaviour of
        action+input methods (from the common code wrapper).

        Examples
        --------
        >>> self.act('next',t + 0.5)

        Notes
        -----
        * The 'value' and 'context' args are usually redundant, but are included for
          completeness.  If required, an action may be defined to take a value argument,
          or value + context, but normally they are not -- in which case, passing either
          value or context will cause an error.

        * This method can only be called from within an action/input routine.  This is
          checked + will error if not.
        """
        # Check that we are called only from within an input/action routine.
        if self._current_time is None:
            raise ValueError(f"{self.name}.act not called from input/action/act/out.")
        time = EventTime(time)
        if value is not None:
            value = EventValue(value)
        action: EventClient | None = None
        match action_or_name:
            case func if callable(func):
                action = action_or_name
            case str():
                for prefix in ("act_", "act", ""):
                    name = prefix + action_or_name
                    action = self.actions.get(name, None)
                    if action is not None:
                        break

        if action not in self.actions.values():
            msg = (
                f"Argument {action_or_name} is not an action of this device, "
                f"{self.name}."
            )
            raise ValueError(msg)

        assert callable(action) and hasattr(action, "_label_action")
        with self._run_with_hooks("act", time, value, context=action.__name__):
            event = Event(time, action, value, context)
            self._further_acts.append(event)

    def out(
        self,
        output_name: str,
        value: ValueTypes | None = None,
    ):
        """
        Update an output.

        There is no 'time' arg, as time is taken from the calling function
        (i.e. an action or input).
        Any resulting new events are automatically returned from the caller input/action.

        Notes
        -----
        Can only be called from within an action/input routine.  This is checked + will
        error if not.

        Examples
        --------
        >>> self.out('out1', new_value)
        """
        # Check that we are called only from within an input/action routine.
        if self._current_time is None:
            raise ValueError(f"{self.name}.out not called from input/action/act/out.")
        time = self._current_time
        if value is None:
            value = SIG_UNDEFINED
        else:
            value = EventValue(value)

        with self._run_with_hooks("out", time, value, context=output_name):
            new_events = self.outputs[output_name].update(time, value)

        if new_events:
            self._further_acts.extend(new_events)

    def xto(self, current_state_s: str | list[str], new_state: str | None = None):
        if self._current_time is None:
            raise ValueError(f"{self.name}.xto not called from input/action/act/out.")

        if isinstance(current_state_s, str):
            current_states = [current_state_s]
        else:
            current_states = current_state_s

        funcname = "<?unknown?"
        callnames = self.all_eventcall_names()
        for stk in inspect.stack():
            thisname = stk.function
            obj = stk.frame.f_locals.get("self", None)
            if obj is self and thisname in callnames:
                funcname = thisname
                break
        caller_name = f"{self.name}.{funcname}"

        msg = ""
        given_states = current_states
        if new_state is not None:
            given_states += [new_state]
        for state in given_states:
            if state not in self.STATES:
                msg = (
                    f"State {state!r} in args of {self.name}.xto is not a valid state. "
                    f"Called from {caller_name} method, "
                    f"Valid states are {self.STATES!r}."
                )
                break
        if self.state not in current_states:
            msg = (
                f"Current state {self.state} in {self.name}.xto, "
                f"called from {caller_name} method, "
                f"is not one of the expected states: {self.STATES!r}."
            )

        if msg:
            raise ValueError(msg)

        time, value = self._current_time, EventValue(0)
        with self._run_with_hooks(
            "xto", time, value, context=(caller_name, self.state, new_state)
        ):
            if new_state is not None:
                self.state = new_state

    # Device hooks + tracing.
    # TODO: tracing should *not* be embedded in the Device code,
    #  but implemented via hooks.
    #  The storage + handling will still need an instance variable, though.
    def hook(
        self, name: str, call: EventClient, context=None, call_after: bool = False
    ) -> SignalConnection:
        """Hook an operation of the device.

                You can hook (by name) any input/output/action, or the 'act' and 'out' calls.

                This installs a callback that gets called when the given operation occurs, either
                *before* (default) or *after* (alternatively) the operation takes place.

                For inputs, when its 'update' is called.
                For actions, when the action occurs.
                For outputs, when the output changes (just like connecting to the signal).
                For 'act'/'out', when the method is called (always within the code of an input
                  or action operation).
        =
                Notes:
                * these operations cannot return new events
                * the context passed to the callback is always of the form
                    {'call_context': <hooked_call_context>, 'hook_context': <context>}
                  In the case of an output, the 'call_context' part is **always** None.
        """
        if name in self.outputs:
            # Outputs are signals, so hooks are installed by just connecting
            hooklist = self._output_hooks.setdefault(name, [])
            hook_context = {"call_context": None, "hook_context": context}
            index = -1 if call_after else 0
            new_hook = self.outputs[name].connect(call, hook_context, index)
            hooklist.append(new_hook)
        else:
            # Inputs and Actions are EventClient-type methods : hooks are created by
            #  just inserting connections into the pre- or post-hook lists.
            # The "act" and "update" methods are also 'hookable'.
            all_names = self.all_eventcall_names()
            if name not in all_names:
                raise ValueError(f"Unrecognised hook name: {name!r}")
            if name in ["act", "update", "out"]:
                # Special cases : since no callback, only put these in pre-hooks
                call_after = False
            hookset = self._posthooks if call_after else self._prehooks
            hooklist = hookset.setdefault(name, [])
            new_hook = SignalConnection(call, context)
            hooklist.append(new_hook)
        return new_hook

    def unhook(self, name_or_hook: str | SignalConnection):
        # Discard ALL hooks for the named component, OR just the specific one given.
        match name_or_hook:
            case str():
                # Search in all hook places : remove ALL under that name
                name: str = name_or_hook
                for hookset in (self._prehooks, self._posthooks, self._output_hooks):
                    hooklist = hookset.pop(name)
                    if hooklist and hookset is self._output_hooks:
                        # Must *also* disconnect all the hooks from the signal
                        output = self.outputs.get(name, None)
                        if output is not None:
                            for a_hook in hooklist:
                                output.disconnect(a_hook)

            case SignalConnection():
                # Search in all hooks + remove this *specific* hook
                hook: SignalConnection = name_or_hook
                for hookset in (self._prehooks, self._posthooks, self._output_hooks):
                    for name, hooklist in hookset.items():
                        if hook in hooklist:
                            hooklist.remove(hook)
                            if hookset is self._output_hooks:
                                # Must also disconnect all the hooks from the signal
                                output = self.outputs.get(name, None)
                                if output is not None:
                                    output.disconnect(hook)

    @contextmanager
    def _run_with_hooks(
        self, name: str, time: EventTime, value: EventValue | None = None, context=None
    ):
        """Implement 'hook' callbacks for a device operation.

        Call pre/posthooks before/after a code block.
        """

        def call_hooks(hookset: dict[str, list[SignalConnection]]):
            hooks = hookset.get(name, [])
            for hook in hooks:
                hook_context = {
                    "call_context": context,
                    "hook_context": hook.call_context,
                }
                hook.call(time, value, hook_context)

        call_hooks(self._prehooks)
        yield
        call_hooks(self._posthooks)

    def _trace_callback(
        self, time: EventTime, value: EventValue | None = None, context=None
    ):
        match value:
            case None:
                val = SIG_UNDEFINED
            case EventValue():
                val = value
            case _:
                raise ValueError(f"unexpected type {type(value)} of 'value': {value!r}")

        trace_context = context["hook_context"]
        call_context = context["call_context"]
        device_type = trace_context["device_type"]
        device_name = trace_context["device_name"]
        component_type = trace_context["component_type"]
        component_name = trace_context["component_name"]
        time_str = f"{time.time:.1f}".rjust(6)
        if time.priority != 0:
            time_str += f"(priority={time.priority})"
        msg = f"TRACE {time}: {device_type}({device_name}).{component_type}({component_name}) : "
        if component_type == "input":
            msg += f", value <-- {val}"
        elif component_type == "action":
            if value is not None or call_context is not None:
                msg += f", value={value}"
            if call_context is not None:
                msg += f", context={call_context}"
        elif component_type == "output":
            sig = self.outputs[component_name]
            msg += f" :: {sig.previous_value} --> {sig.value}"
            # msg = wirables.signal.TRACE_HANDLER_CLIENT(time, value, signal=call_context)
        elif component_type == "act":
            msg += f" ==> {call_context!r}"
        elif component_type == "out":
            msg += f" {call_context} <== {value}"
        elif component_type == "xto":
            callername, oldstate, newstate = call_context
            msg += f" (in {callername}) state {oldstate!r} -> {newstate!r}."
        if component_type not in ("input", "action"):
            msg = "  " + msg
        print(msg)

    def all_eventcall_names(self) -> list[str]:
        all_names = (
            ["act", "out", "xto"] + list(self.inputs.keys()) + list(self.actions.keys())
        )
        return all_names

    def trace(self, name: str, after: bool = False) -> SignalConnection | None:
        if name == "*":
            for a_name in self.all_eventcall_names():
                self.trace(a_name)
            result = None
        else:
            if name in self.inputs:
                component_type = "input"
            elif name in self.actions:
                component_type = "action"
            elif name in self.outputs:
                component_type = "output"
            elif name in ["act", "out", "xto"]:
                component_type = name
            else:
                msg = (
                    f"Cannot trace unknown device component: {name!r}, "
                    "not a known input, output or action."
                )
                raise ValueError(msg)
            context = {
                "device_type": self.__class__.__name__,
                "device_name": self.name,
                "component_type": component_type,
                "component_name": name,
            }
            result = self.hook(name, self._trace_callback, context, call_after=after)
        return result

    def untrace(self, name_or_hook: str | SignalConnection):
        match name_or_hook:
            case SignalConnection():
                # Easy case : simply remove the hook
                hook: SignalConnection = name_or_hook
                self.unhook(hook)
            case str():
                # Given name : we must identify all matching hooks + remove each one.
                name: str = name_or_hook
                if name == "*":
                    names = self.all_eventcall_names()
                else:
                    names = [name]
                for name in names:
                    for hookset in (
                        self._prehooks,
                        self._posthooks,
                        self._output_hooks,
                    ):
                        hooklist = hookset.get(name, None)
                        if hooklist is not None:
                            tracehooks = [
                                hook
                                for hook in hooklist
                                if hook.call == self._trace_callback
                            ]
                            for tracehook in tracehooks:
                                self.unhook(tracehook)

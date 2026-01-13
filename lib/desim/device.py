from functools import wraps

from desim import SIG_UNDEFINED
from desim.event import Event, EventClient, EventTime, EventValue
from desim.signal import SIG_START_DEFAULT, SIG_ZERO, Signal, SignalConnection


class Device:
    """
    Object to simulate an entity with state, behaviour and connections.

    Device.inputs are EventClients which can be connected to Signals.
    Device.outputs are Signals.
    Device.actions are EventClients which represent delayed internal activities,
        typically involving state transitions, and typically invoked by scheduled Events.
    Both input and action methods can also schedule new events by calling Device.act(),
        or returning a list of events.
    """

    def __init__(self, name: str):
        self.name = name
        self.state = "idle"  # This is conventional
        self._prehooks: dict[str, list[SignalConnection]] = {}
        self._posthooks: dict[str, list[SignalConnection]] = {}
        self._output_hooks: dict[str, list[SignalConnection]] = {}
        self.outputs: dict[str, Signal] = {}
        self._further_acts: list[Event] = []

    def reset(self):
        self.state = "idle"

    def hook(
        self, name: str, call: EventClient, context=None, call_after=False
    ) -> SignalConnection:
        """Hook an output, input or action of the device.

        This installs a callback that runs when an output (signal) updates, either
        *before* (default) or *after* (alternatively) an input/action func is invoked.

        Notes:
        * these operations cannot return new events
        * the context passed to the callback is always of the form
            {'call_context': <hooked_call_context>, 'hook_context': <context>}
          In the case of an output, the 'call_context' part is always None.
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
            hookset = self._posthooks if call_after else self._prehooks
            hooklist = hookset.setdefault(name, [])
            new_hook = SignalConnection(call, context)
            hooklist.append(new_hook)
        return new_hook

    def unhook(self, name_or_hook: str | SignalConnection):
        # Discard ALL hooks for the given name, or the specific one given.
        match name_or_hook:
            case str():
                # Search in all hook places : remove ALL under that name
                name: str = name_or_hook
                for hookset in (self._prehooks, self._posthooks, self._output_hooks):
                    hooklist = hookset.pop(name)
                    if hookset is self._output_hooks:
                        # Must also disconnect all the hooks from the signal
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

    def call_hooks(
        self,
        name: str,
        hookset: dict[str, list[SignalConnection]],
        time: EventTime,
        value: EventValue,
        context,
    ):
        hooks = hookset.get(name, [])
        for hook in hooks:
            hook_context = {"call_context": context, "hook_context": hook.call_context}
            hook.call(time, value, hook_context)

    def _trace_callback(
        self, time: EventTime, value: EventValue | None = None, context=None
    ):
        match value:
            case None:
                val = SIG_UNDEFINED
            case EventValue():
                val = value

        trace_context = context["hook_context"]
        call_context = context["call_context"]
        device_type = trace_context["device_type"]
        device_name = trace_context["device_name"]
        component_type = trace_context["component_type"]
        component_name = trace_context["component_name"]
        msg = (
            f"TRACE {device_type}({device_name}).{component_type}({component_name}) : "
        )
        if component_type == "input":
            msg += f"time={time}, value={val}"
        elif component_type == "action":
            msg += f"time={time}, value={val}"
            if call_context:
                msg += f", context={call_context}"
        elif component_type == "output":
            sig = self.outputs[component_name]
            msg += f"time={time}, value {sig.previous_value} --> {sig.value}"
        print(msg)

    def trace(self, name: str) -> SignalConnection:
        if name in self.inputs:
            component_type = "input"
        elif name in self.actions:
            component_type = "action"
        elif name in self.outputs:
            component_type = "output"
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
        hook = self.hook(name, self._trace_callback, context)
        return hook

    def untrace(self, name_or_hook: str | SignalConnection):
        match name_or_hook:
            case SignalConnection():
                # Easy case : simply remove the hook
                hook: SignalConnection = name_or_hook
                self.unhook(hook)
            case str():
                # Given name : we must identify all matching hooks + remove each one.
                name: str = name_or_hook
                for hookset in (self._prehooks, self._posthooks, self._output_hooks):
                    hooklist = hookset.get(name, None)
                    if hooklist is not None:
                        tracehooks = [
                            hook
                            for hook in hooklist
                            if hook.call == self._trace_callback
                        ]
                        for tracehook in tracehooks:
                            self.unhook(tracehook)

    @staticmethod
    def _wrap_functype(inner_func, label: str) -> EventClient:
        """
        A basic decorator for wrapping input+action functions.

        Provides common behaviours, including "hooks" and labelling.
        Expects signatures like input(time, value) and action(time).
        Converts the wrapped function into a EventClient instance.
        """
        name = inner_func.__name__

        @wraps(inner_func)
        def wrapper_call(
            self,
            time: EventTime,
            value: EventValue | int | float | str | None = None,
            context=None,
        ):
            time = EventTime(time)
            match value:
                case None:
                    value = None
                case EventValue() | int() | float() | str():
                    value = EventValue(value)
                case _:
                    msg = f"'value' {value!r} has unsupported type."
                    raise TypeError(msg)
            args: tuple = (self,)
            if context is not None:
                args += (time, value, context)
            elif value is not None:
                args += (time, value)
            else:
                args += (time,)
            self.call_hooks(
                name=name,
                hookset=self._prehooks,
                time=time,
                value=value,
                context=context,
            )
            # NOTE: this means an action/input cannot directly call an action/input of the
            inner_results = inner_func(*args)  # NB explicit self is needed here
            self.call_hooks(
                name=name,
                hookset=self._posthooks,
                time=time,
                value=value,
                context=context,
            )
            if inner_results:
                self._further_acts += inner_results
            # now **remove** any created events acts from the static list + return them.
            results = self._further_acts
            self._further_acts = []
            return results

        setattr(wrapper_call, label, True)
        return wrapper_call  # type: ignore

    @staticmethod
    def action(inner_func) -> EventClient:
        """Decorator to make an action function."""
        return Device._wrap_functype(inner_func, "_label_action")

    @staticmethod
    def input(inner_func) -> EventClient:
        """Decorator to make an input function."""
        return Device._wrap_functype(inner_func, "_label_input")

    def connect(self, input_name: str, signal: Signal):
        """Connect a signal to a device input."""
        signal.connect(self.inputs[input_name])

    def act(
        self,
        time: EventTime | float | int,
        action_name: str,
        value: EventValue | float | int | str = SIG_ZERO,
        context=None,
    ):
        """
        Schedule a call (later) to one of this device's actions.
        This should *only* be called from another action or input function.

        Usually, this will cause a state transition after a time delay.
        """
        time = EventTime(time)
        value = EventValue(value)
        action = self.actions.get(action_name)
        assert callable(action) and hasattr(action, "_label_action")

        def _nonmethod_call(
            time: EventTime, value: EventValue | None = None, context=None
        ):
            # Call the contained action with self as the instance.
            action(self, time, value, context)

        event = Event(time, value, _nonmethod_call, context)
        self._further_acts.append(event)

    @classmethod
    def _list_labelled_funcs(cls, label: str) -> dict[str, EventClient]:
        """Return a dict of the device's inputs with a particular label.

        This enables us to identify inputs + actions.
        Doing it this way to avoid using a metaclass.
        """
        all_attrs = {name: getattr(cls, name) for name in dir(cls)}
        wanted_calls = {
            name: call
            for name, call in all_attrs.items()
            if callable(call) and hasattr(call, label)
        }
        return wanted_calls

    @property
    def actions(self):
        """Return a dict of the device's actions."""
        return self._list_labelled_funcs("_label_action")

    @property
    def inputs(self):
        """Return a dict of the device's inputs."""
        return self._list_labelled_funcs("_label_input")

    def add_output(self, name: str, start_value: EventValue = SIG_START_DEFAULT):
        output_signal = Signal(name=name, start_value=start_value)
        self.outputs[name] = output_signal
        setattr(self, name, output_signal)

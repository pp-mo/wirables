"""
Signal support.

A Signal is an object with a current state "value", which notifies a list of
  connections whenever a new value is "sent" (aka "an update").
  [[ A Signal can also be "traced", which adds a monitoring action to its connections. ]]
Signal(name, state, previous_state, connected_clients)
    .update(time, value)
    .connect(client)
    .disconnection(client)
The 'client's are callables with the generic signature (time, state)
NOTE: the ".set()" call has NO provision for passing additional per-call context.
This is intentional, as the action of a Signal update should not depend on the "source"
of the change.

Signal outputs can model EITHER a value which changes on update, or may be completely
event-triggered, i.e. the value of an update can be irrelevant (e.g. always sends the
same value, but the event itself can cause change elsewhere).
We also don't control the type of values in any way (though assume immutable??).

We also have
    Signal.hook(hook_client, **kwargs)
    Signal.unhook(hook_client)
In this case, a hook_client has the generic signature (time, signal, **kwargs)
    - when called, the signal provides "signal.state" and "signal.previous_state"
    - this is "less agnostic" about the signal itself (as opposed to the update)
        -> allows to define a tracing operation (showing previous+new)

#
# trace/untrace_signal add/remove a specific 'client' which emits/logs an update message
# whenever a signal is updated.
#
def _trace_signal(time, signal):
    # need to do better than this...
    print(time, signal)

def trace_signal(signal)
    signal._hook(_trace_signal)

def untrace_signal(signal)
    signal._unhook(_trace_signal)
"""

from dataclasses import dataclass
from typing import Any, Callable

# : allowed signal value content
type SignalValueType = str | int | float
ALLOWED_SIGNAL_VALUE_TYPES = (str, int, float)

# : time specifiers
type TimeType = float

# class SignalClient(Protocol):
#     """The type of a signal client.
#
#     A signal client is just a callback with a specific signature.
#     """
#     def __call__(self, time: TimeType, signal:"Signal", **kwargs: dict[str, Any] | None):
#         pass

# : signal client callback type : note, final 'dict' is a kwargs-style context argument.
type SignalClient = Callable[[TimeType, Signal, dict[str, Any] | None], None]


@dataclass
class Connection:
    """
    A Connection is a client associated with a specific per-connection context.

    The kwargs are those given when the client was connected with Signal.connect.
    This isn't strictly necessary, but without it a callback function could only be used
    once : the provision of a context makes especially automated uses neater.
    It is also useful to have a distinct object for each connection : at the least,
    it means that we can implement Signal.disconnect.
    """

    call: SignalClient
    context_kwargs: dict[str, Any]


# Pre-defined constant values
SIG_UNDEFINED: SignalValueType = "<undefined-value>"
SIG_ZERO: SignalValueType = 0
SIG_START_DEFAULT: SignalValueType = SIG_ZERO


def default_trace_action(
    time: TimeType, sig: "Signal", kwargs: dict[str, Any] | None = None
):
    """The default trace operation (which is to print)."""
    msg = f"@{time}: Sig<{sig.name}> : {sig.previous_value} ==> {sig.value}"
    print(msg)


# : A single common definition for what the trace actions do.
TRACE_HANDLER_CLIENT: SignalClient = default_trace_action


class Signal:
    def __init__(self, name: str, start_value: SignalValueType | None = None):
        self.name = name
        if start_value is None:
            # Note: pragmatically, the default start state is 0 rather than 'undefined'
            start_value = SIG_START_DEFAULT
        self.value = start_value
        self.previous_value = SIG_UNDEFINED
        self.connected_clients: list[Connection] = []
        # This is a placeholder for the (unique) trace connection
        self._trace_connection: Connection | None = None

    def __repr__(self):
        msg = f"Signal<{self.name} = {self.value!r}>"
        return msg

    def update(self, time: TimeType, value: SignalValueType = SIG_ZERO):
        assert isinstance(value, ALLOWED_SIGNAL_VALUE_TYPES)
        self.previous_value = self.value
        self.value = value
        for connection in self.connected_clients:
            # TODO: should really send only the state, not itself ??
            # current form for access to .state and .previous (?.name? : not really)
            # NEEDED for trace, in current form.  But device tracing is nicer ...
            # NOTE: the context is passed as a kwargs **argument**.
            connection.call(time, self, connection.context_kwargs)

    def connect(
        self, call: SignalClient, index: int = -1, kwargs: dict[str, Any] | None = None
    ) -> Connection:
        """Create a connection to this signal.

        The 'call' callback (aka 'client') is invoked whenever the signal updates.
        """
        if kwargs is None:
            kwargs = {}
        connection = Connection(call, kwargs)
        if connection not in self.connected_clients:
            self.connected_clients[index:index] = [connection]
        return connection  # this enables us to remove it

    def disconnect(self, connection: Connection):
        """Remove a given output connection."""
        while connection in self.connected_clients:
            self.connected_clients.remove(connection)

    # Tracing
    #   this is best defined within the Signal class, since it relies on the private
    #   instance variable "self._trace_connection".
    #

    @staticmethod
    def _call_trace(
        time: TimeType, sig: "Signal", kwargs: dict[str, Any] | None = None
    ):
        """The client callback for trace connections.

        All traces call this, which then calls TRACE_HANDLER_CLIENT.
        This enables you to modify **all** trace operations by setting
        TRACE_HANDLER_CLIENT.

        This is defined as a static function, since it must conform to the SignalClient
        definition.
        """
        TRACE_HANDLER_CLIENT(time, sig, kwargs)

    def trace(self):
        """Start tracing this signal.

        Adds a standard logging client to show whenever the signal updates.
        The operation performed can be configured via desim.signal.DEFAULT_TRACE_OP.
        The connection created is stored as self._trace.
        """
        trace = getattr(self, "_trace_connection", None)
        if trace is None:
            # (of course doesn't function if something else inserts there)
            self._trace_connection = self.connect(
                self._call_trace,
                # N.B. insert trace at **start** of connections, so it happens before
                # other clients are invoked.
                # Of course this can be broken by further insertions.
                index=0,
            )

    def untrace(self):
        """Stop tracing this signal."""
        trace = getattr(self, "_trace_connection", None)
        if trace is not None:
            self.disconnect(trace)
        self._trace_connection = None

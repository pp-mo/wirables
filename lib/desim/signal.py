"""
Signal support.

A Signal is an object with a current state "value", which notifies a list of
  connections whenever a new value is "sent" via Signal.update(time, value).
  [[ A Signal can also be "traced", which adds a monitoring action to its connections. ]]

A signal event and/or value change is made by calling Signal.update(time, value=None),
where time and value are interpreted as EventTime and EventValue.

A signal's value is its only state, and it implements no logic or scheduling functions:
It is purely a message-passing mechanism.

A signal's values and updates can represent EITHER a continuous value which only changes
at updates, OR a pure event-trigger, for which the value is irrelevant.

NOTE: the ".update()" call itself has NO provision for passing additional per-call
context.  This is intentional, as the output of a Signal should not depend on the
"source" of a change.
Being an EventClient, the Signal.update call() is capable of generating additional
scheduled actions, by returning a list of new Events to the caller.

Connections are added with Signal.connect(client, call_context=None, index=-1).
When connection clients are called in a Signal.update(), the new time and value are
passed.  The signal itself can be used as, or included in, the connection context.

We also provide Signal.trace/untrace().
Tracing connects a standard EventClient, which emits or logs a standard signal update
message whenever the signal is updated.
The operation of this is configurable by changing the value of TRACE_HANDLER_CLIENT :
its default is the 'default_trace_action' function, which prints to the terminal.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from desim.event import EventTime, EventValue, EventClient, Event


@dataclass
class SignalConnection:
    """
    A Connection is a client associated with a specific per-connection context.

    The call_context is that given when the client was connected with Signal.connect.
    This isn't *strictly* necessary, but without it a given callback function could only
    be connected once : the provision of a context value makes especially automated uses
    neater.
    It is also useful to have a distinct object for each connection : at the least,
    it means that we can implement Signal.disconnect.
    """

    call: EventClient
    call_context: Any


# Pre-defined constant values
SIG_UNDEFINED: EventValue = EventValue("<undefined-value>")
SIG_ZERO: EventValue = EventValue(0)
SIG_START_DEFAULT: EventValue = SIG_ZERO


def default_trace_action(
    time: EventTime, value: EventValue | None = None, signal: Signal | None = None
):
    """The default trace operation = print signal update details to the terminal.

    N.B. although this conforms to the generic EventClient signature, in this case the
    passed 'context' argument is **always the signal which this is a trace of**.
    """
    match signal:
        case None:
            sig = Signal("<?missing?>")
        case _:
            sig = signal
    msg = f"@{time}: Sig<{sig.name}> : {sig.previous_value} ==> {sig.value}"
    print(msg)


# : A single common definition for what trace actions do.
TRACE_HANDLER_CLIENT: EventClient = default_trace_action


class Signal:
    def __init__(
        self, name: str, start_value: EventValue | int | float | str = SIG_START_DEFAULT
    ):
        self.name = name
        self.value: EventValue = EventValue(start_value)
        self.previous_value = SIG_UNDEFINED
        self.connected_clients: list[SignalConnection] = []
        # This is a placeholder for the (unique) trace connection
        self._trace_connection: SignalConnection | None = None

    def __str__(self):
        msg = f"Signal<{self.name} = {self.value!s}>"
        return msg

    def update(
        self,
        time: EventTime | int | float,
        value: EventValue | int | float | str = SIG_ZERO,
    ) -> list[Event]:
        time = EventTime(time)
        value = EventValue(value)
        self.previous_value = self.value
        self.value = value
        further_events: list[Event] = []
        for connection in self.connected_clients:
            # TODO: should really send only the state, not itself ??
            # current form for access to .state and .previous (?.name? : not really)
            # NEEDED for trace, in current form.  But device tracing is nicer ...
            # NOTE: the context is passed as a kwargs **argument**.
            new_events = connection.call(time, value, connection.call_context)
            if new_events:
                # N.B. also allows callbacks to return nothing.
                further_events.extend(new_events)
        return further_events

    def connect(
        self, call: EventClient, call_context=None, index: int = -1
    ) -> SignalConnection:
        """Create a connection to this signal.

        The 'call' callback (aka 'client') is invoked whenever the signal updates.
        The index governs where the connection is installed in the (current) connections
        list, for ordering control: -1[default] --> last; 0 --> first.
        """
        connection = SignalConnection(call, call_context)
        if connection not in self.connected_clients:
            self.connected_clients[index:index] = [connection]
        return connection  # this enables us to remove it

    def disconnect(self, connection: SignalConnection):
        """Remove a given output connection."""
        while connection in self.connected_clients:
            self.connected_clients.remove(connection)

    # Tracing
    #   This is defined within the Signal class, although it operates via the public
    #   'connection' mechanism, since it uses on a private instance variable
    #   "self._trace_connection", which is created in init.
    #

    @staticmethod
    def _call_trace(time: EventTime, value: EventValue, sig: "Signal"):
        """The client callback for trace connections.

        All traces call this, which then calls TRACE_HANDLER_CLIENT.
        This enables you to modify **all** trace operations by setting
        TRACE_HANDLER_CLIENT.
        """
        TRACE_HANDLER_CLIENT(time, sig.value, sig)  # N.B. the signal is the context

    def trace(self):
        """Start tracing this signal.

        Adds a standard logging client to show whenever the signal updates.
        The operation performed can be configured via desim.signal.DEFAULT_TRACE_OP.
        """
        trace = getattr(self, "_trace_connection", None)
        if trace is None:
            self._trace_connection = self.connect(
                self._call_trace,
                call_context=self,
                # N.B. always insert trace at **start** of connections, so it happens
                # before other clients (whereas *default* behaviour = insert at end).
                # Of course this can be broken by further insertions.
                index=0,
            )

    def untrace(self):
        """Stop tracing this signal."""
        trace = getattr(self, "_trace_connection", None)
        if trace is not None:
            self.disconnect(trace)
        self._trace_connection = None

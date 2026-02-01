import pytest

from wirables import Device, Event, Signal, SIG_UNDEFINED


class TestInit:
    def test_init(self):
        class Dev1Input(Device):
            def __init__(self, *args, mycontext=None, **kwargs):
                super().__init__(*args, **kwargs)
                self.my_context = mycontext

        dev1 = Dev1Input("name", mycontext="this-one")
        assert dev1.my_context == "this-one"
        assert dev1.inputs == {}
        assert dev1.actions == {}
        assert dev1.outputs == {}


RESULT_TEST_VALUE_OPTIONS = [
    "anyval",
    "return-empty",
    "return-event",
    "return-list-1",
    "return-list-2",
]


@pytest.fixture(params=RESULT_TEST_VALUE_OPTIONS)
def val(request):
    yield request.param


def _result_events_list(value, event):
    if value == "return-empty":
        result = []
    elif value == "return-event":
        result = event
    elif value == "return-list-1":
        result = [event]
    elif value == "return-list-2":
        result = [event, event]
    else:
        result = None
    return result


def check_result_events(result, val):
    assert isinstance(result, list)
    if val in ("anyval", "return-empty"):
        assert result == []
    elif val in ("return-event", "return-list-1"):
        assert len(result) == 1
        assert isinstance(result[0], Event)
    elif val == "return-list-2":
        assert len(result) == 2
    else:
        raise ValueError("unexpected param 'val' : {val!r}")


def dummy_event_callback(time, value):
    pass


class TestInputs:
    class DevMinimalInput(Device):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.in1_calls = []

        @Device.input
        def in1(self, time, value):
            self.in1_calls.append((time, value))
            ev = Event(time=time.time + 0.1, call=dummy_event_callback)
            return _result_events_list(value, ev)

    def test_input(self):
        dev = self.DevMinimalInput("mydev1")
        assert dev.name == "mydev1"
        assert dev.inputs == {"in1": dev.in1}
        assert dev.in1_calls == []
        dev.in1(1.0, "val")
        assert dev.in1_calls == [(1.0, "val")]

    def test_input_from_signal_connection(self):
        dev = self.DevMinimalInput("mydev2")
        sig = Signal("sig1")
        sig.connect(dev.in1)
        assert dev.in1_calls == []
        sig.update(4.2, 3.4)
        sig.update(1)
        assert dev.in1_calls == [(4.2, 3.4), (1, SIG_UNDEFINED)]

    def test_returnvalues(self, val):
        dev = self.DevMinimalInput("mydev1")
        results = dev.in1(1, val)
        check_result_events(results, val)


class TestActions:
    class Dev1Action(Device):
        @Device.action
        def act1(self, time, value):
            ev = Event(time, "now-what")
            self.act1_triggered = True
            return _result_events_list(value, ev)

    def test_basic(self, val):
        dev = self.Dev1Action("dev1")
        assert dev.actions == {"act1": dev.act1}
        assert not hasattr(dev, "act1_triggered")
        results = dev.act1(1.23, val)
        assert hasattr(dev, "act1_triggered") and dev.act1_triggered
        # Check various return value formats, as for input call.
        check_result_events(results, val)
        if results:
            assert results[0].time == 1.23

    class DevMinimalAction(Device):
        @Device.action
        def act(self, time):
            pass

    def test_action_novalue_ok(self):
        dev = self.DevMinimalAction("name")
        # It's ok to call with no value
        assert dev.act(1) == []
        # It's an error to pass a value when none was expected
        msg = "\.act\(\) takes 2 positional arguments but 3 were given"
        with pytest.raises(TypeError, match=msg):
            dev.act(2, 1)


class Test_add_output:
    class DevMinimalOutput(Device):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            result = self.add_output("out1")
            # Just check here the return of the function.
            assert result == self.out1

    def test_create_basic(self):
        dev = self.DevMinimalOutput("dev1")
        assert dev.outputs == {"out1": dev.out1}
        assert isinstance(dev.out1, Signal)

    def test_create_startvalue(self):
        dev = Device("minimal")
        dev.add_output("x", 23)
        assert dev.x.value == 23

    def test_create_fromsignal(self):
        dev = Device("minimal")
        sig = Signal("signame")
        dev.add_output(sig)
        assert dev.outputs == {"signame": sig}

    @pytest.mark.parametrize("arg", [None, 1, {}])
    def test_create_badargs(self, arg):
        dev = Device("minimal")
        msg = "Unexpected type.*for 'name_or_signal'"
        with pytest.raises(ValueError, match=msg):
            dev.add_output(arg)


class TestAct:
    """."""


class TestOut:
    """."""

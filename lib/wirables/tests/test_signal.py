import pytest

from wirables import signal
from wirables import Signal, SIG_START_DEFAULT, SIG_UNDEFINED


@pytest.fixture(autouse=True)
def sig():
    return Signal("s1")


class TestCreate:
    def test(self, sig):
        assert sig.name == "s1"
        assert sig.value == SIG_START_DEFAULT
        assert sig.previous_value == SIG_UNDEFINED
        assert sig.connected_clients == []
        assert sig._trace_connection is None

    @pytest.mark.parametrize("val", ["one", 17, 3.21, "no-assign"])
    def test_str(self, val):
        if val != "no-assign":
            sig = Signal("s2", val)
        else:
            sig = Signal("s2")
            val = 0
        expect = f"Signal<s2 = {val!r}>"
        print(f"Expected: {expect}")
        assert str(sig) == expect


class TestUpdate:
    @pytest.mark.parametrize("val", ["one", 17, 3.21])
    def test_update(self, sig, val):
        sig.update(0, val)
        assert sig.value == val

    def test_update_noval(self, sig):
        sig.update(0, 77)
        assert sig.value == 77
        sig.update(0)
        assert sig.value == SIG_UNDEFINED


class TestConnect:
    @pytest.fixture(autouse=True)
    def call_and_callrecords(self, sig):
        call_records = []

        def call(time, value, context):
            call_records.append((time, value, context))

        return call, call_records

    def test_connect_basic(self, sig, call_and_callrecords):
        call, call_records = call_and_callrecords
        sig.connect(call)
        assert call_records == []
        time1, value1 = 0.123, 123
        sig.update(time1, value1)
        time2, value2 = 2.1, "stuff"
        sig.update(time2, value2)
        assert call_records == [(time1, value1, None), (time2, value2, None)]

    def test_connect_callcontext(self, sig, call_and_callrecords):
        call, call_records = call_and_callrecords
        call_kwargs = {"a": 1}
        sig.connect(call, call_context=call_kwargs)
        time, value = 0.123, 123
        sig.update(time, value)
        assert call_records == [(time, value, call_kwargs)]


class TestTrace:
    @pytest.fixture(autouse=True)
    def trace_records(self):
        trace_records = []

        def my_trace(time, value, sig):
            record = (time, sig, sig.value, sig.previous_value)
            print("Logged trace record :", record)
            trace_records.append(record)

        old_client = signal.TRACE_HANDLER_CLIENT
        signal.TRACE_HANDLER_CLIENT = my_trace
        try:
            yield trace_records
        finally:
            signal.TRACE_HANDLER_CLIENT = old_client

    def test_trace(self, sig, trace_records):
        sig.update(0.0, 77)
        assert trace_records == []
        sig.trace()
        assert trace_records == []
        sig.update(1.2, 22)
        sig.update(1.3, 33)
        assert trace_records == [(1.2, sig, 22, 77), (1.3, sig, 33, 22)]

    def test_untrace(self, sig, trace_records):
        sig.update(0.0, 77)
        sig.trace()
        sig.update(2.2, 55)
        sig.update(2.3, 66)
        sig.untrace()
        sig.update(9, 999)
        assert trace_records == [(2.2, sig, 55, 77), (2.3, sig, 66, 55)]

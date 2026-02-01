import pytest

from wirables import EventTime


class TestCreate:
    def test_float(self):
        time = EventTime(1.2)
        assert time.time == 1.2
        assert time.priority == 0

    def test_int(self):
        time = EventTime(3)
        assert time.time == 3
        assert isinstance(time.time, float)
        assert time.priority == 0

    def test_priority(self):
        time = EventTime(1, priority=7)
        assert time.time == 1
        assert time.priority == 7


class TestEqNe:
    def test_self_eq(self):
        t1 = EventTime(3)
        assert t1 == t1

    def test_eventtime_eq(self):
        t1 = EventTime(1.1)
        t2 = EventTime(1.1)
        assert t1 == t2
        assert t2 == t1

    def test_eventtime_ne(self):
        t1 = EventTime(1.1)
        t2 = EventTime(1.1001)
        assert t1 != t2

    def test_plainvalue_eq(self):
        t1 = EventTime(1.23)
        time = 1.23
        assert t1 == time
        assert time == t1

    def test_plainvalue_ne(self):
        t1 = EventTime(1.23)
        time = 1.24
        assert t1 != time
        assert time != t1


class TestStrRepr:
    @pytest.fixture(params=[1, 1.23])
    def time(self, request):
        yield request.param

    def test_str(self, time):
        t1 = EventTime(time)
        expected = {
            1: "1.0",  # always a float internally
            1.23: "1.23",
        }[time]
        result = str(t1)
        assert result == expected

    def test_repr(self, time):
        t1 = EventTime(time)
        expected = {
            1: "EventTime(1.0)",
            1.23: "EventTime(1.23)",
        }[time]
        result = repr(t1)
        assert result == expected


class TestAdd:
    @pytest.mark.parametrize("val", [1, 1.23, EventTime(2, 5)])
    @pytest.mark.parametrize("order", ["forward", "reverse"])
    def test_add_ev_value(self, val, order):
        time = EventTime(10.0, priority=17)
        if order == "forward":
            time2 = time + val
        else:
            time2 = val + time
        if isinstance(val, EventTime):
            vt = val.time
        else:
            vt = val
        assert isinstance(time2, EventTime)
        assert time2.time == time.time + vt
        assert time2.priority == 0


class TestSortorder:
    def test_evcompare(self):
        t1 = EventTime(1)
        t2 = EventTime(2)
        # msg = "not supported between instances of 'EventTime' and 'EventTime'"
        # with pytest.raises(TypeError, match=msg):
        assert t1 < t2
        # with pytest.raises(TypeError, match=msg):
        assert not (t2 < t1)

    def test_valcompare(self):
        t1 = EventTime(1)
        time = 2
        # msg = "not supported between instances of 'EventTime' and 'int'"
        # with pytest.raises(TypeError, match=msg):
        assert t1 < time
        assert not (time < t1)

    def test_prioritycompare(self):
        t1 = EventTime(1)
        t1_less = EventTime(1, priority=1)
        t1_more = EventTime(1, priority=-1)
        assert t1 > t1_less
        assert t1_less < t1
        assert t1_more > t1
        assert t1 < t1_more

import pytest

from wirables import EventValue


class TestCreate:
    def test_int(self):
        val = EventValue(3)
        assert val.value == 3

    def test_float(self):
        val = EventValue(1.2)
        assert val.value == 1.2

    def test_str(self):
        val = EventValue("one")
        assert val.value == "one"


class TestEqNe:
    def test_self_eq(self):
        v1 = EventValue("one")
        assert v1 == v1

    def test_ev_eq(self):
        v1 = EventValue(1.1)
        v2 = EventValue(1.1)
        assert v1 == v2
        assert v2 == v1

    def test_ev_ne(self):
        v1 = EventValue(1.1)
        v2 = EventValue(1.1001)
        assert v1 != v2

    def test_plainvalue_eq(self):
        v1 = EventValue(1.23)
        val = 1.23
        assert v1 == val
        assert val == v1

    def test_plainvalue_ne(self):
        v1 = EventValue(1.23)
        val = 1.24
        assert v1 != val
        assert val != v1


class TestNoSortorder:
    def test_evcompare_fail(self):
        v1 = EventValue(1)
        v2 = EventValue(2)
        msg = "not supported between instances of 'EventValue' and 'EventValue'"
        with pytest.raises(TypeError, match=msg):
            v1 < v2
        with pytest.raises(TypeError, match=msg):
            v2 < v1

    def test_valcompare_fail(self):
        v1 = EventValue(1)
        val = 2
        msg = "not supported between instances of 'EventValue' and 'int'"
        with pytest.raises(TypeError, match=msg):
            v1 < val
        msg = "not supported between instances of 'int' and 'EventValue'"
        with pytest.raises(TypeError, match=msg):
            val < v1


class TestStrRepr:
    @pytest.fixture(params=[1, 1.23, "one"])
    def val(self, request):
        yield request.param

    def test_str(self, val):
        v1 = EventValue(val)
        expected = {1: "1", 1.23: "1.23", "one": "'one'"}[val]
        result = str(v1)
        assert result == expected

    def test_repr(self, val):
        v1 = EventValue(val)
        expected = {
            1: "EventValue(1)",
            1.23: "EventValue(1.23)",
            "one": "EventValue('one')",
        }[val]
        result = repr(v1)
        assert result == expected

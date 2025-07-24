import unittest

from common.model.pydantic import SerializeType


class SerializeTypeTest(unittest.TestCase):
    def test_type(self):
        class SomeType(SerializeType):
            pass

        x = SomeType()
        assert (
            x._type == "SomeType"
        ), "Field _type should contain the class name as string value"

        d = x.model_dump()
        assert d == {
            "_type": "SomeType"
        }, "Field _type should be present after serialization"

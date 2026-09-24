import unittest

from raceops.snbt import IntArray, dumps, loads, response_value


class StorageProtocolTests(unittest.TestCase):
    def test_offline_uuid_signed_array_and_escaped_strings(self):
        payload = {"uuid": IntArray([-1941638236, -27115537, -1572596904, 860963649]),
                   "name": '测试 "quoted" \\ player', "records": [{"finished": True, "tick": 117005654}]}
        decoded = response_value("Storage xdu_race:state has the following contents: " + dumps(payload))
        self.assertEqual(decoded["uuid"], payload["uuid"])
        self.assertIsInstance(decoded["uuid"], IntArray)
        self.assertEqual(decoded["name"], payload["name"])
        self.assertEqual(decoded["records"][0]["tick"], 117005654)

    def test_truncated_or_ambiguous_storage_is_not_accepted(self):
        for text in ('{players:[{name:"Alice"}, ...', '{a:1,a:2}', '{a:"unfinished}',
                     '[I;1,"not an int"]', '{a:1} garbage'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                loads(text)

    def test_nested_values_preserve_numeric_meaning(self):
        self.assertEqual(loads('{flags:[1b,0b],time:12345678901L,pos:[1.25d,-3.5f],state:"IDLE"}'),
                         {"flags": [1, 0], "time": 12345678901, "pos": [1.25, -3.5], "state": "IDLE"})


if __name__ == "__main__":
    unittest.main()

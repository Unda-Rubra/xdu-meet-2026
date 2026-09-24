import unittest

from raceops.identity import offline_uuid, validate_roster


class OfflineIdentityTests(unittest.TestCase):
    def roster(self):
        return {"schema_version": 1, "event_id": "event", "grand_prix_round": 1,
                "groups": {g: [{"name": name, "uuid": offline_uuid(name)}]
                           for g, name in zip("ABC", ["Alice", "Bob", "Carol"])}}

    def test_case_aliases_cannot_enter_different_groups(self):
        roster = self.roster()
        roster["groups"]["B"] = [{"name": "ALICE", "uuid": offline_uuid("ALICE")}]
        with self.assertRaisesRegex(ValueError, "case-ambiguous"):
            validate_roster(roster, "event", 1)

    def test_forged_uuid_does_not_pass_offline_name_binding(self):
        roster = self.roster()
        roster["groups"]["A"][0]["uuid"] = offline_uuid("SomeoneElse")
        with self.assertRaisesRegex(ValueError, "Offline UUID"):
            validate_roster(roster, "event", 1)

    def test_wrong_round_and_empty_groups_fail_admission(self):
        with self.assertRaises(ValueError):
            validate_roster(self.roster(), "event", 2)
        roster = self.roster()
        roster["groups"]["C"] = []
        with self.assertRaises(ValueError):
            validate_roster(roster, "event", 1)


if __name__ == "__main__":
    unittest.main()

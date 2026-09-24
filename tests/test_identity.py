import unittest

from raceops.identity import offline_uuid, validate_roster


class OfflineIdentityTests(unittest.TestCase):
    event = {"event_id": "event", "grand_prix_rounds": 7}
    def roster(self):
        return {"schema_version": 1, "event_id": "event", "grand_prix_round": 1,
                "groups": {g: [{"name": name, "uuid": offline_uuid(name)}]
                           for g, name in zip("ABC", ["Alice", "Bob", "Carol"])}}

    def test_case_aliases_cannot_enter_different_groups(self):
        roster = self.roster()
        roster["groups"]["B"] = [{"name": "ALICE", "uuid": offline_uuid("ALICE")}]
        with self.assertRaisesRegex(ValueError, "case-ambiguous"):
            validate_roster(roster, self.event, 1)

    def test_forged_uuid_does_not_pass_offline_name_binding(self):
        roster = self.roster()
        roster["groups"]["A"][0]["uuid"] = offline_uuid("SomeoneElse")
        with self.assertRaisesRegex(ValueError, "Offline UUID"):
            validate_roster(roster, self.event, 1)

    def test_wrong_round_and_empty_groups_fail_admission(self):
        with self.assertRaises(ValueError):
            validate_roster(self.roster(), self.event, 2)
        roster = self.roster()
        roster["groups"]["C"] = []
        with self.assertRaises(ValueError):
            validate_roster(roster, self.event, 1)

    def test_seventh_round_accepts_two_groups_and_eighth_refused(self):
        roster = self.roster()
        del roster["groups"]["C"]
        roster["grand_prix_round"] = 7
        result = validate_roster(roster, self.event, 7)
        self.assertEqual(set(result["groups"]), {"A", "B"})
        roster["grand_prix_round"] = 8
        with self.assertRaises(ValueError):
            validate_roster(roster, self.event, 8)

    def test_configured_round_limit_and_boolean_rejected(self):
        roster = self.roster()
        roster["grand_prix_round"] = 7
        with self.assertRaises(ValueError):
            validate_roster(roster, {**self.event, "grand_prix_rounds": 5}, 7)
        with self.assertRaises(ValueError):
            validate_roster(self.roster(), {**self.event, "grand_prix_rounds": True}, 1)

    def test_invalid_subset_and_overfull_group_rejected(self):
        roster = self.roster()
        del roster["groups"]["B"]
        with self.assertRaises(ValueError):
            validate_roster(roster, self.event, 1)
        roster = self.roster()
        roster["groups"]["A"] = [{"name": f"Player{i}", "uuid": offline_uuid(f"Player{i}")} for i in range(18)]
        with self.assertRaises(ValueError):
            validate_roster(roster, self.event, 1)


if __name__ == "__main__":
    unittest.main()

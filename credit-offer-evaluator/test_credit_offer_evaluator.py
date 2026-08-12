import unittest
from datetime import date

from credit_offer_evaluator import evaluate_offer


class EvaluatorTests(unittest.TestCase):
    def evaluate(self, offer):
        return evaluate_offer(
            offer,
            as_of=date(2026, 8, 11),
            min_net_value=500,
            review_min_value=100,
            stale_after_days=120,
        )

    def test_amex_points_are_worth_one_point_five_cents(self):
        row = self.evaluate(
            {
                "name": "Amex",
                "points_program": "amex_membership_rewards",
                "points": 100_000,
                "annual_fee": 695,
                "eligible": True,
                "expires_on": "2026-09-01",
            }
        )
        self.assertEqual(row["points_value"], 1500)
        self.assertEqual(row["estimated_net_value"], 805)
        self.assertEqual(row["decision"], "CONSIDER")

    def test_chase_points_are_worth_two_cents(self):
        row = self.evaluate(
            {
                "name": "Chase",
                "points_program": "chase_ultimate_rewards",
                "points": 60_000,
                "annual_fee": 95,
                "eligible": True,
                "expires_on": "2026-09-01",
            }
        )
        self.assertEqual(row["estimated_net_value"], 1105)

    def test_other_points_are_worth_one_cent(self):
        row = self.evaluate(
            {
                "name": "Hotel",
                "points_program": "other",
                "points": 160_000,
                "annual_fee": 99,
                "eligible": True,
                "expires_on": "2026-09-01",
            }
        )
        self.assertEqual(row["estimated_net_value"], 1501)

    def test_already_applied_is_excluded_even_with_high_value(self):
        row = self.evaluate(
            {
                "name": "Already opened",
                "points_program": "chase_ultimate_rewards",
                "points": 200_000,
                "annual_fee": 900,
                "already_applied": True,
                "eligible": True,
                "expires_on": "2026-09-01",
            }
        )
        self.assertEqual(row["decision"], "EXCLUDE")
        self.assertIn("already applied", row["reason"])


if __name__ == "__main__":
    unittest.main()

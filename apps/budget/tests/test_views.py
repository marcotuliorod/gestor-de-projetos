from decimal import Decimal

from rest_framework.test import APIClient, APITestCase

from apps.budget.models import BudgetSettings


class BudgetViewTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

    def test_get_returns_expected_shape(self):
        response = self.client.get("/api/budget/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for key in (
            "quota_total_usd",
            "used_usd",
            "pct",
            "color",
            "should_pause_nightly",
            "distribution",
            "weeks",
        ):
            self.assertIn(key, data)
        # Decimal deve virar número no JSON, não string (response.data ainda
        # seria o objeto Python cru, pré-serialização — .json() é o que o
        # frontend de fato recebe).
        self.assertIsInstance(data["quota_total_usd"], (int, float))

    def test_post_updates_settings(self):
        response = self.client.post(
            "/api/budget/",
            {"quota_total_usd": 42.5, "personal_reserve_pct": 20, "pause_threshold_pct": 90},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["quota_total_usd"], 42.5)

        settings_obj = BudgetSettings.load()
        self.assertEqual(settings_obj.quota_total_usd, Decimal("42.50"))
        self.assertEqual(settings_obj.personal_reserve_pct, 20)
        self.assertEqual(settings_obj.pause_threshold_pct, 90)

    def test_post_partial_update_keeps_other_fields(self):
        self.client.post("/api/budget/", {"quota_total_usd": 10}, format="json")
        self.client.post("/api/budget/", {"pause_threshold_pct": 50}, format="json")

        settings_obj = BudgetSettings.load()
        self.assertEqual(settings_obj.quota_total_usd, Decimal("10.00"))
        self.assertEqual(settings_obj.pause_threshold_pct, 50)

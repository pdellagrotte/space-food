"""Rank credit-card and bank offers from a JSON input file.

The evaluator intentionally stays simple: it estimates first-year value, removes
clearly ineligible/stale offers, and writes a ranked CSV for human review.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any


POINT_VALUES_CPP = {
    "amex": 1.5,
    "amex_membership_rewards": 1.5,
    "american_express_membership_rewards": 1.5,
    "chase": 2.0,
    "chase_ultimate_rewards": 2.0,
    "ultimate_rewards": 2.0,
}

DECISION_ORDER = {"CONSIDER": 0, "REVIEW": 1, "SKIP": 2, "EXCLUDE": 3}


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        return date.fromisoformat(normalized[:10])


def as_money(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    return float(value)


def point_value_cpp(offer: dict[str, Any]) -> float:
    program = str(offer.get("points_program", "other")).strip().lower()
    return POINT_VALUES_CPP.get(program, 1.0)


def evaluate_offer(
    offer: dict[str, Any],
    *,
    as_of: date,
    min_net_value: float,
    review_min_value: float,
    stale_after_days: int,
) -> dict[str, Any]:
    points = as_money(offer.get("points"))
    cpp = point_value_cpp(offer)
    points_value = points * cpp / 100
    cash_bonus = as_money(offer.get("cash_bonus"))
    first_year_perks = as_money(offer.get("first_year_perks_value"))
    annual_fee = as_money(offer.get("annual_fee"))
    net_value = points_value + cash_bonus + first_year_perks - annual_fee

    expires_on = parse_date(offer.get("expires_on"))
    email_date = parse_date(offer.get("source_email_timestamp"))
    eligibility = offer.get("eligible", "unknown")
    reasons: list[str] = []

    if offer.get("already_applied"):
        reasons.append("already applied")
    if offer.get("already_has_product"):
        reasons.append("already has product")
    if offer.get("bonus_received_before"):
        reasons.append("bonus received before")
    if eligibility is False:
        reasons.append("not eligible")
    if expires_on and expires_on < as_of:
        reasons.append(f"expired {expires_on.isoformat()}")
    if not expires_on and email_date:
        age_days = (as_of - email_date).days
        if age_days > stale_after_days:
            reasons.append(f"email is stale ({age_days} days old with no deadline)")

    if reasons:
        decision = "EXCLUDE"
        reason = "; ".join(reasons)
    elif eligibility == "unknown" or offer.get("metadata_complete") is False:
        decision = "REVIEW"
        reason = "verify eligibility or missing terms before applying"
    elif net_value >= min_net_value:
        decision = "CONSIDER"
        reason = f"estimated net first-year value is ${net_value:,.2f}"
    elif net_value >= review_min_value:
        decision = "REVIEW"
        reason = f"positive but modest estimated value of ${net_value:,.2f}"
    else:
        decision = "SKIP"
        reason = f"estimated net value is below ${review_min_value:,.2f}"

    return {
        "name": offer.get("name", "Unnamed offer"),
        "issuer": offer.get("issuer", ""),
        "decision": decision,
        "estimated_net_value": round(net_value, 2),
        "points_value": round(points_value, 2),
        "cash_bonus": round(cash_bonus, 2),
        "first_year_perks_value": round(first_year_perks, 2),
        "annual_fee": round(annual_fee, 2),
        "minimum_requirement": offer.get("minimum_requirement", ""),
        "expires_on": expires_on.isoformat() if expires_on else "",
        "reason": reason,
        "source_email_subject": offer.get("source_email_subject", ""),
        "source_email_sender": offer.get("source_email_sender", ""),
        "source_email_timestamp": offer.get("source_email_timestamp", ""),
        "source_email_url": offer.get("source_email_url", ""),
    }


def load_offers(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    offers = payload.get("offers") if isinstance(payload, dict) else payload
    if not isinstance(offers, list):
        raise ValueError("Input must be a JSON list or an object with an 'offers' list.")
    if not all(isinstance(item, dict) for item in offers):
        raise ValueError("Every offer must be a JSON object.")
    return offers


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["name", "decision", "reason"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON file containing offers")
    parser.add_argument("--output", type=Path, default=Path("offer_results.csv"))
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--min-net-value", type=float, default=500.0)
    parser.add_argument("--review-min-value", type=float, default=100.0)
    parser.add_argument("--stale-after-days", type=int, default=120)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    offers = load_offers(args.input)
    rows = [
        evaluate_offer(
            offer,
            as_of=args.as_of,
            min_net_value=args.min_net_value,
            review_min_value=args.review_min_value,
            stale_after_days=args.stale_after_days,
        )
        for offer in offers
    ]
    rows.sort(key=lambda row: (DECISION_ORDER[row["decision"]], -row["estimated_net_value"]))
    write_csv(args.output, rows)
    counts = {decision: sum(row["decision"] == decision for row in rows) for decision in DECISION_ORDER}
    print(f"Wrote {len(rows)} offers to {args.output}")
    print(" | ".join(f"{key}: {value}" for key, value in counts.items()))


if __name__ == "__main__":
    main()

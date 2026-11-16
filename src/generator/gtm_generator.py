"""Deterministic Synthetic Data Generator for Canonical GTM Lakehouse.

Generates coordinated B2B SaaS RevOps datasets across accounts, contacts,
opportunities, campaigns, daily marketing costs, campaign touches, and product events.
Includes specific ground-truth scenarios for Agent evaluation.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import random
from typing import Dict, List, Optional
from faker import Faker


@dataclass
class GTMDataset:
    accounts: List[dict]
    contacts: List[dict]
    opportunities: List[dict]
    campaigns: List[dict]
    campaign_daily_costs: List[dict]
    campaign_touches: List[dict]
    product_events: List[dict]


class GTMDataGenerator:
    """Generates coordinated GTM datasets with embedded ground-truth RevOps scenarios."""

    def __init__(self, seed: int = 42, total_accounts: int = 30):
        self.seed = seed
        self.total_accounts = total_accounts
        self.fake = Faker()
        Faker.seed(seed)
        random.seed(seed)

        # Baseline timeline: Q4 2024
        self.q4_start = datetime(2024, 10, 1, 0, 0, tzinfo=timezone.utc)
        self.q4_end = datetime(2024, 12, 31, 23, 59, tzinfo=timezone.utc)

    def generate_all(self) -> GTMDataset:
        """Generate all coordinated datasets."""
        accounts = self._generate_accounts()
        contacts = self._generate_contacts(accounts)
        opportunities = self._generate_opportunities(accounts)
        campaigns = self._generate_campaigns()
        daily_costs = self._generate_campaign_daily_costs(campaigns)
        touches = self._generate_campaign_touches(contacts, campaigns)
        product_events = self._generate_product_events(accounts)

        return GTMDataset(
            accounts=accounts,
            contacts=contacts,
            opportunities=opportunities,
            campaigns=campaigns,
            campaign_daily_costs=daily_costs,
            campaign_touches=touches,
            product_events=product_events,
        )

    # -----------------------------------------------------------------------
    # 1. Accounts Generation
    # -----------------------------------------------------------------------
    def _generate_accounts(self) -> List[dict]:
        accounts = []

        # Ground-truth Target & Control Accounts
        ground_truth_accounts = [
            # Target 1: Enterprise, Open Expansion deal in Q4, WAU drops > 60%
            {
                "account_id": "acc_ent_001",
                "name": "Acme Corporation",
                "domain": "acme.com",
                "tier": "Enterprise",
                "industry": "SaaS & Cloud Infrastructure",
                "arr": Decimal("285000.00"),
                "health_score": 58,
                "lifecycle_stage": "Customer",
                "created_at": datetime(2023, 3, 10, 9, 30, tzinfo=timezone.utc),
                "num_employees": 1400,
            },
            # Target 2: Enterprise, Open Expansion deal in Q4, WAU drops > 50%
            {
                "account_id": "acc_ent_002",
                "name": "NovaTech Solutions",
                "domain": "novatech.io",
                "tier": "Enterprise",
                "industry": "FinTech",
                "arr": Decimal("420000.00"),
                "health_score": 52,
                "lifecycle_stage": "Customer",
                "created_at": datetime(2023, 6, 15, 11, 0, tzinfo=timezone.utc),
                "num_employees": 2200,
            },
            # Control 1: Enterprise, Open Expansion in Q4, but WAU GROWING (+16%)
            {
                "account_id": "acc_ent_003",
                "name": "CloudPeak Systems",
                "domain": "cloudpeak.net",
                "tier": "Enterprise",
                "industry": "Cybersecurity",
                "arr": Decimal("310000.00"),
                "health_score": 89,
                "lifecycle_stage": "Customer",
                "created_at": datetime(2023, 1, 20, 14, 0, tzinfo=timezone.utc),
                "num_employees": 950,
            },
            # Control 2: Enterprise, WAU drops > 50%, but Open Deal is RENEWAL (NOT Expansion)
            {
                "account_id": "acc_ent_004",
                "name": "Helios Financial",
                "domain": "heliosfin.com",
                "tier": "Enterprise",
                "industry": "Banking & Finance",
                "arr": Decimal("520000.00"),
                "health_score": 48,
                "lifecycle_stage": "Customer",
                "created_at": datetime(2022, 11, 5, 8, 45, tzinfo=timezone.utc),
                "num_employees": 3800,
            },
            # Control 3: Open Expansion in Q4, WAU drops > 50%, but tier is MID-MARKET (NOT Enterprise)
            {
                "account_id": "acc_mid_005",
                "name": "Zenith Logic",
                "domain": "zenithlogic.org",
                "tier": "Mid-Market",
                "industry": "HealthTech",
                "arr": Decimal("75000.00"),
                "health_score": 51,
                "lifecycle_stage": "Customer",
                "created_at": datetime(2023, 8, 12, 16, 20, tzinfo=timezone.utc),
                "num_employees": 210,
            },
        ]
        accounts.extend(ground_truth_accounts)

        # Remaining Random Accounts
        industries = ["SaaS", "FinTech", "HealthTech", "E-Commerce", "Logistics", "EdTech"]
        tiers = ["Enterprise", "Mid-Market", "SMB"]
        stages = ["Customer", "Customer", "Prospect", "Customer", "Churned"]

        for i in range(len(ground_truth_accounts) + 1, self.total_accounts + 1):
            tier = random.choices(tiers, weights=[0.25, 0.45, 0.30])[0]
            company_name = self.fake.company()
            domain = company_name.lower().replace(" ", "").replace(",", "").replace("-", "") + ".com"
            
            if tier == "Enterprise":
                arr = Decimal(str(random.randint(150, 600) * 1000))
                emp = random.randint(1000, 5000)
            elif tier == "Mid-Market":
                arr = Decimal(str(random.randint(40, 140) * 1000))
                emp = random.randint(150, 999)
            else:
                arr = Decimal(str(random.randint(10, 39) * 1000))
                emp = random.randint(20, 149)

            created_days_ago = random.randint(120, 700)
            created_at = self.q4_start - timedelta(days=created_days_ago)

            accounts.append({
                "account_id": f"acc_{i:03d}",
                "name": company_name,
                "domain": domain,
                "tier": tier,
                "industry": random.choice(industries),
                "arr": arr,
                "health_score": random.randint(35, 95),
                "lifecycle_stage": random.choice(stages),
                "created_at": created_at,
                "num_employees": emp,
            })

        return accounts

    # -----------------------------------------------------------------------
    # 2. Contacts Generation
    # -----------------------------------------------------------------------
    def _generate_contacts(self, accounts: List[dict]) -> List[dict]:
        contacts = []
        roles = ["Decision Maker", "Champion", "Influencer", "End User"]
        titles_map = {
            "Decision Maker": ["VP of Engineering", "Chief Technology Officer", "VP of Sales", "Chief Revenue Officer"],
            "Champion": ["Staff Engineer", "Director of Product", "RevOps Director", "Head of Data"],
            "Influencer": ["Senior Architect", "Lead Developer", "Sales Operations Manager"],
            "End User": ["Software Engineer", "Account Executive", "Data Analyst"],
        }
        statuses = ["Lead", "MQL", "SQL", "Opportunity", "Disqualified"]

        contact_idx = 1
        for acc in accounts:
            # 2 to 5 contacts per account
            count = random.randint(2, 5)
            for j in range(count):
                role = roles[j % len(roles)]
                first_name = self.fake.first_name()
                last_name = self.fake.last_name()
                email = f"{first_name.lower()}.{last_name.lower()}@{acc['domain']}"
                title = random.choice(titles_map[role])
                is_primary = (j == 0)

                created_at = acc["created_at"] + timedelta(days=random.randint(5, 60))
                if created_at > self.q4_end:
                    created_at = self.q4_start

                status = "Opportunity" if acc["account_id"] in ["acc_ent_001", "acc_ent_002"] else random.choice(statuses)

                contacts.append({
                    "contact_id": f"cnt_{contact_idx:04d}",
                    "account_id": acc["account_id"],
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "title": title,
                    "role": role,
                    "is_primary": is_primary,
                    "created_at": created_at,
                    "status": status,
                })
                contact_idx += 1

        return contacts

    # -----------------------------------------------------------------------
    # 3. Opportunities Generation
    # -----------------------------------------------------------------------
    def _generate_opportunities(self, accounts: List[dict]) -> List[dict]:
        opportunities = []

        # Ground-truth opportunities
        ground_truth_opps = [
            # Target 1: Open Expansion in Q4
            {
                "deal_id": "opp_exp_001",
                "account_id": "acc_ent_001",
                "deal_name": "Acme Global Core Platform Expansion",
                "deal_type": "Expansion",
                "stage": "Negotiation",
                "amount": Decimal("150000.00"),
                "close_date": date(2024, 12, 18),
                "is_closed": False,
                "is_won": False,
                "created_at": datetime(2024, 10, 5, 10, 0, tzinfo=timezone.utc),
            },
            # Target 2: Open Expansion in Q4
            {
                "deal_id": "opp_exp_002",
                "account_id": "acc_ent_002",
                "deal_name": "NovaTech Tier-1 Add-On Expansion",
                "deal_type": "Expansion",
                "stage": "Proposal/Quote",
                "amount": Decimal("95000.00"),
                "close_date": date(2024, 12, 28),
                "is_closed": False,
                "is_won": False,
                "created_at": datetime(2024, 10, 12, 14, 30, tzinfo=timezone.utc),
            },
            # Control 1: Open Expansion in Q4 (Healthy WAU)
            {
                "deal_id": "opp_exp_003",
                "account_id": "acc_ent_003",
                "deal_name": "CloudPeak Compute Expansion",
                "deal_type": "Expansion",
                "stage": "Negotiation",
                "amount": Decimal("120000.00"),
                "close_date": date(2024, 12, 20),
                "is_closed": False,
                "is_won": False,
                "created_at": datetime(2024, 10, 8, 9, 0, tzinfo=timezone.utc),
            },
            # Control 2: Open Renewal in Q4 (NOT Expansion)
            {
                "deal_id": "opp_ren_004",
                "account_id": "acc_ent_004",
                "deal_name": "Helios Annual Platform Renewal",
                "deal_type": "Renewal",
                "stage": "Negotiation",
                "amount": Decimal("520000.00"),
                "close_date": date(2024, 12, 10),
                "is_closed": False,
                "is_won": False,
                "created_at": datetime(2024, 10, 2, 11, 0, tzinfo=timezone.utc),
            },
            # Control 3: Open Expansion in Q4 (Mid-Market)
            {
                "deal_id": "opp_exp_005",
                "account_id": "acc_mid_005",
                "deal_name": "Zenith Seat Upgrade Expansion",
                "deal_type": "Expansion",
                "stage": "Negotiation",
                "amount": Decimal("25000.00"),
                "close_date": date(2024, 12, 22),
                "is_closed": False,
                "is_won": False,
                "created_at": datetime(2024, 10, 15, 13, 0, tzinfo=timezone.utc),
            },
        ]
        opportunities.extend(ground_truth_opps)

        # Remaining Opportunities across other accounts
        opp_idx = 6
        deal_types = ["New Business", "Expansion", "Renewal"]
        stages = ["Prospecting", "Qualification", "Proposal/Quote", "Negotiation", "Closed Won", "Closed Lost"]

        for acc in accounts:
            if acc["account_id"] in ["acc_ent_001", "acc_ent_002", "acc_ent_003", "acc_ent_004", "acc_mid_005"]:
                continue

            num_opps = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
            for _ in range(num_opps):
                stage = random.choice(stages)
                deal_type = random.choice(deal_types)
                is_closed = stage in ("Closed Won", "Closed Lost")
                is_won = (stage == "Closed Won")

                # Deal value scaled to account tier
                multiplier = 0.3 if deal_type == "Expansion" else 1.0
                amount = (acc["arr"] * Decimal(str(multiplier))).quantize(Decimal("0.01"))

                # Close date in Q4 or earlier
                close_day = random.randint(1, 85)
                close_dt = date(2024, 10, 1) + timedelta(days=close_day)
                created_dt = self.q4_start - timedelta(days=random.randint(10, 90))

                opportunities.append({
                    "deal_id": f"opp_{opp_idx:04d}",
                    "account_id": acc["account_id"],
                    "deal_name": f"{acc['name']} - {deal_type}",
                    "deal_type": deal_type,
                    "stage": stage,
                    "amount": amount,
                    "close_date": close_dt,
                    "is_closed": is_closed,
                    "is_won": is_won,
                    "created_at": created_dt,
                })
                opp_idx += 1

        return opportunities

    # -----------------------------------------------------------------------
    # 4. Campaigns Generation
    # -----------------------------------------------------------------------
    def _generate_campaigns(self) -> List[dict]:
        campaigns = [
            {
                "campaign_id": "cmp_001",
                "name": "Q4 Enterprise Security Webinar",
                "channel": "Webinar",
                "type": "Expansion",
                "status": "Completed",
                "budget": Decimal("25000.00"),
                "start_date": date(2024, 10, 1),
                "end_date": date(2024, 11, 15),
                "created_at": datetime(2024, 9, 15, 8, 0, tzinfo=timezone.utc),
            },
            {
                "campaign_id": "cmp_002",
                "name": "Google Ads - Enterprise RevOps High Intent",
                "channel": "Paid Search",
                "type": "Acquisition",
                "status": "Active",
                "budget": Decimal("60000.00"),
                "start_date": date(2024, 10, 1),
                "end_date": date(2024, 12, 31),
                "created_at": datetime(2024, 9, 20, 10, 0, tzinfo=timezone.utc),
            },
            {
                "campaign_id": "cmp_003",
                "name": "SaaS Breakthrough Summit 2024",
                "channel": "Conference",
                "type": "Brand",
                "status": "Completed",
                "budget": Decimal("45000.00"),
                "start_date": date(2024, 10, 20),
                "end_date": date(2024, 10, 24),
                "created_at": datetime(2024, 8, 1, 9, 0, tzinfo=timezone.utc),
            },
            {
                "campaign_id": "cmp_004",
                "name": "Executive Outbound Cold Cadence",
                "channel": "Outbound",
                "type": "Acquisition",
                "status": "Active",
                "budget": Decimal("15000.00"),
                "start_date": date(2024, 10, 1),
                "end_date": date(2024, 12, 31),
                "created_at": datetime(2024, 9, 25, 12, 0, tzinfo=timezone.utc),
            },
            {
                "campaign_id": "cmp_005",
                "name": "Product Adoption Email Nurture",
                "channel": "Email",
                "type": "Retention",
                "status": "Active",
                "budget": Decimal("10000.00"),
                "start_date": date(2024, 10, 1),
                "end_date": date(2024, 12, 31),
                "created_at": datetime(2024, 9, 10, 15, 0, tzinfo=timezone.utc),
            },
            {
                "campaign_id": "cmp_006",
                "name": "LinkedIn Ads - VP Sales & CRO Outreach",
                "channel": "Paid Search",
                "type": "Acquisition",
                "status": "Active",
                "budget": Decimal("35000.00"),
                "start_date": date(2024, 10, 15),
                "end_date": date(2024, 12, 31),
                "created_at": datetime(2024, 10, 1, 11, 0, tzinfo=timezone.utc),
            },
        ]
        return campaigns

    # -----------------------------------------------------------------------
    # 5. Campaign Daily Costs Generation
    # -----------------------------------------------------------------------
    def _generate_campaign_daily_costs(self, campaigns: List[dict]) -> List[dict]:
        daily_costs = []
        cost_idx = 1

        for cmp in campaigns:
            curr_date = cmp["start_date"]
            end_date = cmp["end_date"] or date(2024, 12, 31)

            # Daily budget approximation
            total_days = max(1, (end_date - curr_date).days + 1)
            target_daily_budget = float(cmp["budget"]) / total_days

            while curr_date <= end_date:
                # Add realistic variance (e.g. weekends lower for B2B)
                is_weekend = curr_date.weekday() >= 5
                factor = random.uniform(0.3, 0.6) if is_weekend else random.uniform(0.8, 1.3)
                cost = Decimal(str(round(target_daily_budget * factor, 2)))

                if cmp["channel"] in ("Paid Search", "Conference"):
                    impressions = int(float(cost) * random.uniform(15.0, 30.0))
                    clicks = int(impressions * random.uniform(0.02, 0.05))
                elif cmp["channel"] == "Webinar":
                    impressions = int(float(cost) * random.uniform(8.0, 15.0))
                    clicks = int(impressions * random.uniform(0.05, 0.10))
                else:
                    impressions = int(float(cost) * random.uniform(10.0, 20.0))
                    clicks = int(impressions * random.uniform(0.03, 0.08))

                created_at = datetime.combine(curr_date, time(23, 59, tzinfo=timezone.utc))

                daily_costs.append({
                    "cost_id": f"cst_{cost_idx:06d}",
                    "campaign_id": cmp["campaign_id"],
                    "date": curr_date,
                    "cost": cost,
                    "impressions": impressions,
                    "clicks": clicks,
                    "created_at": created_at,
                })
                cost_idx += 1
                curr_date += timedelta(days=1)

        return daily_costs

    # -----------------------------------------------------------------------
    # 6. Campaign Touches Generation
    # -----------------------------------------------------------------------
    def _generate_campaign_touches(self, contacts: List[dict], campaigns: List[dict]) -> List[dict]:
        touches = []
        touch_idx = 1
        touch_types = ["First Touch", "Lead Creation", "Opportunity Creation", "Closed Won Influence"]

        for contact in contacts:
            # 1 to 4 touches per contact
            num_touches = random.randint(1, 4)
            for _ in range(num_touches):
                cmp = random.choice(campaigns)
                touch_day = random.randint(1, 90)
                touch_dt = self.q4_start + timedelta(
                    days=touch_day,
                    hours=random.randint(8, 18),
                    minutes=random.randint(0, 59),
                )
                if touch_dt > self.q4_end:
                    touch_dt = self.q4_end - timedelta(hours=random.randint(1, 12))

                touches.append({
                    "touch_id": f"tch_{touch_idx:06d}",
                    "contact_id": contact["contact_id"],
                    "campaign_id": cmp["campaign_id"],
                    "channel": cmp["channel"],
                    "touch_type": random.choice(touch_types),
                    "touch_time": touch_dt,
                })
                touch_idx += 1

        return touches

    # -----------------------------------------------------------------------
    # 7. Product Events Telemetry Generation (with Ground-Truth WAU Drops)
    # -----------------------------------------------------------------------
    def _generate_product_events(self, accounts: List[dict]) -> List[dict]:
        events = []
        event_idx = 1
        event_names = ["login", "dashboard_view", "report_exported", "feature_used", "invite_member"]
        features = ["Analytics", "Export Engine", "Pipeline Board", "Integrations", "User Admin"]

        # Number of weeks in Q4 (13 weeks)
        for acc in accounts:
            acc_id = acc["account_id"]
            tier = acc["tier"]

            for week_num in range(13):
                week_start_dt = self.q4_start + timedelta(weeks=week_num)

                # Determine active users this week based on target / control profiles
                if acc_id == "acc_ent_001":
                    # Acme Corp: Drop from 40 active users (Oct) -> 12 active users (Dec) (>65% drop!)
                    if week_num < 4:
                        active_user_count = random.randint(38, 42)  # Early Q4: ~40
                    elif week_num < 8:
                        active_user_count = random.randint(25, 30)  # Mid Q4: ~28
                    else:
                        active_user_count = random.randint(11, 14)  # Late Q4: ~12
                elif acc_id == "acc_ent_002":
                    # NovaTech: Drop from 50 active users (Oct) -> 24 active users (Dec) (>50% drop!)
                    if week_num < 4:
                        active_user_count = random.randint(48, 52)  # Early Q4: ~50
                    elif week_num < 8:
                        active_user_count = random.randint(35, 40)
                    else:
                        active_user_count = random.randint(22, 26)  # Late Q4: ~24
                elif acc_id == "acc_ent_003":
                    # CloudPeak: Active users GROW from 30 -> 35
                    if week_num < 4:
                        active_user_count = random.randint(28, 31)
                    else:
                        active_user_count = random.randint(34, 37)
                elif acc_id == "acc_ent_004":
                    # Helios Financial: Drops 45 -> 18 (Renewal, not Expansion)
                    if week_num < 4:
                        active_user_count = random.randint(42, 47)
                    else:
                        active_user_count = random.randint(16, 20)
                elif acc_id == "acc_mid_005":
                    # Zenith Logic: Drops 30 -> 13 (Mid-Market)
                    if week_num < 4:
                        active_user_count = random.randint(28, 32)
                    else:
                        active_user_count = random.randint(12, 15)
                else:
                    # Generic accounts
                    base = 25 if tier == "Enterprise" else (12 if tier == "Mid-Market" else 5)
                    active_user_count = max(2, int(base * random.uniform(0.85, 1.15)))

                # Generate events for active users across the week
                for u_idx in range(1, active_user_count + 1):
                    user_id = f"usr_{acc_id}_{u_idx:03d}"
                    # Each active user triggers 3 to 8 events in this week
                    for _ in range(random.randint(3, 8)):
                        day_offset = random.randint(0, 6)
                        hour_offset = random.randint(8, 20)
                        minute_offset = random.randint(0, 59)
                        second_offset = random.randint(0, 59)
                        event_time = week_start_dt + timedelta(
                            days=day_offset,
                            hours=hour_offset,
                            minutes=minute_offset,
                            seconds=second_offset,
                        )
                        if event_time > self.q4_end:
                            event_time = self.q4_end - timedelta(minutes=random.randint(1, 60))

                        event_name = random.choice(event_names)
                        feat = random.choice(features) if event_name == "feature_used" else None
                        dur = random.randint(15, 1200)

                        events.append({
                            "event_id": f"evt_{event_idx:07d}",
                            "account_id": acc_id,
                            "user_id": user_id,
                            "event_name": event_name,
                            "feature_name": feat,
                            "session_duration_seconds": dur,
                            "event_time": event_time,
                        })
                        event_idx += 1

        return events


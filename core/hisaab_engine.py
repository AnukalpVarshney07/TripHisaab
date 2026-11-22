from decimal import Decimal, ROUND_HALF_UP


def round_money(val: float | Decimal) -> float:
    return float(Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate_hisaab(members: list[dict], expenses: list[dict]) -> dict:
    """
    Computes:
    - total_expenditure
    - member_count
    - per_head
    - member_stats: list of {user_id, name, email, paid, balance, status}
    - settlements: simplified list of {from_name, to_name, amount}
    """
    member_count = len(members)
    if member_count == 0:
        return {
            "total_expenditure": 0.0,
            "member_count": 0,
            "per_head": 0.0,
            "member_stats": [],
            "settlements": [],
        }

    # Map total paid per member (default 0.0 even if a member logged no expenses)
    paid_map: dict[str, float] = {m["id"]: 0.0 for m in members}
    total_exp = 0.0

    for exp in expenses:
        amt = float(exp.get("amount", 0.0))
        uid = exp.get("user_id")
        total_exp += amt
        if uid in paid_map:
            paid_map[uid] += amt

    total_exp = round_money(total_exp)
    per_head = round_money(total_exp / member_count)

    member_stats = []
    debtors = []   # owes money (balance < 0)
    creditors = [] # gets money back (balance > 0)

    for m in members:
        uid = m["id"]
        paid = round_money(paid_map[uid])
        balance = round_money(paid - per_head)

        if balance > 0.01:
            status = "gets_back"
            creditors.append({"name": m["name"], "amount": balance})
        elif balance < -0.01:
            status = "owes"
            debtors.append({"name": m["name"], "amount": abs(balance)})
        else:
            status = "settled"

        member_stats.append({
            "user_id": uid,
            "name": m["name"],
            "email": m.get("email", ""),
            "paid": paid,
            "balance": balance,
            "status": status,
        })

    # Sort largest amounts first for minimal transfers
    debtors.sort(key=lambda x: x["amount"], reverse=True)
    creditors.sort(key=lambda x: x["amount"], reverse=True)

    settlements = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor = debtors[i]
        creditor = creditors[j]
        transfer = round_money(min(debtor["amount"], creditor["amount"]))

        if transfer > 0.01:
            settlements.append({
                "from_name": debtor["name"],
                "to_name": creditor["name"],
                "amount": transfer,
            })

        debtor["amount"] = round_money(debtor["amount"] - transfer)
        creditor["amount"] = round_money(creditor["amount"] - transfer)

        if debtor["amount"] <= 0.01:
            i += 1
        if creditor["amount"] <= 0.01:
            j += 1

    # Sort member stats: highest positive balance first
    member_stats.sort(key=lambda x: x["balance"], reverse=True)

    return {
        "total_expenditure": total_exp,
        "member_count": member_count,
        "per_head": per_head,
        "member_stats": member_stats,
        "settlements": settlements,
    }


def format_whatsapp_summary(trip_name: str, join_code: str, hisaab: dict) -> str:
    lines = [
        f"*TRIP HISAAB — {trip_name.upper()}* ({join_code})",
        "━━━━━━━━━━━━━━━━━━━━",
        f"Total Spent: ₹{hisaab['total_expenditure']:,.2f}",
        f"Members: {hisaab['member_count']}",
        f"Per Head: ₹{hisaab['per_head']:,.2f}",
        "",
        "*MEMBER BREAKDOWN:*",
    ]
    for m in hisaab["member_stats"]:
        if m["status"] == "gets_back":
            tag = f"Gets back ₹{m['balance']:,.2f}"
        elif m["status"] == "owes":
            tag = f"Owes ₹{abs(m['balance']):,.2f}"
        else:
            tag = "Settled"
        lines.append(f"• {m['name']}: Paid ₹{m['paid']:,.2f} ({tag})")

    if hisaab["settlements"]:
        lines.append("")
        lines.append("*WHO PAYS WHOM:*")
        for s in hisaab["settlements"]:
            lines.append(f"• {s['from_name']} ➔ {s['to_name']}: ₹{s['amount']:,.2f}")

    return "\n".join(lines)
import asyncio
import flet as ft
from core.database import DatabaseError, add_expense, end_trip, get_trip_full_data
from core.utils import current_date_str, current_time_str
from ui.theme import (
    BG_CARD,
    BG_INPUT,
    BORDER_SUBTLE,
    BRAND_BLUE,
    BRAND_GOLD,
    BRAND_RED,
    BRAND_WHITE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    card_container,
    copy_to_clipboard,
    pill_button,
    section_label,
    styled_input,
)


def build_trip_view(page: ft.Page, user: dict, trip: dict, on_back, on_view_summary, show_snack):
    is_host = trip["host_id"] == user["id"]
    total_text = ft.Text("₹0.00", size=34, weight=ft.FontWeight.W_600, color=BRAND_WHITE)
    members_text = ft.Text("Syncing members...", size=12, color=TEXT_MUTED)
    expenses_list = ft.Column(spacing=8)

    sync_state = {
        "active": True,
        "last_fingerprint": None,
        "dialog_open": False,
    }

    def handle_back(e=None):
        sync_state["active"] = False
        on_back()

    def copy_code(e):
        copy_to_clipboard(page, trip["join_code"])
        show_snack(f"Trip Code {trip['join_code']} copied!")

    def render_trip_data(data: dict, force: bool = False):
        current_trip = data["trip"]
        members = data["members"]
        expenses = data["expenses"]

        # If host ended the trip, stop polling and jump everyone to Final Hisaab
        if current_trip["status"] == "ended":
            sync_state["active"] = False
            on_view_summary(current_trip)
            return

        total = sum(float(x["amount"]) for x in expenses)
        fingerprint = (
            current_trip["status"],
            len(members),
            len(expenses),
            round(total, 2),
            expenses[0]["id"] if expenses else None,
        )

        if not force and fingerprint == sync_state["last_fingerprint"]:
            return
        sync_state["last_fingerprint"] = fingerprint

        total_text.value = f"₹{total:,.2f}"
        member_names = ", ".join([m["name"] for m in members])
        members_text.value = f"{len(members)} Members  •  {member_names}"

        expenses_list.controls.clear()
        if not expenses:
            expenses_list.controls.append(
                card_container(
                    ft.Text(
                        "No expenses logged yet. Tap 'Log Expense' to add the first entry.",
                        color=TEXT_MUTED,
                        size=13,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    padding=26,
                )
            )
        else:
            for exp in expenses:
                payer_name = exp.get("users", {}).get("name", "Member")
                is_mine = exp["user_id"] == user["id"]

                item = ft.Container(
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(exp["remarks"], size=15, weight=ft.FontWeight.W_500, color=TEXT_PRIMARY),
                                    ft.Text(
                                        f"{'You' if is_mine else payer_name}  •  {exp['expense_date']}, {exp['expense_time']}",
                                        size=12,
                                        color=TEXT_MUTED,
                                    ),
                                ],
                                spacing=3,
                                expand=True,
                            ),
                            ft.Text(
                                f"₹{float(exp['amount']):,.2f}",
                                size=16,
                                weight=ft.FontWeight.W_600,
                                color=BRAND_GOLD if is_mine else TEXT_PRIMARY,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    bgcolor=BG_CARD,
                    padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                    border_radius=14,
                    border=ft.Border.all(1, BORDER_SUBTLE),
                )
                expenses_list.controls.append(item)

        page.update()

    def refresh_trip_data(silent: bool = False):
        try:
            data = get_trip_full_data(trip["id"])
            render_trip_data(data, force=not silent)
        except DatabaseError as err:
            if not silent:
                show_snack(str(err), is_error=True)
        except Exception:
            pass

    async def auto_sync_loop():
        while sync_state["active"]:
            await asyncio.sleep(4)
            if not sync_state["active"] or sync_state["dialog_open"]:
                continue
            try:
                data = await asyncio.to_thread(get_trip_full_data, trip["id"])
                if sync_state["active"]:
                    render_trip_data(data, force=False)
            except Exception:
                pass

    def open_add_expense_dialog(e):
        sync_state["dialog_open"] = True
        amt_field = styled_input(hint="Enter Amount (₹)", keyboard_type=ft.KeyboardType.NUMBER)
        rem_field = styled_input(hint="Enter Remarks (Dinner, Cab, Fuel...)")
        date_field = styled_input(label="Date", value=current_date_str())
        time_field = styled_input(label="Time", value=current_time_str())

        def close_dlg(_=None):
            sync_state["dialog_open"] = False
            dlg.open = False
            page.pop_dialog()
            page.update()

        def save_expense(ev):
            try:
                amt = float((amt_field.value or "").strip())
                if amt <= 0:
                    raise ValueError()
            except ValueError:
                show_snack("Enter a valid positive amount.", is_error=True)
                return

            rem = (rem_field.value or "").strip()
            if not rem:
                show_snack("Please add short remarks.", is_error=True)
                return

            try:
                add_expense(
                    trip_id=trip["id"],
                    user_id=user["id"],
                    amount=amt,
                    remarks=rem,
                    exp_date=date_field.value or current_date_str(),
                    exp_time=time_field.value or current_time_str(),
                )
                close_dlg()
                show_snack("Expense added!")
                refresh_trip_data(silent=False)
            except DatabaseError as err:
                show_snack(str(err), is_error=True)

        save_btn = pill_button("Continue", on_click=save_expense, bg=BRAND_WHITE, fg="#000000")

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=BG_CARD,
            shape=ft.RoundedRectangleBorder(radius=18),
            title=ft.Text("Log Expense", size=19, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
            content=ft.Container(
                width=400,
                content=ft.Column(
                    [amt_field, rem_field, date_field, time_field],
                    tight=True,
                    spacing=12,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", style=ft.ButtonStyle(color=TEXT_SECONDARY), on_click=close_dlg),
                save_btn,
            ],
        )
        page.show_dialog(dlg)

    def confirm_end_trip(e):
        sync_state["dialog_open"] = True

        def close_end_dlg(_=None):
            sync_state["dialog_open"] = False
            dlg.open = False
            page.pop_dialog()
            page.update()

        def execute_end(ev):
            try:
                ended = end_trip(trip["id"], user["id"])
                sync_state["active"] = False
                close_end_dlg()
                show_snack("Trip ended! Calculating Hisaab...")
                on_view_summary(ended)
            except DatabaseError as err:
                show_snack(str(err), is_error=True)

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=BG_CARD,
            shape=ft.RoundedRectangleBorder(radius=18),
            title=ft.Text("End Trip & Calculate Hisaab?", size=18, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
            content=ft.Text(
                "This locks further expense entries and computes the total expenditure, per-head share, and outstanding balances.",
                color=TEXT_SECONDARY,
                size=13,
            ),
            actions=[
                ft.TextButton("Cancel", style=ft.ButtonStyle(color=TEXT_SECONDARY), on_click=close_end_dlg),
                pill_button("End Trip", on_click=execute_end, bg=BRAND_RED, fg=BRAND_WHITE),
            ],
        )
        page.show_dialog(dlg)

    code_pill = ft.Container(
        content=ft.Row(
            [
                ft.Text(trip["join_code"], size=12, weight=ft.FontWeight.W_600, color=BRAND_GOLD),
                ft.Icon(ft.Icons.COPY, size=13, color=BRAND_GOLD),
            ],
            spacing=6,
            tight=True,
        ),
        bgcolor=BG_INPUT,
        border=ft.Border.all(1, BORDER_SUBTLE),
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=20,
        ink=True,
        on_click=copy_code,
    )

    top_bar = ft.Row(
        [
            ft.Row(
                [
                    ft.IconButton(ft.Icons.ARROW_BACK, icon_size=20, icon_color=TEXT_PRIMARY, on_click=handle_back),
                    ft.Text(trip["trip_name"], size=19, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                ],
                spacing=4,
            ),
            ft.Row(
                [
                    code_pill,
                    ft.IconButton(
                        ft.Icons.REFRESH,
                        icon_size=20,
                        icon_color=TEXT_SECONDARY,
                        tooltip="Sync Now",
                        on_click=lambda e: refresh_trip_data(silent=False),
                    ),
                ],
                spacing=4,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    summary_banner = card_container(
        ft.Column(
            [
                ft.Row(
                    [
                        section_label("Total Expenditure"),
                        ft.Row(
                            [
                                ft.Container(width=6, height=6, border_radius=3, bgcolor="#22C55E"),
                                ft.Text("LIVE SYNC", size=10, weight=ft.FontWeight.W_600, color="#22C55E"),
                            ],
                            spacing=4,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                total_text,
                members_text,
            ],
            spacing=6,
        ),
        padding=22,
        border_color=BRAND_BLUE,
    )

    action_buttons = [
        pill_button("Log Expense", on_click=open_add_expense_dialog, icon=ft.Icons.ADD, bg=BRAND_WHITE, fg="#000000", expand=True),
    ]
    if is_host:
        action_buttons.append(
            pill_button("End Trip", on_click=confirm_end_trip, icon=ft.Icons.FLAG, bg=BRAND_RED, fg=BRAND_WHITE, expand=True)
        )

    refresh_trip_data(silent=False)
    page.run_task(auto_sync_loop)

    return ft.Container(
        content=ft.Column(
            [
                top_bar,
                summary_banner,
                ft.Row(action_buttons, spacing=10),
                ft.Container(height=6),
                section_label("Expense Ledger"),
                expenses_list,
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=12,
        ),
        expand=True,
    )
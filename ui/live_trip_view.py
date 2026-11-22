import asyncio
import flet as ft
from core.database import DatabaseError, add_expense, end_trip, get_trip_full_data
from core.hisaab_engine import calculate_hisaab
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
    set_pill_loading,
    styled_input,
)


def build_live_trip_view(page: ft.Page, user: dict, trip: dict, on_back, on_trip_ended, show_snack):
    is_host = trip["host_id"] == user["id"]
    sync_state = {"active": True, "last_sig": None, "dialog_open": False, "current_trip": dict(trip)}

    total_text = ft.Text("₹0.00", size=22, weight=ft.FontWeight.W_600, color=BRAND_WHITE)
    per_head_text = ft.Text("₹0.00", size=22, weight=ft.FontWeight.W_600, color=BRAND_GOLD)
    per_head_label = section_label("Per Head (0)")
    members_row = ft.Row(wrap=True, spacing=8, run_spacing=8)
    expenses_col = ft.Column(spacing=10)

    def leave_view():
        sync_state["active"] = False
        on_back()

    def render_data(data: dict, force: bool = False):
        current_trip = data["trip"]
        sync_state["current_trip"] = current_trip
        if current_trip.get("status") == "ended" and sync_state["active"]:
            sync_state["active"] = False
            on_trip_ended(current_trip)
            return

        members = data["members"]
        expenses = data["expenses"]
        sig = (
            current_trip.get("status"),
            len(members),
            tuple(m["id"] for m in members),
            len(expenses),
            tuple((e["id"], e["amount"], e.get("remarks")) for e in expenses),
        )
        if not force and sig == sync_state["last_sig"]:
            return
        sync_state["last_sig"] = sig

        hisaab = calculate_hisaab(members, expenses)
        total_text.value = f"₹{hisaab['total_expenditure']:,.2f}"
        per_head_label.value = f"Per Head ({hisaab['member_count']})"
        per_head_text.value = f"₹{hisaab['per_head']:,.2f}"

        members_row.controls.clear()
        for m in members:
            m_tag = m["name"]
            if m["id"] == current_trip["host_id"]:
                m_tag = f"{m_tag} • Host"
            members_row.controls.append(
                ft.Container(
                    content=ft.Text(m_tag, size=12, weight=ft.FontWeight.W_500, color=TEXT_PRIMARY),
                    bgcolor=BG_INPUT,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    border_radius=20,
                    border=ft.Border.all(1, BORDER_SUBTLE),
                )
            )

        expenses_col.controls.clear()
        if not expenses:
            expenses_col.controls.append(
                card_container(
                    ft.Text("No expenses logged yet. Tap Add Expense below.", size=13, color=TEXT_MUTED),
                    padding=18,
                )
            )
        else:
            for exp in expenses:
                payer_name = (exp.get("users") or {}).get("name") or "Member"
                remark_str = exp.get("remarks") or "General Expense"
                time_meta = "  •  ".join(
                    p for p in [exp.get("expense_date"), exp.get("expense_time")] if p
                )
                expenses_col.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(remark_str, size=15, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                                        ft.Text(f"Paid by {payer_name}", size=12, color=BRAND_GOLD),
                                        ft.Text(time_meta, size=11, color=TEXT_MUTED),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.Text(
                                    f"₹{float(exp['amount']):,.2f}",
                                    size=16,
                                    weight=ft.FontWeight.W_600,
                                    color=BRAND_WHITE,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        bgcolor=BG_CARD,
                        padding=15,
                        border_radius=14,
                        border=ft.Border.all(1, BORDER_SUBTLE),
                    )
                )

        page.update()

    async def _load_live_async(show_loader: bool = True):
        if show_loader:
            expenses_col.controls.clear()
            expenses_col.controls.append(
                ft.Row(
                    [ft.ProgressRing(width=20, height=20, stroke_width=2, color=BRAND_GOLD)],
                    alignment=ft.MainAxisAlignment.CENTER,
                )
            )
            page.update()
        try:
            data = await asyncio.to_thread(get_trip_full_data, trip["id"], user["id"])
            if sync_state["active"]:
                render_data(data, force=True)
        except DatabaseError as err:
            if sync_state["active"]:
                expenses_col.controls.clear()
                page.update()
                show_snack(str(err), is_error=True)
        except Exception:
            if sync_state["active"]:
                expenses_col.controls.clear()
                page.update()

    def load_live_data(show_loader: bool = True):
        page.run_task(_load_live_async, show_loader)

    async def live_sync_loop():
        while sync_state["active"]:
            await asyncio.sleep(4)
            if not sync_state["active"] or sync_state["dialog_open"]:
                continue
            try:
                data = await asyncio.to_thread(get_trip_full_data, trip["id"], user["id"])
                if sync_state["active"] and not sync_state["dialog_open"]:
                    render_data(data, force=False)
            except Exception:
                pass

    def open_add_expense_dialog(e):
        sync_state["dialog_open"] = True
        amount_input = styled_input(hint="Amount (e.g. 450)", keyboard_type=ft.KeyboardType.NUMBER, width=320)
        remarks_input = styled_input(hint="What was this for? (e.g. Dinner, Cab)", width=320)
        date_input = styled_input(hint="Date", value=current_date_str(), width=320)
        time_input = styled_input(hint="Time", value=current_time_str(), width=320)
        submitting = {"lock": False}

        def close_dlg(_=None):
            sync_state["dialog_open"] = False
            dlg.open = False
            page.pop_dialog()
            page.update()

        async def _add_task(amt: float, rem: str, dt_str: str, tm_str: str):
            try:
                await asyncio.to_thread(add_expense, trip["id"], user["id"], amt, rem, dt_str, tm_str)
                close_dlg()
                await _load_live_async(show_loader=False)
                show_snack("Expense added!")
            except DatabaseError as err:
                submitting["lock"] = False
                set_pill_loading(save_btn, False, default_text="Add Expense", fg="#000000")
                page.update()
                show_snack(str(err), is_error=True)

        def on_save(ev):
            if submitting["lock"]:
                return
            try:
                amt = float((amount_input.value or "").strip())
                if amt <= 0:
                    raise ValueError()
            except ValueError:
                show_snack("Enter a valid positive amount.", is_error=True)
                return

            rem = (remarks_input.value or "").strip()
            if not rem:
                show_snack("Please enter a short remark for the expense.", is_error=True)
                return

            submitting["lock"] = True
            set_pill_loading(save_btn, True, loading_text="Saving...", fg="#000000")
            page.update()
            page.run_task(_add_task, amt, rem, (date_input.value or "").strip(), (time_input.value or "").strip())

        save_btn = pill_button("Add Expense", on_click=on_save, bg=BRAND_WHITE, fg="#000000", width=200)

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=BG_CARD,
            shape=ft.RoundedRectangleBorder(radius=22),
            title=ft.Text("Add Expense", size=19, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
            content=ft.Container(
                width=340,
                content=ft.Column(
                    [amount_input, remarks_input, date_input, time_input],
                    tight=True,
                    spacing=11,
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
        ending = {"lock": False}

        def close_dlg(_=None):
            sync_state["dialog_open"] = False
            dlg.open = False
            page.pop_dialog()
            page.update()

        async def _end_task():
            try:
                ended = await asyncio.to_thread(end_trip, trip["id"], user["id"])
                sync_state["active"] = False
                sync_state["dialog_open"] = False
                dlg.open = False
                page.pop_dialog()
                page.update()
                on_trip_ended(ended)
            except DatabaseError as err:
                ending["lock"] = False
                set_pill_loading(confirm_btn, False, default_text="End & Settle", fg=BRAND_WHITE)
                page.update()
                show_snack(str(err), is_error=True)

        def on_confirm(ev):
            if ending["lock"]:
                return
            ending["lock"] = True
            set_pill_loading(confirm_btn, True, loading_text="Ending...", fg=BRAND_WHITE)
            page.update()
            page.run_task(_end_task)

        confirm_btn = pill_button("End & Settle", on_click=on_confirm, bg=BRAND_RED, fg=BRAND_WHITE)

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=BG_CARD,
            shape=ft.RoundedRectangleBorder(radius=20),
            title=ft.Text("End Trip?", size=19, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
            content=ft.Text(
                "Ending the trip locks new expenses for all members and calculates the final settlement.",
                size=13,
                color=TEXT_SECONDARY,
            ),
            actions=[
                ft.TextButton("Cancel", style=ft.ButtonStyle(color=TEXT_SECONDARY), on_click=close_dlg),
                confirm_btn,
            ],
        )
        page.show_dialog(dlg)

    code_chip = ft.Container(
        bgcolor=BG_INPUT,
        border_radius=12,
        border=ft.Border.all(1, BRAND_GOLD),
        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
        ink=True,
        on_click=lambda e: (copy_to_clipboard(page, trip["join_code"]), show_snack(f"Code {trip['join_code']} copied!")),
        content=ft.Row(
            [
                ft.Text(trip["join_code"], size=12, weight=ft.FontWeight.W_600, color=BRAND_GOLD),
                ft.Icon(ft.Icons.COPY_ROUNDED, size=14, color=BRAND_GOLD),
            ],
            spacing=5,
            tight=True,
        ),
    )

    top_bar = ft.Row(
        [
            ft.Row(
                [
                    ft.IconButton(ft.Icons.ARROW_BACK, icon_size=20, icon_color=TEXT_PRIMARY, on_click=lambda e: leave_view()),
                    ft.Column(
                        [
                            ft.Text(trip["trip_name"], size=18, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                            ft.Text("Live Sync Active", size=11, color=BRAND_GOLD),
                        ],
                        spacing=1,
                    ),
                ],
                spacing=4,
            ),
            ft.Row(
                [
                    code_chip,
                    ft.IconButton(
                        ft.Icons.REFRESH_ROUNDED,
                        icon_size=20,
                        icon_color=TEXT_SECONDARY,
                        tooltip="Refresh",
                        on_click=lambda e: load_live_data(show_loader=True),
                    ),
                ],
                spacing=2,
                tight=True,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    kpi_row = ft.Row(
        [
            ft.Container(
                content=ft.Column([section_label("Total Spent"), total_text], spacing=4),
                bgcolor=BG_CARD,
                padding=16,
                border_radius=16,
                border=ft.Border.all(1, BRAND_BLUE),
                expand=True,
            ),
            ft.Container(
                content=ft.Column([per_head_label, per_head_text], spacing=4),
                bgcolor=BG_CARD,
                padding=16,
                border_radius=16,
                border=ft.Border.all(1, BORDER_SUBTLE),
                expand=True,
            ),
        ],
        spacing=10,
    )

    action_buttons = [
        pill_button(
            "Add Expense",
            on_click=open_add_expense_dialog,
            icon=ft.Icons.ADD_ROUNDED,
            bg=BRAND_WHITE,
            fg="#000000",
            expand=True,
        )
    ]
    if is_host:
        action_buttons.append(
            pill_button(
                "End Trip",
                on_click=confirm_end_trip,
                icon=ft.Icons.FLAG_ROUNDED,
                bg=BRAND_RED,
                fg=BRAND_WHITE,
            )
        )

    load_live_data(show_loader=True)
    page.run_task(live_sync_loop)

    return ft.Container(
        expand=True,
        content=ft.Column(
            [
                top_bar,
                kpi_row,
                section_label("Members"),
                members_row,
                ft.Row(action_buttons, spacing=10),
                section_label("Recent Expenses"),
                expenses_col,
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=10,
        ),
    )
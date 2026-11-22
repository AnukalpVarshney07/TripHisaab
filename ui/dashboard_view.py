import asyncio
from datetime import datetime
import flet as ft
from core.database import (
    DatabaseError,
    create_trip,
    generate_unique_trip_code,
    get_user_trips,
    join_trip_by_code,
)
from core.utils import current_date_str, generate_trip_code
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
    brand_logo,
    copy_to_clipboard,
    pill_button,
    set_pill_loading,
    styled_input,
)


def _time_greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good Morning"
    elif hour < 17:
        return "Good Afternoon"
    return "Good Evening"


def build_dashboard_view(page: ft.Page, user: dict, on_open_trip, on_open_profile, on_logout, show_snack):
    trips_column = ft.Column(spacing=10)
    dash_sync = {"active": True, "last_sig": None, "dialog_open": False}

    def go_to_trip(trip_obj: dict):
        dash_sync["active"] = False
        on_open_trip(trip_obj)

    def go_to_profile(e=None):
        dash_sync["active"] = False
        on_open_profile()

    def handle_logout_click(e=None):
        dash_sync["dialog_open"] = True

        def close_logout_dlg(_=None):
            dash_sync["dialog_open"] = False
            dlg.open = False
            page.pop_dialog()
            page.update()

        def confirm_logout(_=None):
            dash_sync["active"] = False
            dash_sync["dialog_open"] = False
            dlg.open = False
            page.pop_dialog()
            page.update()
            on_logout()

        username_display = f" (@{user['username']})" if user.get("username") else ""

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=BG_CARD,
            shape=ft.RoundedRectangleBorder(radius=20),
            title=ft.Text("Sign Out?", size=19, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
            content=ft.Text(
                f"You are currently signed in as {user['name']}{username_display}. You will need to log in again to access your trips.",
                color=TEXT_SECONDARY,
                size=13,
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    style=ft.ButtonStyle(color=TEXT_SECONDARY),
                    on_click=close_logout_dlg,
                ),
                pill_button("Sign Out", on_click=confirm_logout, bg=BRAND_RED, fg=BRAND_WHITE),
            ],
        )
        page.show_dialog(dlg)

    def circle_back_btn(on_click):
        return ft.Container(
            width=38,
            height=38,
            border_radius=19,
            bgcolor=BG_INPUT,
            alignment=ft.Alignment(0, 0),
            ink=True,
            on_click=on_click,
            content=ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, color=TEXT_PRIMARY, size=20),
        )

    def render_trips(trips: list[dict], force: bool = False):
        sig = [(t["id"], t["status"], t["trip_name"], t.get("start_date")) for t in trips]
        if not force and sig == dash_sync["last_sig"]:
            return
        dash_sync["last_sig"] = sig

        trips_column.controls.clear()
        if not trips:
            trips_column.controls.append(
                ft.Container(
                    content=ft.Text(
                        "No trips yet. Tap CREATE NEW TRIP or JOIN TRIP above.",
                        color=TEXT_MUTED,
                        size=13,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    bgcolor=BG_CARD,
                    padding=24,
                    border_radius=16,
                    alignment=ft.Alignment(0, 0),
                )
            )
        else:
            for t in trips:
                is_active = t["status"] == "active"
                status_bg = BRAND_BLUE if is_active else BG_INPUT
                status_fg = BRAND_WHITE if is_active else TEXT_MUTED
                status_label = "ACTIVE" if is_active else "SETTLED"
                is_host = t["host_id"] == user["id"]

                meta_parts = [f"Code: {t['join_code']}", "Host" if is_host else "Member"]
                if t.get("start_date"):
                    meta_parts.append(t["start_date"])

                trip_card = ft.Container(
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(
                                                t["trip_name"],
                                                size=16,
                                                weight=ft.FontWeight.W_600,
                                                color=TEXT_PRIMARY,
                                            ),
                                            ft.Container(
                                                content=ft.Text(
                                                    status_label,
                                                    size=10,
                                                    weight=ft.FontWeight.W_600,
                                                    color=status_fg,
                                                ),
                                                bgcolor=status_bg,
                                                padding=ft.Padding.symmetric(horizontal=9, vertical=3),
                                                border_radius=20,
                                            ),
                                        ],
                                        spacing=8,
                                    ),
                                    ft.Text(
                                        "  •  ".join(meta_parts),
                                        size=12,
                                        color=BRAND_GOLD if is_active else TEXT_MUTED,
                                    ),
                                ],
                                spacing=5,
                                expand=True,
                            ),
                            ft.Container(
                                width=34,
                                height=34,
                                border_radius=17,
                                bgcolor=BRAND_RED if is_active else BG_INPUT,
                                alignment=ft.Alignment(0, 0),
                                content=ft.Icon(ft.Icons.CHEVRON_RIGHT, color=BRAND_WHITE, size=20),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    bgcolor=BG_CARD,
                    padding=18,
                    border_radius=18,
                    border=ft.Border.all(1, BORDER_SUBTLE),
                    ink=True,
                    on_click=lambda e, trip_obj=t: go_to_trip(trip_obj),
                )
                trips_column.controls.append(trip_card)

        page.update()

    def load_trips(show_loader: bool = True):
        if show_loader:
            trips_column.controls.clear()
            trips_column.controls.append(
                ft.Row(
                    [ft.ProgressRing(width=20, height=20, stroke_width=2, color=BRAND_GOLD)],
                    alignment=ft.MainAxisAlignment.CENTER,
                )
            )
            page.update()

        try:
            trips = get_user_trips(user["id"])
            render_trips(trips, force=True)
        except DatabaseError as err:
            trips_column.controls.clear()
            page.update()
            show_snack(str(err), is_error=True)

    async def dashboard_sync_loop():
        while dash_sync["active"]:
            await asyncio.sleep(5)
            if not dash_sync["active"] or dash_sync["dialog_open"]:
                continue
            try:
                trips = await asyncio.to_thread(get_user_trips, user["id"])
                if dash_sync["active"]:
                    render_trips(trips, force=False)
            except Exception:
                pass

    # ---------------- POP-UP 1: CREATING NEW TRIP ----------------
    def open_create_trip_popup(e):
        dash_sync["dialog_open"] = True
        try:
            auto_code = generate_unique_trip_code()
        except Exception:
            auto_code = generate_trip_code(6)

        name_input = styled_input(hint="NAME YOUR TRIP.....", width=320)
        date_input = styled_input(hint="DATE START.....", value=current_date_str(), width=320)
        budget_input = styled_input(
            hint="SET BUDGET (OPTIONAL).....",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=320,
        )

        code_box = ft.Container(
            width=320,
            bgcolor=BG_INPUT,
            border_radius=14,
            padding=ft.Padding.symmetric(horizontal=18, vertical=14),
            border=ft.Border.all(1, BRAND_GOLD),
            ink=True,
            on_click=lambda ev: (
                copy_to_clipboard(page, auto_code),
                show_snack(f"Trip Code {auto_code} copied!"),
            ),
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text("TRIP CODE (AUTO-GENERATED)", size=10, weight=ft.FontWeight.W_600, color=TEXT_MUTED),
                            ft.Text(auto_code, size=18, weight=ft.FontWeight.W_600, color=BRAND_GOLD),
                        ],
                        spacing=1,
                    ),
                    ft.Icon(ft.Icons.COPY_ROUNDED, color=BRAND_GOLD, size=18),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        )

        is_submitting = {"lock": False}

        def close_create_dlg(_=None):
            dash_sync["dialog_open"] = False
            dlg.open = False
            page.pop_dialog()
            page.update()

        async def _create_trip_task(t_name: str, start_date: str, parsed_budget: float | None):
            try:
                new_trip = await asyncio.to_thread(
                    create_trip,
                    trip_name=t_name,
                    host_id=user["id"],
                    join_code=auto_code,
                    start_date=start_date,
                    budget=parsed_budget,
                )
                close_create_dlg()
                show_snack(f"Trip Created • Code: {new_trip['join_code']}")
                go_to_trip(new_trip)
            except DatabaseError as err:
                is_submitting["lock"] = False
                set_pill_loading(done_btn, False, default_text="DONE")
                page.update()
                show_snack(str(err), is_error=True)

        def submit_new_trip(ev):
            if is_submitting["lock"]:
                return

            t_name = (name_input.value or "").strip()
            if len(t_name) < 2:
                show_snack("Please enter a name for your trip.", is_error=True)
                return

            raw_budget = (budget_input.value or "").strip()
            parsed_budget = None
            if raw_budget:
                try:
                    parsed_budget = float(raw_budget)
                    if parsed_budget <= 0:
                        raise ValueError()
                except ValueError:
                    show_snack("Budget must be a valid positive number.", is_error=True)
                    return

            is_submitting["lock"] = True
            set_pill_loading(done_btn, True, loading_text="Creating...")
            page.update()

            page.run_task(_create_trip_task, t_name, (date_input.value or "").strip(), parsed_budget)

        done_btn = pill_button("DONE", on_click=submit_new_trip, bg=BRAND_WHITE, fg="#000000", width=180)

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=BG_CARD,
            shape=ft.RoundedRectangleBorder(radius=24),
            content_padding=ft.Padding.all(22),
            content=ft.Container(
                width=350,
                content=ft.Column(
                    [
                        ft.Row(
                            [circle_back_btn(close_create_dlg)],
                            alignment=ft.MainAxisAlignment.START,
                        ),
                        brand_logo(size=120),
                        ft.Container(height=6),
                        ft.Text(
                            "Creating New Trip",
                            size=21,
                            weight=ft.FontWeight.W_600,
                            color=TEXT_PRIMARY,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(height=8),
                        name_input,
                        date_input,
                        budget_input,
                        code_box,
                        ft.Container(height=10),
                        done_btn,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                    spacing=12,
                ),
            ),
        )
        page.show_dialog(dlg)

    # ---------------- POP-UP 2: JOINING NEW TRIP ----------------
    def open_join_trip_popup(e):
        dash_sync["dialog_open"] = True
        code_input = styled_input(
            hint="ENTER TRIP CODE.....",
            max_length=6,
            capitalize=True,
            width=320,
        )

        is_joining = {"lock": False}

        def close_join_dlg(_=None):
            dash_sync["dialog_open"] = False
            dlg.open = False
            page.pop_dialog()
            page.update()

        async def _join_trip_task(code: str):
            try:
                joined_trip = await asyncio.to_thread(join_trip_by_code, code, user["id"])
                close_join_dlg()
                show_snack(f"Joined {joined_trip['trip_name']}!")
                go_to_trip(joined_trip)
            except DatabaseError as err:
                is_joining["lock"] = False
                set_pill_loading(join_btn, False, default_text="JOIN")
                page.update()
                show_snack(str(err), is_error=True)

        def submit_join_trip(ev):
            if is_joining["lock"]:
                return

            code = (code_input.value or "").strip().upper()
            if len(code) != 6:
                show_snack("Please enter the 6-character trip code.", is_error=True)
                return

            is_joining["lock"] = True
            set_pill_loading(join_btn, True, loading_text="Joining...")
            page.update()

            page.run_task(_join_trip_task, code)

        join_btn = pill_button("JOIN", on_click=submit_join_trip, bg=BRAND_WHITE, fg="#000000", width=180)

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=BG_CARD,
            shape=ft.RoundedRectangleBorder(radius=24),
            content_padding=ft.Padding.all(22),
            content=ft.Container(
                width=350,
                content=ft.Column(
                    [
                        ft.Row(
                            [circle_back_btn(close_join_dlg)],
                            alignment=ft.MainAxisAlignment.START,
                        ),
                        brand_logo(size=125),
                        ft.Container(height=8),
                        ft.Text(
                            "Joining New Trip",
                            size=21,
                            weight=ft.FontWeight.W_600,
                            color=TEXT_PRIMARY,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(height=14),
                        code_input,
                        ft.Container(height=16),
                        join_btn,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                    spacing=12,
                ),
            ),
        )
        page.show_dialog(dlg)

    # ---------------- MAIN DASHBOARD SCREEN ----------------
    def big_action_tile(label: str, icon, on_click):
        return ft.Container(
            height=88,
            border_radius=20,
            bgcolor=BRAND_WHITE,
            alignment=ft.Alignment(0, 0),
            ink=True,
            on_click=on_click,
            content=ft.Row(
                [
                    ft.Icon(icon, color="#000000", size=24),
                    ft.Text(
                        label,
                        size=20,
                        weight=ft.FontWeight.W_600,
                        color="#000000",
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                tight=True,
            ),
        )

    top_nav = ft.Row(
        [
            circle_back_btn(handle_logout_click),
            ft.Row(
                [
                    ft.IconButton(
                        ft.Icons.PERSON_OUTLINE_ROUNDED,
                        icon_size=22,
                        icon_color=BRAND_GOLD,
                        tooltip="Edit Profile",
                        on_click=go_to_profile,
                    ),
                    ft.IconButton(
                        ft.Icons.REFRESH_ROUNDED,
                        icon_size=21,
                        icon_color=TEXT_SECONDARY,
                        tooltip="Refresh Trips",
                        on_click=lambda e: load_trips(show_loader=True),
                    ),
                ],
                spacing=0,
                tight=True,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    greeting_text = ft.Text(
        f"{_time_greeting()}, {user['name']}",
        size=24,
        weight=ft.FontWeight.W_600,
        color=TEXT_PRIMARY,
    )

    load_trips(show_loader=True)
    page.run_task(dashboard_sync_loop)

    return ft.Container(
        expand=True,
        content=ft.Column(
            [
                top_nav,
                ft.Container(height=8),
                greeting_text,
                ft.Container(height=16),
                big_action_tile("CREATE NEW TRIP", icon=ft.Icons.ADD_ROUNDED, on_click=open_create_trip_popup),
                ft.Container(height=8),
                big_action_tile("JOIN TRIP", icon=ft.Icons.GROUPS_ROUNDED, on_click=open_join_trip_popup),
                ft.Container(height=20),
                ft.Text(
                    "Previous Trip",
                    size=18,
                    weight=ft.FontWeight.W_600,
                    color=TEXT_PRIMARY,
                ),
                ft.Container(height=4),
                trips_column,
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=6,
        ),
    )
import json
from pathlib import Path
import flet as ft
from core.utils import has_internet
from ui.auth_view import build_auth_view
from ui.dashboard_view import build_dashboard_view
from ui.live_trip_view import build_live_trip_view
from ui.profile_view import build_profile_view
from ui.summary_view import build_summary_view
from ui.theme import BG_APP, BRAND_GOLD, BRAND_RED, TEXT_PRIMARY, apply_theme
from ui.welcome_view import build_welcome_view

import os
from pathlib import Path


def _resolve_session_file() -> Path:
    for env_var in ("FLET_APP_STORAGE_DATA", "FLET_APP_STORAGE_TEMP"):
        val = os.getenv(env_var)
        if val:
            path = Path(val)
            path.mkdir(parents=True, exist_ok=True)
            return path / ".trip_hisaab_session.json"
    try:
        home = Path.home()
        home.mkdir(parents=True, exist_ok=True)
        return home / ".trip_hisaab_session.json"
    except Exception:
        return Path(".trip_hisaab_session.json")


SESSION_FILE = _resolve_session_file()
SAFE_USER_FIELDS = ("id", "name", "username", "email")


def _sanitize_session_user(user: dict) -> dict | None:
    if not isinstance(user, dict) or not user.get("id") or not user.get("name"):
        return None
    return {k: user[k] for k in SAFE_USER_FIELDS if k in user}


def load_saved_user() -> dict | None:
    try:
        if SESSION_FILE.exists():
            data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
            return _sanitize_session_user(data)
    except Exception:
        pass
    return None


def save_session(user: dict) -> None:
    safe = _sanitize_session_user(user)
    if not safe:
        return
    try:
        SESSION_FILE.write_text(json.dumps(safe), encoding="utf-8")
    except Exception:
        pass


def clear_session() -> None:
    try:
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()
    except Exception:
        pass


def main(page: ft.Page):
    apply_theme(page)
    page.title = "Trip Hisaab"
    page.window.width = 430
    page.window.height = 840
    page.window.min_width = 360
    page.window.min_height = 600

    saved_user = load_saved_user()
    state = {
        "user": saved_user,
        "active_trip": None,
        "view": "dashboard" if saved_user else "welcome",
    }

    def show_snack(message: str, is_error: bool = False):
        snack = ft.SnackBar(
            content=ft.Text(message, color=TEXT_PRIMARY, size=13),
            bgcolor=BRAND_RED if is_error else "#1C1C20",
            behavior=ft.SnackBarBehavior.FLOATING,
            shape=ft.RoundedRectangleBorder(radius=12),
            margin=ft.Margin.all(14),
        )
        page.show_dialog(snack)

    def handle_login_success(user: dict):
        safe_user = _sanitize_session_user(user) or user
        state["user"] = safe_user
        save_session(safe_user)
        set_view("dashboard")
        show_snack(f"Welcome, {safe_user['name']}!")

    def handle_profile_updated(updated_user: dict):
        safe_user = _sanitize_session_user(updated_user) or updated_user
        state["user"] = safe_user
        save_session(safe_user)

    def handle_logout():
        clear_session()
        state["user"] = None
        state["active_trip"] = None
        set_view("auth")
        show_snack("Signed out.")

    def open_trip(trip: dict):
        state["active_trip"] = trip
        if trip.get("status") == "ended":
            set_view("summary")
        else:
            set_view("live_trip")

    switcher = ft.AnimatedSwitcher(
        content=ft.Container(expand=True, bgcolor=BG_APP),
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=220,
        reverse_duration=160,
        switch_in_curve=ft.AnimationCurve.EASE_OUT,
        switch_out_curve=ft.AnimationCurve.EASE_IN,
    )

    root_wrapper = ft.Container(
        expand=True,
        bgcolor=BG_APP,
        padding=ft.Padding.only(left=20, right=20, top=22, bottom=14),
        content=switcher,
    )

    def set_view(view_name: str):
        state["view"] = view_name

        if not has_internet():
            offline_card = ft.Container(
                expand=True,
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, size=48, color=BRAND_GOLD),
                        ft.Container(height=12),
                        ft.Text("No Internet Connection", size=20, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                        ft.Text(
                            "Trip Hisaab syncs live expenses with cloud storage. Connect to the internet and try again.",
                            size=13,
                            color="#A1A1AA",
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(height=16),
                        ft.ElevatedButton(
                            "Retry",
                            bgcolor="#FFFFFF",
                            color="#000000",
                            on_click=lambda e: set_view(state["view"]),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                ),
            )
            switcher.content = offline_card
            page.update()
            return

        if view_name == "welcome":
            switcher.content = build_welcome_view(
                page=page,
                on_get_started=lambda: set_view("auth"),
            )
        elif view_name == "auth":
            switcher.content = build_auth_view(
                page=page,
                on_login_success=handle_login_success,
                show_snack=show_snack,
            )
        elif view_name == "dashboard":
            switcher.content = build_dashboard_view(
                page=page,
                user=state["user"],
                on_open_trip=open_trip,
                on_open_profile=lambda: set_view("profile"),
                on_logout=handle_logout,
                show_snack=show_snack,
            )
        elif view_name == "profile":
            switcher.content = build_profile_view(
                page=page,
                user=state["user"],
                on_back=lambda: set_view("dashboard"),
                on_profile_updated=handle_profile_updated,
                on_logout=handle_logout,
                show_snack=show_snack,
            )
        elif view_name == "live_trip":
            switcher.content = build_live_trip_view(
                page=page,
                user=state["user"],
                trip=state["active_trip"],
                on_back=lambda: set_view("dashboard"),
                on_trip_ended=lambda ended_trip: (
                    state.__setitem__("active_trip", ended_trip),
                    set_view("summary"),
                ),
                show_snack=show_snack,
            )
        elif view_name == "summary":
            switcher.content = build_summary_view(
                page=page,
                user=state["user"],
                trip=state["active_trip"],
                on_back=lambda: set_view("dashboard"),
                show_snack=show_snack,
            )

        page.update()

    page.add(root_wrapper)
    set_view(state["view"])


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
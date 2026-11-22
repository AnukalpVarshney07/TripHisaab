import asyncio
import re
import flet as ft
from core.database import DatabaseError, update_user_profile
from ui.theme import (
    BG_INPUT,
    BRAND_GOLD,
    BRAND_RED,
    BRAND_WHITE,
    TEXT_MUTED,
    TEXT_PRIMARY,
    card_container,
    pill_button,
    section_label,
    set_pill_loading,
    styled_input,
)


def build_profile_view(page: ft.Page, user: dict, on_back, on_profile_updated, on_logout, show_snack):
    saving = {"lock": False}

    name_input = styled_input(hint="Enter Full Name", label="Display Name", value=user.get("name", ""), width=320)
    username_input = styled_input(hint="Enter Username", label="Username", value=user.get("username", ""), width=320)
    email_input = styled_input(
        hint="Enter Email",
        label="Email (for OTP Recovery)",
        value=user.get("email", "") or "",
        keyboard_type=ft.KeyboardType.EMAIL,
        width=320,
    )

    initial_val = (user.get("name") or "U")[0].upper()
    avatar_text = ft.Text(initial_val, size=22, weight=ft.FontWeight.W_600, color="#000000")
    header_name = ft.Text(user.get("name", ""), size=18, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY)
    header_username = ft.Text(f"@{user.get('username', '')}", size=13, color=BRAND_GOLD)
    header_email = ft.Text(user.get("email") or "No email set", size=12, color=TEXT_MUTED)

    def _refresh_header(u: dict):
        avatar_text.value = ((u.get("name") or "U")[0]).upper()
        header_name.value = u.get("name", "")
        header_username.value = f"@{u.get('username', '')}"
        header_email.value = u.get("email") or "No email set"

    async def _save_task(new_name: str, new_username: str, new_email: str):
        try:
            updated = await asyncio.to_thread(
                update_user_profile,
                user["id"],
                new_name,
                new_username,
                new_email,
            )
            saving["lock"] = False
            set_pill_loading(save_btn, False, default_text="Save Changes", fg="#000000")
            _refresh_header(updated)
            on_profile_updated(updated)
            page.update()
            show_snack("Profile updated!")
        except DatabaseError as err:
            saving["lock"] = False
            set_pill_loading(save_btn, False, default_text="Save Changes", fg="#000000")
            page.update()
            show_snack(str(err), is_error=True)
        except Exception as ex:
            saving["lock"] = False
            set_pill_loading(save_btn, False, default_text="Save Changes", fg="#000000")
            page.update()
            show_snack(f"Update failed: {ex}", is_error=True)

    def handle_save(e):
        if saving["lock"]:
            return

        new_name = " ".join((name_input.value or "").strip().split())
        new_username = (username_input.value or "").strip().lower()
        new_email = (email_input.value or "").strip().lower()

        if len(new_name) < 2:
            show_snack("Name must be at least 2 characters.", is_error=True)
            return
        if not re.fullmatch(r"[a-z0-9_]{3,24}", new_username):
            show_snack("Username: 3-24 chars (letters, numbers, underscores).", is_error=True)
            return
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", new_email):
            show_snack("Please enter a valid email address.", is_error=True)
            return

        saving["lock"] = True
        set_pill_loading(save_btn, True, loading_text="Saving...", fg="#000000")
        page.update()
        page.run_task(_save_task, new_name, new_username, new_email)

    save_btn = pill_button(
        "Save Changes",
        on_click=handle_save,
        icon=ft.Icons.CHECK_ROUNDED,
        bg=BRAND_WHITE,
        fg="#000000",
        width=320,
    )

    logout_btn = pill_button(
        "Sign Out",
        on_click=lambda e: on_logout(),
        icon=ft.Icons.LOGOUT_ROUNDED,
        bg=BRAND_RED,
        fg=BRAND_WHITE,
        width=320,
    )

    header_card = card_container(
        ft.Row(
            [
                ft.Container(
                    width=54,
                    height=54,
                    border_radius=27,
                    bgcolor=BRAND_GOLD,
                    alignment=ft.Alignment(0, 0),
                    content=avatar_text,
                ),
                ft.Column(
                    [header_name, header_username, header_email],
                    spacing=2,
                    expand=True,
                ),
            ],
            spacing=14,
        ),
        padding=18,
    )

    top_bar = ft.Row(
        [
            ft.Container(
                width=38,
                height=38,
                border_radius=19,
                bgcolor=BG_INPUT,
                alignment=ft.Alignment(0, 0),
                ink=True,
                on_click=lambda e: on_back(),
                content=ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, color=TEXT_PRIMARY, size=20),
            ),
            ft.Text("My Profile", size=20, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
        ],
        spacing=10,
    )

    return ft.Container(
        expand=True,
        content=ft.Column(
            [
                top_bar,
                ft.Container(height=6),
                header_card,
                ft.Container(height=10),
                section_label("Edit Profile Details"),
                ft.Column(
                    [name_input, username_input, email_input],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
                ft.Container(height=12),
                ft.Container(content=save_btn, alignment=ft.Alignment(0, 0)),
                ft.Container(height=6),
                ft.Container(content=logout_btn, alignment=ft.Alignment(0, 0)),
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=8,
        ),
    )
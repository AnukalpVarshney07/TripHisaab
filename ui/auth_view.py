import asyncio
import flet as ft
from core.database import (
    DatabaseError,
    login_user,
    register_user,
    request_password_reset_otp,
    verify_otp_and_reset_password,
)
from ui.theme import (
    BG_CARD,
    BORDER_SUBTLE,
    BRAND_GOLD,
    BRAND_WHITE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    brand_logo,
    pill_button,
    set_pill_loading,
    styled_input,
)


def build_auth_view(page: ft.Page, on_login_success, show_snack):
    mode = {"is_login": False}
    busy = {"lock": False}

    name_input = styled_input(hint="Full Name", width=320)
    username_input = styled_input(hint="Username", width=320)
    email_input = styled_input(
        hint="Email Address",
        keyboard_type=ft.KeyboardType.EMAIL,
        width=320,
    )
    password_input = styled_input(
        hint="Password",
        password=True,
        width=320,
    )

    heading_text = ft.Text(
        "Sign Up",
        size=24,
        weight=ft.FontWeight.W_600,
        color=TEXT_PRIMARY,
        text_align=ft.TextAlign.CENTER,
    )

    switch_prefix = ft.Text("Already Have An Account ", size=13, color=TEXT_SECONDARY)
    switch_action = ft.Text(
        "Log In..",
        size=13,
        weight=ft.FontWeight.W_600,
        color=BRAND_WHITE,
    )

    forgot_btn = ft.Container(
        content=ft.Text(
            "Forgot Password?",
            size=12,
            weight=ft.FontWeight.W_500,
            color=BRAND_GOLD,
        ),
        ink=True,
        padding=ft.Padding.only(top=2, bottom=2),
        visible=False,
    )

    def open_forgot_password_dialog(e=None):
        fp_email = styled_input(
            hint="Registered Email Address",
            keyboard_type=ft.KeyboardType.EMAIL,
            width=300,
        )
        fp_otp = styled_input(
            hint="6-Digit OTP",
            max_length=6,
            keyboard_type=ft.KeyboardType.NUMBER,
            width=300,
        )
        fp_new_pass = styled_input(
            hint="New Password (min 6 chars)",
            password=True,
            width=300,
        )
        fp_busy = {"lock": False}

        def close_fp_dlg(_=None):
            dlg.open = False
            page.pop_dialog()
            page.update()

        async def _send_otp_task(mail: str):
            try:
                await asyncio.to_thread(request_password_reset_otp, mail)
                fp_busy["lock"] = False
                set_pill_loading(send_otp_btn, False, default_text="Send OTP", fg="#000000")
                page.update()
                show_snack("OTP sent to your email! Valid for 10 minutes.")
            except DatabaseError as err:
                fp_busy["lock"] = False
                set_pill_loading(send_otp_btn, False, default_text="Send OTP", fg="#000000")
                page.update()
                show_snack(str(err), is_error=True)
            except Exception as ex:
                fp_busy["lock"] = False
                set_pill_loading(send_otp_btn, False, default_text="Send OTP", fg="#000000")
                page.update()
                show_snack(f"Failed to send OTP: {ex}", is_error=True)

        async def _reset_pass_task(mail: str, otp_code: str, new_pwd: str):
            try:
                await asyncio.to_thread(verify_otp_and_reset_password, mail, otp_code, new_pwd)
                fp_busy["lock"] = False
                set_pill_loading(reset_btn, False, default_text="Reset Password", fg=BRAND_WHITE)
                close_fp_dlg()
                show_snack("Password updated! Please log in.")
            except DatabaseError as err:
                fp_busy["lock"] = False
                set_pill_loading(reset_btn, False, default_text="Reset Password", fg=BRAND_WHITE)
                page.update()
                show_snack(str(err), is_error=True)
            except Exception as ex:
                fp_busy["lock"] = False
                set_pill_loading(reset_btn, False, default_text="Reset Password", fg=BRAND_WHITE)
                page.update()
                show_snack(f"Reset failed: {ex}", is_error=True)

        def on_send_otp(ev):
            if fp_busy["lock"]:
                return
            mail = "".join((fp_email.value or "").split()).lower()
            if not mail:
                show_snack("Enter your registered email address.", is_error=True)
                return
            fp_busy["lock"] = True
            set_pill_loading(send_otp_btn, True, loading_text="Sending...", fg="#000000")
            page.update()
            page.run_task(_send_otp_task, mail)

        def on_reset_password(ev):
            if fp_busy["lock"]:
                return
            mail = "".join((fp_email.value or "").split()).lower()
            otp_code = (fp_otp.value or "").strip()
            new_pwd = fp_new_pass.value or ""
            if not mail:
                show_snack("Enter your registered email address.", is_error=True)
                return
            if len(otp_code) != 6:
                show_snack("Enter the 6-digit OTP.", is_error=True)
                return
            if len(new_pwd) < 6:
                show_snack("New password must be at least 6 characters.", is_error=True)
                return
            fp_busy["lock"] = True
            set_pill_loading(reset_btn, True, loading_text="Updating...", fg=BRAND_WHITE)
            page.update()
            page.run_task(_reset_pass_task, mail, otp_code, new_pwd)

        send_otp_btn = pill_button("Send OTP", on_click=on_send_otp, bg=BRAND_GOLD, fg="#000000", width=300)
        reset_btn = pill_button("Reset Password", on_click=on_reset_password, bg="#0A4DA2", fg=BRAND_WHITE, width=300)

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=BG_CARD,
            shape=ft.RoundedRectangleBorder(radius=22),
            title=ft.Text("Reset Password", size=19, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
            content=ft.Container(
                width=320,
                content=ft.Column(
                    [
                        ft.Text(
                            "Request a 6-digit OTP on your email, then set a new password.",
                            size=12,
                            color=TEXT_SECONDARY,
                        ),
                        fp_email,
                        send_otp_btn,
                        ft.Divider(color=BORDER_SUBTLE, height=8),
                        fp_otp,
                        fp_new_pass,
                        reset_btn,
                    ],
                    tight=True,
                    spacing=10,
                ),
            ),
            actions=[
                ft.TextButton("Close", style=ft.ButtonStyle(color=TEXT_SECONDARY), on_click=close_fp_dlg),
            ],
        )
        page.show_dialog(dlg)

    forgot_btn.on_click = open_forgot_password_dialog

    async def _submit_auth_task(is_login: bool, full_name: str, uname: str, mail: str, pwd: str):
        try:
            if is_login:
                user_obj = await asyncio.to_thread(login_user, uname, pwd)
            else:
                user_obj = await asyncio.to_thread(register_user, full_name, uname, pwd, mail)

            busy["lock"] = False
            default_lbl = "Log In" if is_login else "Continue"
            set_pill_loading(submit_btn, False, default_text=default_lbl, fg="#000000")
            page.update()
            on_login_success(user_obj)
        except DatabaseError as err:
            busy["lock"] = False
            default_lbl = "Log In" if is_login else "Continue"
            set_pill_loading(submit_btn, False, default_text=default_lbl, fg="#000000")
            page.update()
            show_snack(str(err), is_error=True)
        except Exception as ex:
            busy["lock"] = False
            default_lbl = "Log In" if is_login else "Continue"
            set_pill_loading(submit_btn, False, default_text=default_lbl, fg="#000000")
            page.update()
            show_snack(f"Authentication error: {ex}", is_error=True)

    def handle_submit(e):
        if busy["lock"]:
            return

        is_login = mode["is_login"]
        full_name = " ".join((name_input.value or "").strip().split())
        uname = (username_input.value or "").strip().lower()
        mail = "".join((email_input.value or "").split()).lower()
        pwd = password_input.value or ""

        if not is_login and len(full_name) < 2:
            show_snack("Please enter your full name.", is_error=True)
            return
        if len(uname) < 3:
            show_snack("Username must be at least 3 characters.", is_error=True)
            return
        if not is_login and ("@" not in mail or "." not in mail.split("@")[-1]):
            show_snack("Please enter a valid email address.", is_error=True)
            return
        if len(pwd) < 6:
            show_snack("Password must be at least 6 characters.", is_error=True)
            return

        busy["lock"] = True
        loading_lbl = "Signing In..." if is_login else "Creating Account..."
        set_pill_loading(submit_btn, True, loading_text=loading_lbl, fg="#000000")
        page.update()
        page.run_task(_submit_auth_task, is_login, full_name, uname, mail, pwd)

    submit_btn = pill_button(
        "Continue",
        on_click=handle_submit,
        bg=BRAND_WHITE,
        fg="#000000",
        width=220,
    )

    def toggle_mode(e=None):
        if busy["lock"]:
            return
        mode["is_login"] = not mode["is_login"]
        is_login = mode["is_login"]

        name_input.visible = not is_login
        email_input.visible = not is_login
        forgot_btn.visible = is_login

        if is_login:
            heading_text.value = "Log In"
            submit_btn.content = ft.Text("Log In", size=16, weight=ft.FontWeight.W_600, color="#000000")
            switch_prefix.value = "Don't Have An Account? "
            switch_action.value = "Sign Up"
        else:
            heading_text.value = "Sign Up"
            submit_btn.content = ft.Text("Continue", size=16, weight=ft.FontWeight.W_600, color="#000000")
            switch_prefix.value = "Already Have An Account "
            switch_action.value = "Log In.."

        page.update()

    switch_row = ft.Container(
        content=ft.Row(
            [switch_prefix, switch_action],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=2,
            tight=True,
        ),
        ink=True,
        padding=ft.Padding.symmetric(vertical=6, horizontal=10),
        on_click=toggle_mode,
    )

    return ft.Container(
        expand=True,
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            [
                brand_logo(size=140),
                ft.Container(height=6),
                heading_text,
                ft.Container(height=8),
                name_input,
                username_input,
                email_input,
                password_input,
                ft.Container(
                    width=320,
                    alignment=ft.Alignment(1, 0),
                    content=forgot_btn,
                ),
                ft.Container(height=6),
                submit_btn,
                ft.Container(height=4),
                switch_row,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
            spacing=11,
        ),
    )
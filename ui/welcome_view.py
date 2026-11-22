import flet as ft
from ui.theme import (
    BG_APP,
    BRAND_RED,
    BRAND_WHITE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    brand_logo,
)


def _credit_block(role_label: str, person_name: str) -> ft.Column:
    return ft.Column(
        [
            ft.Text(
                role_label,
                size=16,
                weight=ft.FontWeight.W_400,
                color=TEXT_SECONDARY,
            ),
            ft.Text(
                person_name,
                size=28,
                weight=ft.FontWeight.W_500,
                color=TEXT_PRIMARY,
            ),
        ],
        spacing=2,
        tight=True,
    )


def build_welcome_view(page: ft.Page, on_get_started):
    next_button = ft.Container(
        width=74,
        height=74,
        border_radius=37,
        bgcolor=BRAND_RED,
        alignment=ft.Alignment(0, 0),
        ink=True,
        on_click=lambda e: on_get_started(),
        content=ft.Icon(
            ft.Icons.CHEVRON_RIGHT_ROUNDED,
            color=BRAND_WHITE,
            size=38,
        ),
    )

    credits_column = ft.Container(
        width=310,
        content=ft.Column(
            [
                _credit_block("Developed By:", "Anukalp Varshney"),
                ft.Container(height=24),
                _credit_block("Designed By:", "Satwik Gupta"),
                ft.Container(height=24),
                _credit_block("Vision By:", "Kailash Gupta"),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.START,
            tight=True,
        ),
    )

    return ft.Container(
        expand=True,
        bgcolor=BG_APP,
        content=ft.Stack(
            [
                ft.Column(
                    [
                        ft.Container(height=36),
                        brand_logo(size=175),
                        ft.Container(height=42),
                        credits_column,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    scroll=ft.ScrollMode.AUTO,
                ),
                ft.Container(
                    alignment=ft.Alignment(1, 1),
                    padding=ft.Padding.only(right=10, bottom=14),
                    content=next_button,
                ),
            ],
            expand=True,
        ),
    )
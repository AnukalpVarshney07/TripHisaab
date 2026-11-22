from pathlib import Path
import flet as ft

# Brand Palette from UI.pdf

BG_APP = "#000000"
BG_CARD = "#161618"
BG_INPUT = "#1C1C20"
BORDER_SUBTLE = "#26262B"
BRAND_BLUE = "#0A4DA2"
BRAND_GOLD = "#F5D042"
BRAND_RED = "#C61A1A"
BRAND_WHITE = "#FFFFFF"
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#A1A1AA"
TEXT_MUTED = "#71717A"


def apply_theme(page: ft.Page) -> None:
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG_APP
    page.theme = ft.Theme(
        color_scheme_seed=BRAND_GOLD,
        use_material3=True,
    )

BG_PRIMARY = "#000000"       # Pure pitch-black background
BG_CARD = "#161618"          # Dark charcoal card
BG_INPUT = "#262629"         # Rounded pill input fill
BORDER_SUBTLE = "#2E2E32"    # Hairline dark border

BRAND_BLUE = "#0A4DA2"       # Royal Cobalt Blue ("Trip")
BRAND_GOLD = "#F5D042"       # Warm Gold ("HISAAB" & triangle)
BRAND_RED = "#C61A1A"        # Crimson Red circular CTA & alerts
BRAND_WHITE = "#FFFFFF"      # Crisp White primary button & headings

TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#D4D4D8"
TEXT_MUTED = "#8E8E93"


def brand_logo(size: int = 160) -> ft.Control:
    """Renders your exact official logo from assets/logo.png."""
    if Path("assets/logo.png").exists():
        return ft.Image(
            src="logo.png",
            width=size,
            height=size,
            fit=ft.BoxFit.CONTAIN,
        )
    return ft.Container(
        width=size,
        height=size,
        border_radius=size // 2,
        bgcolor=BG_INPUT,
        alignment=ft.Alignment(0, 0),
        content=ft.Text("Place logo.png\nin assets/", size=12, color=TEXT_MUTED, text_align=ft.TextAlign.CENTER),
    )


def pill_button(
    text: str,
    on_click,
    icon=None,
    bg: str = BRAND_WHITE,
    fg: str = "#000000",
    border_color: str | None = None,
    width: int | None = None,
    expand: bool = False,
):
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icon, color=fg, size=17) if icon else ft.Container(width=0),
                ft.Text(text, weight=ft.FontWeight.W_500, size=15, color=fg),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
            spacing=8,
        ),
        bgcolor=bg,
        height=50,
        width=width,
        expand=expand,
        border_radius=25,
        border=ft.Border.all(1, border_color) if border_color else None,
        padding=ft.Padding.symmetric(horizontal=24, vertical=12),
        alignment=ft.Alignment(0, 0),
        ink=True,
        on_click=on_click,
    )

def apply_theme(page: ft.Page) -> None:
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG_APP
    page.theme = ft.Theme(
        color_scheme_seed=BRAND_GOLD,
        use_material3=True,
    )

def set_pill_loading(btn: ft.Container, is_loading: bool, loading_text: str = "Processing...", default_text: str = "Continue", fg: str = "#000000", icon=None):
    if is_loading:
        btn.disabled = True
        btn.opacity = 0.85
        btn.content = ft.Row(
            [
                ft.ProgressRing(width=16, height=16, stroke_width=2.2, color=fg),
                ft.Text(loading_text, weight=ft.FontWeight.W_600, size=14, color=fg),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
            spacing=10,
        )
    else:
        btn.disabled = False
        btn.opacity = 1.0
        btn.content = ft.Row(
            [
                ft.Icon(icon, color=fg, size=17) if icon else ft.Container(width=0),
                ft.Text(default_text, weight=ft.FontWeight.W_600, size=15, color=fg),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
            spacing=8,
        )


def red_circle_next_button(on_click, size: int = 66):
    return ft.Container(
        width=size,
        height=size,
        border_radius=size // 2,
        bgcolor=BRAND_RED,
        alignment=ft.Alignment(0, 0),
        ink=True,
        on_click=on_click,
        content=ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color="#FFFFFF", size=38),
    )


def styled_input(
    hint: str = "",
    label: str | None = None,
    value: str = "",
    keyboard_type: ft.KeyboardType = ft.KeyboardType.TEXT,
    max_length: int | None = None,
    capitalize: bool = False,
    password: bool = False,
    width: int | None = None,
) -> ft.TextField:
    return ft.TextField(
        label=label,
        hint_text=hint,
        value=value,
        width=width,
        password=password,
        can_reveal_password=password,
        keyboard_type=keyboard_type,
        max_length=max_length,
        capitalization=ft.TextCapitalization.CHARACTERS if capitalize else ft.TextCapitalization.NONE,
        bgcolor=BG_INPUT,
        color=TEXT_PRIMARY,
        hint_style=ft.TextStyle(color=TEXT_MUTED, size=14),
        label_style=ft.TextStyle(color=TEXT_SECONDARY, size=13),
        border_radius=14,
        border_width=1,
        border_color=BORDER_SUBTLE,
        focused_border_color=BRAND_WHITE,
        content_padding=ft.Padding.symmetric(horizontal=18, vertical=16),
    )


def card_container(content: ft.Control, padding: int = 20, border_color: str = BORDER_SUBTLE, col=None):
    return ft.Container(
        content=content,
        bgcolor=BG_CARD,
        padding=padding,
        border_radius=16,
        border=ft.Border.all(1, border_color),
        col=col,
    )


def section_label(text: str):
    return ft.Text(
        text.upper(),
        size=11,
        weight=ft.FontWeight.W_500,
        color=BRAND_GOLD,
    )

def copy_to_clipboard(page: ft.Page, text: str):
    async def _copy():
        try:
            await ft.Clipboard().set(text)
        except Exception:
            pass
    page.run_task(_copy)
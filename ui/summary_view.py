import asyncio
import flet as ft
from core.database import DatabaseError, delete_trip, get_trip_full_data
from core.hisaab_engine import calculate_hisaab, format_whatsapp_summary
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
)


def build_summary_view(page: ft.Page, user: dict, trip: dict, on_back, show_snack):
    is_host = trip["host_id"] == user["id"]
    content_col = ft.Column(spacing=12)

    def confirm_delete_trip(e):
        is_deleting = {"lock": False}

        def close_delete_dlg(_=None):
            dlg.open = False
            page.pop_dialog()
            page.update()

        async def _delete_task():
            try:
                await asyncio.to_thread(delete_trip, trip["id"], user["id"])
                close_delete_dlg()
                show_snack(f"Deleted '{trip['trip_name']}'.")
                on_back()
            except DatabaseError as err:
                is_deleting["lock"] = False
                set_pill_loading(confirm_btn, False, default_text="Delete Permanently", fg=BRAND_WHITE, icon=ft.Icons.DELETE_FOREVER_ROUNDED)
                page.update()
                show_snack(str(err), is_error=True)

        def execute_delete(ev):
            if is_deleting["lock"]:
                return
            is_deleting["lock"] = True
            set_pill_loading(confirm_btn, True, loading_text="Deleting...", fg=BRAND_WHITE)
            page.update()
            page.run_task(_delete_task)

        confirm_btn = pill_button(
            "Delete Permanently",
            on_click=execute_delete,
            bg=BRAND_RED,
            fg=BRAND_WHITE,
            icon=ft.Icons.DELETE_FOREVER_ROUNDED,
        )

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=BG_CARD,
            shape=ft.RoundedRectangleBorder(radius=20),
            title=ft.Text("Delete Trip?", size=19, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
            content=ft.Text(
                f"This will permanently delete '{trip['trip_name']}' along with all logged expenses and settlement records for all members. This cannot be undone.",
                color=TEXT_SECONDARY,
                size=13,
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    style=ft.ButtonStyle(color=TEXT_SECONDARY),
                    on_click=close_delete_dlg,
                ),
                confirm_btn,
            ],
        )
        page.show_dialog(dlg)

    def load_summary():
        content_col.controls.clear()
        content_col.controls.append(
            ft.Row(
                [ft.ProgressRing(width=22, height=22, stroke_width=2.5, color=BRAND_GOLD)],
                alignment=ft.MainAxisAlignment.CENTER,
            )
        )
        page.update()

        try:
            data = get_trip_full_data(trip["id"])
            hisaab = calculate_hisaab(data["members"], data["expenses"])
            share_text = format_whatsapp_summary(trip["trip_name"], trip["join_code"], hisaab)

            content_col.controls.clear()

            # 1. Total & Per-Head KPI Row
            kpi_row = ft.Row(
                [
                    ft.Container(
                        content=ft.Column(
                            [
                                section_label("Total Expenditure"),
                                ft.Text(f"₹{hisaab['total_expenditure']:,.2f}", size=24, weight=ft.FontWeight.W_600, color=BRAND_WHITE),
                            ],
                            spacing=4,
                        ),
                        bgcolor=BG_CARD,
                        padding=18,
                        border_radius=16,
                        border=ft.Border.all(1, BRAND_BLUE),
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Column(
                            [
                                section_label(f"Per Head ({hisaab['member_count']})"),
                                ft.Text(f"₹{hisaab['per_head']:,.2f}", size=24, weight=ft.FontWeight.W_600, color=BRAND_GOLD),
                            ],
                            spacing=4,
                        ),
                        bgcolor=BG_CARD,
                        padding=18,
                        border_radius=16,
                        border=ft.Border.all(1, BORDER_SUBTLE),
                        expand=True,
                    ),
                ],
                spacing=10,
            )
            content_col.controls.append(kpi_row)

            # 2. Individual Member Balances
            content_col.controls.append(ft.Container(height=4))
            content_col.controls.append(section_label("Member Balances"))

            for m in hisaab["member_stats"]:
                if m["status"] == "gets_back":
                    badge_text = f"Gets back ₹{m['balance']:,.2f}"
                    badge_color = BRAND_GOLD
                elif m["status"] == "owes":
                    badge_text = f"Owes ₹{abs(m['balance']):,.2f}"
                    badge_color = BRAND_RED
                else:
                    badge_text = "Settled"
                    badge_color = TEXT_MUTED

                content_col.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(m["name"], size=15, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                                        ft.Text(f"Spent ₹{m['paid']:,.2f}", size=12, color=TEXT_MUTED),
                                    ],
                                    spacing=2,
                                ),
                                ft.Text(badge_text, size=14, weight=ft.FontWeight.W_600, color=badge_color),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        bgcolor=BG_CARD,
                        padding=ft.Padding.symmetric(horizontal=16, vertical=13),
                        border_radius=14,
                        border=ft.Border.all(1, BORDER_SUBTLE),
                    )
                )

            # 3. Simplified "Who Pays Whom" Transfers
            content_col.controls.append(ft.Container(height=4))
            content_col.controls.append(section_label("Settlement Transfers"))

            if not hisaab["settlements"]:
                content_col.controls.append(
                    card_container(
                        ft.Text("Everyone spent equally — no transfers required!", size=13, color=TEXT_SECONDARY),
                        padding=18,
                    )
                )
            else:
                for tx in hisaab["settlements"]:
                    content_col.controls.append(
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(tx["from_name"], size=14, weight=ft.FontWeight.W_600, color=BRAND_RED),
                                            ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=16, color=TEXT_MUTED),
                                            ft.Text(tx["to_name"], size=14, weight=ft.FontWeight.W_600, color=BRAND_GOLD),
                                        ],
                                        spacing=8,
                                    ),
                                    ft.Text(f"₹{tx['amount']:,.2f}", size=15, weight=ft.FontWeight.W_600, color=BRAND_WHITE),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            bgcolor=BG_INPUT,
                            padding=ft.Padding.symmetric(horizontal=16, vertical=13),
                            border_radius=14,
                            border=ft.Border.all(1, BORDER_SUBTLE),
                        )
                    )

            # 4. Action Buttons (Copy Summary + Host Delete Trip)
            content_col.controls.append(ft.Container(height=8))
            content_col.controls.append(
                ft.Row(
                    [
                        pill_button(
                            "Copy Hisaab Summary",
                            on_click=lambda e: (copy_to_clipboard(page, share_text), show_snack("Summary copied to clipboard!")),
                            icon=ft.Icons.COPY_ALL_ROUNDED,
                            bg=BRAND_WHITE,
                            fg="#000000",
                            expand=True,
                        )
                    ]
                )
            )

            if is_host:
                content_col.controls.append(
                    ft.Row(
                        [
                            pill_button(
                                "Delete Trip",
                                on_click=confirm_delete_trip,
                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                bg=BRAND_RED,
                                fg=BRAND_WHITE,
                                expand=True,
                            )
                        ]
                    )
                )

        except DatabaseError as err:
            content_col.controls.clear()
            show_snack(str(err), is_error=True)

        page.update()

    top_bar = ft.Row(
        [
            ft.Row(
                [
                    ft.IconButton(ft.Icons.ARROW_BACK, icon_size=20, icon_color=TEXT_PRIMARY, on_click=lambda e: on_back()),
                    ft.Column(
                        [
                            ft.Text("Final Hisaab", size=19, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                            ft.Text(f"{trip['trip_name']}  •  Settled", size=12, color=TEXT_MUTED),
                        ],
                        spacing=1,
                    ),
                ],
                spacing=4,
            ),
            ft.IconButton(
                ft.Icons.DELETE_OUTLINE_ROUNDED,
                icon_size=21,
                icon_color=BRAND_RED,
                tooltip="Delete Trip",
                visible=is_host,
                on_click=confirm_delete_trip,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    load_summary()

    return ft.Container(
        content=ft.Column(
            [
                top_bar,
                content_col,
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=12,
        ),
        expand=True,
    )
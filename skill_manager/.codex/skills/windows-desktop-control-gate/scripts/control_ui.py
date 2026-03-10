import argparse
import ctypes
import json
import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QSize, QPoint
from PySide6.QtGui import QColor, QCursor, QFont, QFontDatabase, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QProgressBar,
    QSizePolicy,
)


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def get_target_screen():
    cursor_screen = QGuiApplication.screenAt(QCursor.pos())
    if cursor_screen is not None:
        return cursor_screen

    user32 = getattr(ctypes, "windll", None)
    if user32 is not None:
        hwnd = user32.user32.GetForegroundWindow()
        if hwnd:
            rect = RECT()
            if user32.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                center = QPoint((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
                screen = QGuiApplication.screenAt(center)
                if screen is not None:
                    return screen

    return QGuiApplication.primaryScreen()


def move_to_screen_anchor(widget: QWidget, screen, *, top_offset: int, right_offset: int = 20) -> None:
    if screen is None:
        return
    available = screen.availableGeometry()
    widget.move(QPoint(available.right() - widget.width() - right_offset, available.top() + top_offset))


def center_on_screen(widget: QWidget, screen) -> None:
    if screen is None:
        return
    available = screen.availableGeometry()
    target_x = available.left() + (available.width() - widget.width()) // 2
    target_y = available.top() + (available.height() - widget.height()) // 2
    widget.move(QPoint(target_x, target_y))


def serialize_screen(screen) -> dict | None:
    if screen is None:
        return None
    geometry = screen.availableGeometry()
    return {
        "name": screen.name(),
        "left": geometry.left(),
        "top": geometry.top(),
        "width": geometry.width(),
        "height": geometry.height(),
    }


def find_screen_from_payload(payload: dict | None):
    if not payload:
        return None

    screen_name = payload.get("name")
    left = payload.get("left")
    top = payload.get("top")
    width = payload.get("width")
    height = payload.get("height")

    for screen in QGuiApplication.screens():
        geometry = screen.availableGeometry()
        if (
            screen_name
            and screen.name() == screen_name
            and geometry.left() == left
            and geometry.top() == top
        ):
            return screen
        if (
            geometry.left() == left
            and geometry.top() == top
            and geometry.width() == width
            and geometry.height() == height
        ):
            return screen
    return None


def apply_constrained_size(
    widget: QWidget,
    *,
    preferred_width: int,
    min_width: int,
    max_width: int,
    min_height: int,
    max_height: int,
) -> None:
    widget.setMinimumWidth(min_width)
    widget.setMaximumWidth(max_width)
    widget.resize(preferred_width, min_height)
    widget.adjustSize()
    width = max(min_width, min(widget.sizeHint().width(), max_width))
    height = max(min_height, min(widget.sizeHint().height() + 8, max_height))
    widget.resize(width, height)


def configure_app() -> QApplication:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "RoundPreferFloor")
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.RoundPreferFloor
    )
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(pick_font(10))
    return app


def pick_font(size: int, weight: int = QFont.Weight.Normal, display: bool = False) -> QFont:
    preferred_families = [
        "Segoe UI Variable Display" if display else "Segoe UI Variable Text",
        "Segoe UI",
        "PingFang SC",
        "HarmonyOS Sans SC",
        "MiSans",
        "OPPOSans",
        "Noto Sans SC",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Microsoft YaHei UI",
        "Microsoft YaHei",
    ]
    available = {family.casefold(): family for family in QFontDatabase.families()}
    primary_family = None
    for family in preferred_families:
        resolved = available.get(family.casefold())
        if resolved:
            primary_family = resolved
            break

    families = [primary_family] if primary_family else ["Segoe UI"]
    for fallback in ("Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans SC"):
        resolved = available.get(fallback.casefold())
        if resolved and resolved not in families:
            families.append(resolved)

    font = QFont()
    font.setFamilies(families)
    font.setPointSizeF(size)
    font.setWeight(weight)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    font.setKerning(True)
    font.setLetterSpacing(
        QFont.SpacingType.PercentageSpacing,
        99 if display else 100,
    )
    return font


def add_shadow(widget: QWidget, blur: int = 28, y_offset: int = 10) -> None:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, y_offset)
    shadow.setColor(QColor(15, 23, 42, 20))
    widget.setGraphicsEffect(shadow)


class ApprovalDialog(QDialog):
    def __init__(self, operation_name: str, details: str, timeout_seconds: int) -> None:
        super().__init__()
        self.operation_name = operation_name
        self.details = details.strip() or "本次没有额外说明。"
        self.timeout_seconds = max(timeout_seconds, 1)
        self.remaining = self.timeout_seconds
        self.decision = "cancelled"
        self.auto_approved = False
        self.target_screen = get_target_screen()

        self.setObjectName("approvalDialog")
        self.setWindowTitle("Agent正在操作")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        card = QFrame()
        card.setObjectName("card")
        add_shadow(card)
        root.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(0)

        badges = QHBoxLayout()
        badges.setSpacing(8)
        badges.addWidget(self.make_badge("输入控制", "primary"))
        badges.addWidget(self.make_badge(f"{self.timeout_seconds} s", "warning"))
        badges.addStretch(1)
        layout.addLayout(badges)

        title = QLabel("Agent正在操作")
        title.setFont(pick_font(15, QFont.Weight.DemiBold, display=True))
        title.setObjectName("title")
        title.setWordWrap(True)
        title.setContentsMargins(0, 12, 0, 0)
        layout.addWidget(title)

        summary = QLabel(f"会激活目标窗口并发送系统输入。未处理时 {self.timeout_seconds} s 后自动继续。")
        summary.setWordWrap(True)
        summary.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        summary.setFont(pick_font(9))
        summary.setObjectName("summary")
        summary.setContentsMargins(0, 6, 0, 0)
        layout.addWidget(summary)

        content_panel = QFrame()
        content_panel.setObjectName("contentPanel")
        panel_layout = QVBoxLayout(content_panel)
        panel_layout.setContentsMargins(18, 16, 18, 16)
        panel_layout.setSpacing(10)

        operation_card = self.make_info_row("操作", operation_name, emphasize=True)
        panel_layout.addWidget(operation_card)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)
        panel_layout.addWidget(divider)

        details_card = self.make_info_row("说明", self.details, emphasize=False)
        panel_layout.addWidget(details_card)

        content_panel.setContentsMargins(0, 14, 0, 0)
        layout.addWidget(content_panel)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 14, 0, 0)
        bottom.setSpacing(12)

        progress_box = QVBoxLayout()
        progress_box.setSpacing(4)
        self.progress = QProgressBar()
        self.progress.setRange(0, self.timeout_seconds * 1000)
        self.progress.setValue(self.timeout_seconds * 1000)
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(252)
        self.progress.setFixedHeight(5)
        progress_box.addWidget(self.progress)

        self.countdown = QLabel()
        self.countdown.setFont(pick_font(10))
        self.countdown.setObjectName("countdown")
        progress_box.addWidget(self.countdown)

        hint = QLabel("不希望执行时，直接点取消。")
        hint.setFont(pick_font(9))
        hint.setObjectName("hint")
        progress_box.addWidget(hint)

        bottom.addLayout(progress_box, 1)

        cancel_button = QPushButton("取消")
        cancel_button.setObjectName("secondaryButton")
        cancel_button.setFont(pick_font(9, QFont.Weight.DemiBold))
        cancel_button.setFixedSize(QSize(92, 40))
        cancel_button.clicked.connect(self.handle_cancel)
        bottom.addWidget(cancel_button)

        continue_button = QPushButton("继续")
        continue_button.setObjectName("primaryButton")
        continue_button.setFont(pick_font(9, QFont.Weight.DemiBold))
        continue_button.setFixedSize(QSize(118, 40))
        continue_button.clicked.connect(self.handle_continue)
        continue_button.setDefault(True)
        bottom.addWidget(continue_button)

        layout.addLayout(bottom)
        self.apply_styles()
        apply_constrained_size(
            self,
            preferred_width=700,
            min_width=660,
            max_width=780,
            min_height=300,
            max_height=500,
        )
        center_on_screen(self, self.target_screen)

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.tick)
        self.tick()
        self.timer.start()

    def make_badge(self, text: str, tone: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName(f"badge-{tone}")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 4, 10, 4)
        label = QLabel(text)
        label.setFont(pick_font(9, QFont.Weight.DemiBold))
        label.setObjectName(f"badgeText-{tone}")
        layout.addWidget(label)
        return frame

    def make_info_row(self, title_text: str, body_text: str, emphasize: bool) -> QFrame:
        frame = QFrame()
        frame.setObjectName("infoRow")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel(title_text)
        title.setObjectName("infoTitle")
        title.setFont(pick_font(9, QFont.Weight.Medium))
        layout.addWidget(title)

        body = QLabel(body_text)
        body.setWordWrap(True)
        body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        body.setObjectName("infoBodyStrong" if emphasize else "infoBody")
        body.setFont(
            pick_font(
                11 if emphasize else 9,
                QFont.Weight.DemiBold if emphasize else QFont.Weight.Normal,
            )
        )
        layout.addWidget(body)
        return frame

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QDialog#approvalDialog { background: transparent; }
            QFrame#card {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #FBFCFE);
                border: 1px solid #E7EAF0;
                border-radius: 20px;
            }
            QFrame#badge-primary {
                background: #EBF2FF;
                border: 1px solid #DBE7FF;
                border-radius: 12px;
            }
            QLabel#badgeText-primary {
                color: #3370FF;
            }
            QFrame#badge-warning {
                background: #FFF4E8;
                border: 1px solid #FFE0C2;
                border-radius: 12px;
            }
            QLabel#badgeText-warning {
                color: #D46B08;
            }
            QLabel#title { color: #1F2329; }
            QLabel#summary { color: #646A73; }
            QFrame#contentPanel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FBFCFE, stop:1 #F7F9FC);
                border: 1px solid #ECEFF5;
                border-radius: 14px;
            }
            QFrame#divider { background: #ECEFF5; }
            QLabel#infoTitle { color: #8F959E; }
            QLabel#infoBodyStrong { color: #1F2329; }
            QLabel#infoBody { color: #4E5969; }
            QLabel#countdown { color: #646A73; }
            QLabel#hint { color: #8F959E; }
            QProgressBar {
                background: #E8EBF1;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: #3370FF;
                border-radius: 3px;
            }
            QPushButton#primaryButton {
                background: #3370FF;
                color: #FFFFFF;
                border: 1px solid #3370FF;
                border-radius: 14px;
                padding: 0 18px;
            }
            QPushButton#primaryButton:hover { background: #2959D9; }
            QPushButton#primaryButton:pressed { background: #1E4FCC; }
            QPushButton#secondaryButton {
                background: #F7F8FA;
                color: #4E5969;
                border: 1px solid #DDE2EA;
                border-radius: 14px;
                padding: 0 16px;
            }
            QPushButton#secondaryButton:hover {
                background: #F1F3F6;
                border: 1px solid #CDD4DF;
            }
            QPushButton#secondaryButton:pressed { background: #EAEDEF; }
            """
        )

    def tick(self) -> None:
        self.remaining = max(self.remaining - 0.1, 0)
        self.progress.setValue(int(self.remaining * 1000))
        self.countdown.setText(f"自动继续 {int(self.remaining + 0.999)} s")
        if self.remaining <= 0:
            self.decision = "auto_approved"
            self.auto_approved = True
            self.accept()

    def handle_continue(self) -> None:
        self.decision = "approved"
        self.accept()

    def handle_cancel(self) -> None:
        self.decision = "cancelled"
        self.reject()


class BannerWidget(QWidget):
    def __init__(self, lease_path: str, operation_name: str, screen) -> None:
        super().__init__()
        self.lease_path = Path(lease_path)
        self.operation_name = operation_name
        self.target_screen = screen
        self.started = time.time()

        self.setObjectName("bannerRoot")
        self.setWindowTitle("Agent正在操作")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        card = QFrame()
        card.setObjectName("card")
        add_shadow(card, blur=22, y_offset=8)
        root.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(0)

        top = QHBoxLayout()
        top.setSpacing(8)
        badge = QFrame()
        badge.setObjectName("badge")
        badge_layout = QHBoxLayout(badge)
        badge_layout.setContentsMargins(10, 4, 10, 4)
        badge_text = QLabel("正在操作")
        badge_text.setFont(pick_font(9, QFont.Weight.DemiBold))
        badge_text.setObjectName("badgeText")
        badge_layout.addWidget(badge_text)
        top.addWidget(badge)
        top.addStretch(1)

        live_dot = QFrame()
        live_dot.setObjectName("liveDot")
        live_dot.setFixedSize(QSize(8, 8))
        top.addWidget(live_dot)

        self.elapsed = QLabel("0 s")
        self.elapsed.setFont(pick_font(9, QFont.Weight.DemiBold))
        self.elapsed.setObjectName("elapsed")
        top.addWidget(self.elapsed)
        layout.addLayout(top)

        title = QLabel("Agent正在操作")
        title.setFont(pick_font(12.5, QFont.Weight.DemiBold, display=True))
        title.setObjectName("title")
        title.setContentsMargins(0, 8, 0, 0)
        layout.addWidget(title)

        operation = QLabel(operation_name)
        operation.setObjectName("operation")
        operation.setFont(pick_font(9.5, QFont.Weight.Medium))
        operation.setWordWrap(True)
        operation.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        operation.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        operation.setContentsMargins(0, 6, 0, 0)
        layout.addWidget(operation)

        self.setStyleSheet(
            """
            QWidget#bannerRoot { background: transparent; }
            QFrame#card {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #FFFFFF, stop:1 #FBFCFE);
                border: 1px solid #E7EAF0;
                border-radius: 16px;
            }
            QFrame#badge {
                background: #EBF2FF;
                border: 1px solid #DBE7FF;
                border-radius: 11px;
            }
            QLabel#badgeText { color: #3370FF; }
            QFrame#liveDot {
                background: #3370FF;
                border-radius: 4px;
            }
            QLabel#title { color: #1F2329; }
            QLabel#operation { color: #646A73; }
            QLabel#elapsed { color: #3370FF; }
            """
        )

        apply_constrained_size(
            self,
            preferred_width=404,
            min_width=352,
            max_width=520,
            min_height=92,
            max_height=160,
        )
        move_to_screen_anchor(self, self.target_screen, top_offset=20)

        self.timer = QTimer(self)
        self.timer.setInterval(300)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def tick(self) -> None:
        if not self.lease_path.exists():
            self.close()
            return
        elapsed = int(time.time() - self.started)
        self.elapsed.setText(f"{elapsed} s")


def run_approval(args: argparse.Namespace) -> int:
    app = configure_app()
    dialog = ApprovalDialog(args.operation_name, args.details or "", args.timeout)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    dialog.exec()
    payload = {
        "approved": dialog.decision in {"approved", "auto_approved"},
        "decision": dialog.decision,
        "autoApproved": dialog.auto_approved,
        "targetScreen": serialize_screen(dialog.target_screen),
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()
    return 0


def resolve_banner_screen(lease_path: str):
    try:
        payload = json.loads(Path(lease_path).read_text(encoding="utf-8"))
    except Exception:
        payload = None

    target_screen = find_screen_from_payload(payload.get("targetScreen") if isinstance(payload, dict) else None)
    return target_screen or get_target_screen()


def run_banner(args: argparse.Namespace) -> int:
    app = configure_app()
    target_screen = resolve_banner_screen(args.lease_path)
    widget = BannerWidget(args.lease_path, args.operation_name, target_screen)
    widget.show()
    widget.raise_()
    return app.exec()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)

    approval = subparsers.add_parser("approval")
    approval.add_argument("--operation-name", required=True)
    approval.add_argument("--details", default="")
    approval.add_argument("--timeout", type=int, default=10)

    banner = subparsers.add_parser("banner")
    banner.add_argument("--lease-path", required=True)
    banner.add_argument("--operation-name", required=True)
    banner.add_argument("--details", default="")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.mode == "approval":
        return run_approval(args)
    if args.mode == "banner":
        return run_banner(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

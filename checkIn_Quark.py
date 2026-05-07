'''
new Env('夸克自动签到')
cron: 0 9 * * *

V2版-目前有效
使用移动端接口修复每日自动签到，移除原有的"登录验证"，参数有效期未知

V1版-已失效
受大佬 @Cp0204 的仓库项目启发改编
源码来自 GitHub 仓库：https://github.com/Cp0204/quark-auto-save
提取"登录验证""签到""领取"方法封装到下文中的"Quark"类中

Author: BNDou
Date: 2024-03-15 21:43:06
LastEditTime: 2025-11-18 03:49:26
FilePath: /Auto_Check_In/checkIn_Quark.py
Description: 
抓包流程：
    【手机端】
    ①打开抓包，手机端访问抽奖页
    ②找到url为 https://drive-m.quark.cn/1/clouddrive/act/growth/reward 的请求信息
    ③复制整段url，该链接后面必须要有参数: kps sign vcode，粘贴到环境变量
    环境变量名为 COOKIE_QUARK 多账户用 回车 或 && 分开
    user字段是用户名 (可是随意填写，多账户方便区分)
    例如: user=张三; url=https://drive-m.quark.cn/1/clouddrive/act/growth/reward?xxxxxx=xxxxxx&kps=abcdefg&sign=hijklmn&vcode=111111111;
    旧版环境变量格式也兼容，例如: user=张三; kps=abcdefg; sign=hijklmn; vcode=111111111;
'''
import json
import os
import sys
import winreg
import ctypes
import ctypes.wintypes
import threading
from datetime import datetime, timedelta

import requests
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QAbstractNativeEventFilter
from PyQt6.QtGui import QIcon, QAction, QColor, QPainter, QFont, QPen, QBrush, QPalette
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QDialog,
    QScrollArea, QSystemTrayIcon, QMenu, QCheckBox, QMessageBox,
    QFrame, QSizePolicy
)

APP_NAME = "QuarkAutoCheckIn"
if getattr(sys, 'frozen', False):
    DATA_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = DATA_DIR
USERS_FILE = os.path.join(DATA_DIR, "users.json")
RECORDS_FILE = os.path.join(DATA_DIR, "sign_records.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
ICON_PATH = os.path.join(BUNDLE_DIR, "icon.ico")
REGISTRY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REGISTRY_KEY = APP_NAME


def extract_params(url):
    query_start = url.find('?')
    query_string = url[query_start + 1:] if query_start != -1 else ''
    params = {}
    for param in query_string.split('&'):
        if '=' in param:
            key, value = param.split('=', 1)
            params[key] = value
    return {
        'kps': params.get('kps', ''),
        'sign': params.get('sign', ''),
        'vcode': params.get('vcode', '')
    }


PBT_APMRESUMEAUTOMATIC = 0x0012
WM_POWERBROADCAST = 0x0218


def ms_until_next_target(target_hour=0, target_minute=30):
    now = datetime.now()
    target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return int((target - now).total_seconds() * 1000)


class PowerBroadcastFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == WM_POWERBROADCAST:
                if msg.wParam == PBT_APMRESUMEAUTOMATIC:
                    QTimer.singleShot(3000, self._callback)
        return False, 0


class DataManager:
    def __init__(self):
        self._lock = threading.Lock()
        self.users = []
        self.sign_records = {}
        self.settings = {"auto_start": False, "auto_sign_on_start": True}
        self.load_all()

    def load_all(self):
        self.load_users()
        self.load_records()
        self.load_settings()

    def load_users(self):
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, 'r', encoding='utf-8') as f:
                    self.users = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.users = []
        else:
            self.users = []

    def save_users(self):
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.users, f, ensure_ascii=False, indent=2)

    def load_records(self):
        if os.path.exists(RECORDS_FILE):
            try:
                with open(RECORDS_FILE, 'r', encoding='utf-8') as f:
                    self.sign_records = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.sign_records = {}
        else:
            self.sign_records = {}

    def save_records(self):
        with open(RECORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.sign_records, f, ensure_ascii=False, indent=2)

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.settings = {"auto_start": False, "auto_sign_on_start": True}
        else:
            self.settings = {"auto_start": False, "auto_sign_on_start": True}

    def save_settings(self):
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=2)

    def add_user(self, nickname, url):
        user_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        user = {"id": user_id, "nickname": nickname, "url": url}
        self.users.append(user)
        self.save_users()
        return user

    def delete_user(self, user_id):
        self.users = [u for u in self.users if u["id"] != user_id]
        self.save_users()
        if user_id in self.sign_records:
            del self.sign_records[user_id]
            self.save_records()

    def is_signed_today(self, user_id):
        today = datetime.now().strftime("%Y-%m-%d")
        with self._lock:
            record = self.sign_records.get(user_id, "")
            return record == today

    def mark_signed(self, user_id):
        today = datetime.now().strftime("%Y-%m-%d")
        with self._lock:
            self.sign_records[user_id] = today
            self.save_records()

    def get_unsigned_users(self):
        return [u for u in self.users if not self.is_signed_today(u["id"])]

    def get_next_sign_target(self):
        ts = self.settings.get("next_sign_target", 0)
        return ts

    def set_next_sign_target(self, timestamp):
        self.settings["next_sign_target"] = timestamp
        self.save_settings()


class Quark:
    def __init__(self, user_data):
        self.param = user_data

    def convert_bytes(self, b):
        units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = 0
        while b >= 1024 and i < len(units) - 1:
            b /= 1024
            i += 1
        return f"{b:.2f} {units[i]}"

    def get_growth_info(self):
        url = "https://drive-m.quark.cn/1/clouddrive/capacity/growth/info"
        querystring = {
            "pr": "ucpro",
            "fr": "android",
            "kps": self.param.get('kps'),
            "sign": self.param.get('sign'),
            "vcode": self.param.get('vcode')
        }
        try:
            response = requests.get(url=url, params=querystring, timeout=15).json()
            if response.get("data"):
                return response["data"]
        except Exception:
            pass
        return False

    def get_growth_sign(self):
        url = "https://drive-m.quark.cn/1/clouddrive/capacity/growth/sign"
        querystring = {
            "pr": "ucpro",
            "fr": "android",
            "kps": self.param.get('kps'),
            "sign": self.param.get('sign'),
            "vcode": self.param.get('vcode')
        }
        data = {"sign_cyclic": True}
        try:
            response = requests.post(url=url, json=data, params=querystring, timeout=15).json()
            resp_data = response.get("data")
            if resp_data:
                return True, resp_data.get("sign_daily_reward", 0)
            else:
                return False, response.get("message", "未知错误")
        except Exception as e:
            return False, str(e)

    def do_sign(self):
        log = ""
        brief = ""
        success = False
        growth_info = self.get_growth_info()
        if growth_info:
            cap_sign = growth_info.get("cap_sign", {})
            cap_comp = growth_info.get("cap_composition", {})
            total_capacity = growth_info.get("total_capacity", 0)
            is_vip = growth_info.get("88VIP", False)

            log += (
                f" {'88VIP' if is_vip else '普通用户'} {self.param.get('user', '未知')}\n"
                f"💾 网盘总容量：{self.convert_bytes(total_capacity)}，"
                f"签到累计容量：")
            if "sign_reward" in cap_comp:
                log += f"{self.convert_bytes(cap_comp['sign_reward'])}\n"
            else:
                log += "0 MB\n"

            if cap_sign.get("sign_daily"):
                sign_daily_reward = cap_sign.get("sign_daily_reward", 0)
                sign_progress = cap_sign.get("sign_progress", 0)
                sign_target = cap_sign.get("sign_target", 0)
                log += (
                    f"✅ 签到日志: 今日已签到+{self.convert_bytes(sign_daily_reward)}，"
                    f"连签进度({sign_progress}/{sign_target})\n"
                )
                updated_growth_info = self.get_growth_info()
                if updated_growth_info:
                    updated_comp = updated_growth_info.get("cap_composition", {})
                    updated_total = updated_growth_info.get("total_capacity", 0)
                    log += (
                        f"📊 当前总容量：{self.convert_bytes(updated_total)}，"
                        f"签到累计容量：{self.convert_bytes(updated_comp.get('sign_reward', 0))}\n"
                    )
                    total_sign = updated_comp.get("sign_reward", 0)
                    brief = f"今日+{self.convert_bytes(sign_daily_reward)}\n累计+{self.convert_bytes(total_sign)}  总空间{self.convert_bytes(updated_total)}  连签{sign_progress}/{sign_target}"
                success = True
            else:
                sign, sign_return = self.get_growth_sign()
                if sign:
                    sign_progress = cap_sign.get("sign_progress", 0) + 1
                    sign_target = cap_sign.get("sign_target", 0)
                    log += (
                        f"✅ 执行签到: 今日签到+{self.convert_bytes(sign_return)}，"
                        f"连签进度({sign_progress}/{sign_target})\n"
                    )
                    updated_growth_info = self.get_growth_info()
                    if updated_growth_info:
                        updated_comp = updated_growth_info.get("cap_composition", {})
                        updated_total = updated_growth_info.get("total_capacity", 0)
                        log += (
                            f"📊 当前总容量：{self.convert_bytes(updated_total)}，"
                            f"签到累计容量：{self.convert_bytes(updated_comp.get('sign_reward', 0))}\n"
                        )
                        total_sign = updated_comp.get("sign_reward", 0)
                        brief = f"今日+{self.convert_bytes(sign_return)}\n累计+{self.convert_bytes(total_sign)}  总空间{self.convert_bytes(updated_total)}  连签{sign_progress}/{sign_target}"
                    success = True
                else:
                    log += f"❌ 签到异常: {sign_return}\n"
                    brief = f"❌ {sign_return}"
        else:
            log += "❌ 签到异常: 获取成长信息失败\n"
            brief = "❌ 获取成长信息失败"

        if success and not brief:
            brief = "✅ 签到成功"

        return log, brief, success


class SignWorker(QThread):
    finished = pyqtSignal(str, str, str, bool)

    def __init__(self, user, data_manager):
        super().__init__()
        self.user = user
        self.data_manager = data_manager

    def run(self):
        user_id = self.user["id"]
        nickname = self.user["nickname"]

        if self.data_manager.is_signed_today(user_id):
            self.finished.emit(user_id, f"✅ {nickname} 今日已签到", "", True)
            return

        url = self.user["url"]
        url_params = extract_params(url)
        user_data = {"user": nickname, "url": url}
        user_data.update(url_params)

        try:
            quark = Quark(user_data)
            log, brief, sign_ok = quark.do_sign()
            if sign_ok:
                self.data_manager.mark_signed(user_id)
                self.finished.emit(user_id, f"🙍🏻‍♂️{nickname}  {brief}", log, True)
            else:
                self.finished.emit(user_id, f"❌{nickname}  {brief}", log, False)
        except Exception as e:
            self.finished.emit(user_id, f"❌{nickname} 签到失败", str(e), False)


class BatchSignWorker(QThread):
    single_finished = pyqtSignal(str, str, str, bool)
    all_finished = pyqtSignal(str)

    def __init__(self, users, data_manager):
        super().__init__()
        self.users = users
        self.data_manager = data_manager

    def run(self):
        results = []
        for user in self.users:
            user_id = user["id"]
            nickname = user["nickname"]

            if self.data_manager.is_signed_today(user_id):
                self.single_finished.emit(user_id, f"✅{nickname} 今日已签到", "", True)
                results.append(f"✅{nickname} 今日已签到")
                continue

            url = user["url"]
            url_params = extract_params(url)
            user_data = {"user": nickname, "url": url}
            user_data.update(url_params)

            try:
                quark = Quark(user_data)
                log, brief, sign_ok = quark.do_sign()
                if sign_ok:
                    self.data_manager.mark_signed(user_id)
                    self.single_finished.emit(user_id, f"🙍🏻‍♂️{nickname}  {brief}", log, True)
                    results.append(f"🙍🏻‍♂️{nickname}  {brief}")
                else:
                    self.single_finished.emit(user_id, f"❌{nickname}  {brief}", log, False)
                    results.append(f"❌{nickname}  {brief}")
            except Exception as e:
                self.single_finished.emit(user_id, f"❌{nickname} 签到失败", str(e), False)
                results.append(f"❌{nickname} 签到失败")

        summary = "\n".join(results)
        self.all_finished.emit(summary)


class ToggleSwitch(QCheckBox):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFixedSize(44, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.isChecked():
            track_color = QColor("#89b4fa")
            thumb_color = QColor("#1e1e2e")
        else:
            track_color = QColor("#45475a")
            thumb_color = QColor("#6c7086")

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(0, 0, 44, 22, 11, 11)

        painter.setBrush(QBrush(thumb_color))
        if self.isChecked():
            painter.drawEllipse(24, 2, 18, 18)
        else:
            painter.drawEllipse(2, 2, 18, 18)

        painter.end()


class ResultDialog(QDialog):
    def __init__(self, title, content, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(460, 300)
        self.resize(500, 400)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
                border-radius: 12px;
            }
            QLabel {
                color: #cdd6f4;
            }
            QScrollArea {
                border: none;
                background-color: #313244;
                border-radius: 8px;
            }
            QScrollBar:vertical {
                background-color: #313244;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background-color: #45475a;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #585b70;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                border-radius: 8px;
                padding: 8px 24px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #74c7ec;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 16)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content_label = QLabel(content)
        content_label.setStyleSheet(
            "color: #bac2de; font-size: 12px; "
            "background-color: #313244; border-radius: 8px; padding: 12px;"
        )
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(content_label)
        layout.addWidget(scroll, 1)

        ok_btn = QPushButton("确定")
        ok_btn.setFixedWidth(100)
        ok_btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)


class CheckableUserItem(QFrame):
    def __init__(self, user, is_signed, parent=None):
        super().__init__(parent)
        self.user_id = user["id"]
        self._checked = not is_signed
        self._enabled = not is_signed
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor if self._enabled else Qt.CursorShape.ArrowCursor)
        self.setStyleSheet("background: transparent; border: none;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        self._indicator = QLabel()
        self._indicator.setFixedSize(20, 20)
        self._update_indicator()
        layout.addWidget(self._indicator)

        name_label = QLabel(user["nickname"])
        name_label.setStyleSheet(
            f"color: {'#cdd6f4' if self._enabled else '#585b70'}; font-size: 13px; border: none; background: transparent;"
        )
        layout.addWidget(name_label)

        layout.addStretch()

        status_label = QLabel("✅已签到" if is_signed else "⏳未签到")
        status_label.setStyleSheet(
            f"color: {'#a6e3a1' if is_signed else '#f9e2af'}; font-size: 11px; border: none; background: transparent;"
        )
        layout.addWidget(status_label)

    def _update_indicator(self):
        if self._checked:
            self._indicator.setText("✓")
            self._indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
            font = self._indicator.font()
            font.setPixelSize(14)
            font.setBold(True)
            self._indicator.setFont(font)
            self._indicator.setStyleSheet(
                "background-color: #89b4fa; border: 2px solid #89b4fa; border-radius: 5px; "
                "color: #1e1e2e; font-size: 14px; font-weight: bold;"
            )
        else:
            self._indicator.setText("")
            self._indicator.setStyleSheet(
                "background-color: #313244; border: 2px solid #45475a; border-radius: 5px;"
            )

    def isChecked(self):
        return self._checked

    def isEnabled(self):
        return self._enabled

    def mousePressEvent(self, event):
        if self._enabled:
            self._checked = not self._checked
            self._update_indicator()
        super().mousePressEvent(event)


class SelectUsersDialog(QDialog):
    def __init__(self, users, data_manager, parent=None):
        super().__init__(parent)
        self.users = users
        self.data_manager = data_manager
        self.selected_ids = []
        self.setWindowTitle("批量签到")
        self.setMinimumSize(400, 300)
        self.resize(420, 380)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
            }
            QLabel {
                color: #cdd6f4;
            }
            QScrollArea {
                border: none;
                background-color: #1e1e2e;
            }
            QScrollBar:vertical {
                background-color: #1e1e2e;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background-color: #45475a;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QPushButton {
                border-radius: 8px;
                padding: 8px 24px;
                font-size: 13px;
                font-weight: bold;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel("选择要签到的用户")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: #1e1e2e;")
        self.checks_layout = QVBoxLayout(scroll_content)
        self.checks_layout.setContentsMargins(4, 4, 4, 4)
        self.checks_layout.setSpacing(6)
        self.checks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.items = []
        for user in users:
            is_signed = self.data_manager.is_signed_today(user["id"])
            item = CheckableUserItem(user, is_signed)
            self.items.append(item)
            self.checks_layout.addWidget(item)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
            }
            QPushButton:hover {
                background-color: #45475a;
            }
        """)
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("开始签到")
        ok_btn.setFixedHeight(36)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e2e;
            }
            QPushButton:hover {
                background-color: #94e2d5;
            }
        """)
        ok_btn.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def get_selected_users(self):
        selected = []
        for item in self.items:
            if item.isChecked() and item.isEnabled():
                selected.append(item.user_id)
        return selected


class AddUserDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加用户")
        self.setFixedSize(500, 300)
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
            }
            QLabel {
                color: #cdd6f4;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 13px;
                min-height: 20px;
                selection-background-color: #89b4fa;
            }
            QLineEdit:focus {
                border: 1px solid #89b4fa;
                background-color: #333448;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(28, 24, 28, 24)

        title = QLabel("➕ 添加新用户")
        title.setStyleSheet("color: #cdd6f4; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        layout.addSpacing(8)

        nickname_label = QLabel("用户昵称")
        nickname_label.setStyleSheet("color: #a6adc8; font-size: 12px; font-weight: bold;")
        layout.addWidget(nickname_label)

        self.nickname_input = QLineEdit()
        self.nickname_input.setPlaceholderText("例如：张三")
        self.nickname_input.setFixedHeight(36)
        layout.addWidget(self.nickname_input)

        url_label = QLabel("签到 URL")
        url_label.setStyleSheet("color: #a6adc8; font-size: 12px; font-weight: bold;")
        layout.addWidget(url_label)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("粘贴完整URL（必须包含 kps、sign、vcode 参数）")
        self.url_input.setFixedHeight(36)
        layout.addWidget(self.url_input)

        placeholder_color = QColor("#585b70")
        for inp in (self.nickname_input, self.url_input):
            pal = inp.palette()
            pal.setColor(QPalette.ColorRole.PlaceholderText, placeholder_color)
            inp.setPalette(pal)

        layout.addSpacing(20)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setFixedHeight(36)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 8px;
                padding: 0 24px;
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #45475a;
            }
            QPushButton:hover {
                background-color: #45475a;
                border: 1px solid #585b70;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)

        self.ok_btn = QPushButton("添加")
        self.ok_btn.setFixedHeight(36)
        self.ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                border-radius: 8px;
                padding: 0 24px;
                font-size: 13px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #74c7ec;
            }
        """)
        self.ok_btn.clicked.connect(self.validate_and_accept)

        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.ok_btn)
        layout.addLayout(btn_layout)

    def validate_and_accept(self):
        nickname = self.nickname_input.text().strip()
        url = self.url_input.text().strip()

        if not nickname:
            QMessageBox.warning(self, "提示", "请输入用户昵称")
            return
        if not url:
            QMessageBox.warning(self, "提示", "请输入签到URL")
            return
        if "kps=" not in url or "sign=" not in url or "vcode=" not in url:
            QMessageBox.warning(self, "提示", "URL必须包含kps、sign、vcode参数")
            return

        self.accept()

    def get_data(self):
        return self.nickname_input.text().strip(), self.url_input.text().strip()


AVATAR_COLORS = [
    "#89b4fa", "#f38ba8", "#a6e3a1", "#f9e2af",
    "#cba6f7", "#94e2d5", "#fab387", "#74c7ec",
    "#eba0ac", "#b4befe", "#89dceb", "#f5c2e7",
]


def get_avatar_color(user_id):
    return AVATAR_COLORS[hash(user_id) % len(AVATAR_COLORS)]


class AvatarLabel(QLabel):
    def __init__(self, text, color, size=36, parent=None):
        super().__init__(parent)
        self._text = text
        self._color = color
        self._size = size
        self.setFixedSize(size, size)
        self.setStyleSheet("background: transparent; border: none;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(self._color)))
        painter.drawEllipse(0, 0, self._size, self._size)
        painter.setPen(QPen(QColor("#1e1e2e")))
        font = QFont()
        font.setPixelSize(int(self._size * 0.44))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)
        painter.end()


class UserCard(QFrame):
    delete_clicked = pyqtSignal(str)
    sign_clicked = pyqtSignal(str)

    def __init__(self, user, is_signed, index=0, parent=None):
        super().__init__(parent)
        self.user = user
        self.user_id = user["id"]
        self._color = get_avatar_color(user["id"])
        self.setFixedHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"""
            UserCard {{
                background-color: #313244;
                border-radius: 10px;
                border-left: 3px solid {self._color};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        initial = user["nickname"][0] if user["nickname"] else "?"
        avatar = AvatarLabel(initial, self._color, 36)
        layout.addWidget(avatar)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        display_name = user["nickname"]
        if len(display_name) > 12:
            display_name = display_name[:12] + "..."
        name_label = QLabel(display_name)
        name_label.setStyleSheet(
            "color: #cdd6f4; font-size: 14px; font-weight: bold; border: none; background: transparent;"
        )
        name_label.setToolTip(user["nickname"])
        info_layout.addWidget(name_label)

        url_text = user["url"]
        display_url = url_text[:40] + "..." if len(url_text) > 40 else url_text
        url_label = QLabel(display_url)
        url_label.setStyleSheet(
            "color: #585b70; font-size: 10px; border: none; background: transparent;"
        )
        url_label.setToolTip(url_text)
        info_layout.addWidget(url_label)

        layout.addLayout(info_layout, 1)

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFixedSize(72, 26)
        layout.addWidget(self.status_label)

        self.sign_btn = QPushButton("签到")
        self.sign_btn.setFixedSize(52, 26)
        self.sign_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sign_btn.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #74c7ec;
            }
            QPushButton:disabled {
                background-color: #45475a;
                color: #585b70;
            }
        """)
        self.sign_btn.clicked.connect(lambda: self.sign_clicked.emit(self.user_id))
        layout.addWidget(self.sign_btn)

        del_btn = QPushButton("删除")
        del_btn.setFixedSize(52, 26)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #f38ba8;
                border-radius: 6px;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #f38ba8;
            }
            QPushButton:hover {
                background-color: #f38ba8;
                color: #1e1e2e;
            }
        """)
        del_btn.clicked.connect(lambda: self.delete_clicked.emit(self.user_id))
        layout.addWidget(del_btn)

        self.update_status(is_signed)

    def update_status(self, is_signed):
        if is_signed:
            self.status_label.setText("✅ 已签到")
            self.status_label.setStyleSheet(
                "color: #a6e3a1; font-size: 11px; font-weight: bold; "
                "background-color: rgba(166,227,161,0.1); border-radius: 6px; padding: 2px 6px; border: none;"
            )
            self.sign_btn.setEnabled(False)
        else:
            self.status_label.setText("⏳ 未签到")
            self.status_label.setStyleSheet(
                "color: #f9e2af; font-size: 11px; font-weight: bold; "
                "background-color: rgba(249,226,175,0.1); border-radius: 6px; padding: 2px 6px; border: none;"
            )
            self.sign_btn.setEnabled(True)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.data_manager = DataManager()
        self.user_cards = {}
        self.sign_workers = []
        self.batch_worker = None
        self._is_batch_signing = False

        self.init_ui()
        self.init_tray()
        self.load_user_cards()

        self._power_filter = PowerBroadcastFilter(self.on_power_resume)
        QApplication.instance().installNativeEventFilter(self._power_filter)

        self._precise_timer = QTimer(self)
        self._precise_timer.setSingleShot(True)
        self._precise_timer.timeout.connect(self.check_and_sign)

        self._safety_timer = QTimer(self)
        self._safety_timer.timeout.connect(self._safety_check)
        self._safety_timer.start(4 * 3600 * 1000)

        QTimer.singleShot(1000, self._startup_check)

    def init_ui(self):
        self.setWindowTitle("夸克网盘签到助手")
        self.setFixedSize(560, 700)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
            }
            QScrollArea {
                border: none;
                background-color: #1e1e2e;
            }
            QScrollBar:vertical {
                background-color: #1e1e2e;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #45475a;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #585b70;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))
            self._set_win32_icon(ICON_PATH)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(12)

        title = QLabel("夸克网盘签到助手")
        title.setStyleSheet("color: #cdd6f4; font-size: 20px; font-weight: bold;")
        header.addWidget(title)

        header.addStretch()

        auto_start_label = QLabel("开机自启")
        auto_start_label.setStyleSheet("color: #6c7086; font-size: 12px;")
        header.addWidget(auto_start_label)

        self.auto_start_cb = ToggleSwitch()
        self.auto_start_cb.setChecked(self.data_manager.settings.get("auto_start", False))
        self.auto_start_cb.stateChanged.connect(self.toggle_auto_start)
        header.addWidget(self.auto_start_cb)

        main_layout.addLayout(header)

        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        add_btn = QPushButton("➕ 添加用户")
        add_btn.setFixedHeight(36)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                border-radius: 10px;
                font-size: 13px;
                font-weight: bold;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #74c7ec;
            }
        """)
        add_btn.clicked.connect(self.add_user)
        btn_bar.addWidget(add_btn)

        sign_all_btn = QPushButton("🚀 一键签到全部")
        sign_all_btn.setFixedHeight(36)
        sign_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #a6e3a1;
                color: #1e1e2e;
                border-radius: 10px;
                font-size: 13px;
                font-weight: bold;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #94e2d5;
            }
        """)
        sign_all_btn.clicked.connect(self.sign_all)
        btn_bar.addWidget(sign_all_btn)

        select_sign_btn = QPushButton("☑️ 批量签到")
        select_sign_btn.setFixedHeight(36)
        select_sign_btn.setStyleSheet("""
            QPushButton {
                background-color: #f9e2af;
                color: #1e1e2e;
                border-radius: 10px;
                font-size: 13px;
                font-weight: bold;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #f5c2e7;
            }
        """)
        select_sign_btn.clicked.connect(self.sign_selected)
        btn_bar.addWidget(select_sign_btn)

        help_btn = QPushButton("📋 抓包说明")
        help_btn.setFixedHeight(36)
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: #45475a;
                color: #cdd6f4;
                border-radius: 10px;
                font-size: 13px;
                font-weight: bold;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #585b70;
            }
        """)
        help_btn.clicked.connect(self.show_help)
        btn_bar.addWidget(help_btn)

        btn_bar.addStretch()
        main_layout.addLayout(btn_bar)

        self.user_count_label = QLabel("共 0 个用户")
        self.user_count_label.setStyleSheet("color: #6c7086; font-size: 12px;")
        main_layout.addWidget(self.user_count_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background-color: #1e1e2e;")
        self.cards_layout = QVBoxLayout(self.scroll_content)
        self.cards_layout.setContentsMargins(0, 0, 8, 0)
        self.cards_layout.setSpacing(10)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area, 1)

        self.log_label = QLabel("就绪")
        self.log_label.setStyleSheet(
            "color: #6c7086; font-size: 11px; padding: 4px 0;"
        )
        main_layout.addWidget(self.log_label)

    def init_tray(self):
        if os.path.exists(ICON_PATH):
            tray_icon = QIcon(ICON_PATH)
        else:
            tray_icon = self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon)

        self.tray = QSystemTrayIcon(tray_icon, self)
        self.tray.setToolTip("夸克网盘签到助手")

        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #45475a;
            }
        """)

        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)

        tray_menu.addSeparator()

        quit_action = QAction("退出程序", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    def show_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _set_win32_icon(self, icon_path):
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        LR_LOADFROMFILE = 0x0010
        IMAGE_ICON = 1

        hwnd = int(self.winId())
        small = ctypes.windll.user32.LoadImageW(0, icon_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        big = ctypes.windll.user32.LoadImageW(0, icon_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
        if small:
            old = ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small)
            if old:
                ctypes.windll.user32.DestroyIcon(old)
        if big:
            old = ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big)
            if old:
                ctypes.windll.user32.DestroyIcon(old)

    def quit_app(self):
        self.tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "夸克网盘签到助手",
            "程序已最小化到系统托盘，双击托盘图标可恢复窗口",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def toggle_auto_start(self, state):
        enabled = state == Qt.CheckState.Checked.value
        self.data_manager.settings["auto_start"] = enabled
        self.data_manager.save_settings()

        exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_SET_VALUE)
            if enabled:
                command = f'"{exe_path}"' if not exe_path.endswith('.py') else f'pythonw "{exe_path}"'
                winreg.SetValueEx(key, REGISTRY_KEY, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, REGISTRY_KEY)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            if enabled:
                QMessageBox.warning(self, "设置失败", f"设置开机自启失败：{str(e)}")

    def load_user_cards(self):
        for i in reversed(range(self.cards_layout.count())):
            item = self.cards_layout.takeAt(i)
            if item.widget():
                item.widget().deleteLater()
        self.user_cards.clear()

        for idx, user in enumerate(self.data_manager.users):
            is_signed = self.data_manager.is_signed_today(user["id"])
            card = UserCard(user, is_signed, index=idx)
            card.delete_clicked.connect(self.delete_user)
            card.sign_clicked.connect(self.sign_single_user)
            self.user_cards[user["id"]] = card
            self.cards_layout.addWidget(card)

        self.update_user_count()

    def update_user_count(self):
        total = len(self.data_manager.users)
        signed = sum(1 for u in self.data_manager.users if self.data_manager.is_signed_today(u["id"]))
        self.user_count_label.setText(f"共 {total} 个用户，今日已签到 {signed} 个")

    def add_user(self):
        dialog = AddUserDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            nickname, url = dialog.get_data()
            self.data_manager.add_user(nickname, url)
            self.load_user_cards()
            self.log_label.setText(f"✅ 已添加用户：{nickname}")

    def show_help(self):
        help_text = (
            "【手机端抓包步骤】\n\n"
            "1. 在手机上安装抓包工具（如 HttpCanary、Stream 等）\n\n"
            "2. 打开抓包工具，开始抓包\n\n"
            "3. 打开夸克网盘 APP，进入签到页面\n\n"
            "4. 在抓包工具中找到 URL 为：\n"
            "   https://drive-m.quark.cn/1/clouddrive/act/growth/reward\n\n"
            "5. 复制该请求的完整 URL（必须包含 kps、sign、vcode 三个参数）\n\n"
            "6. 回到本程序，点击「添加用户」，粘贴 URL 即可\n\n"
            "【注意事项】\n"
            "• URL 有效期未知，失效后需要重新抓包\n"
            "• 多个账户需要分别抓包获取各自的 URL"
        )
        dlg = ResultDialog("📋 抓包说明", help_text, self)
        dlg.exec()

    def delete_user(self, user_id):
        user = next((u for u in self.data_manager.users if u["id"] == user_id), None)
        if not user:
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除用户「{user['nickname']}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.data_manager.delete_user(user_id)
            self.load_user_cards()
            self.log_label.setText(f"🗑️ 已删除用户：{user['nickname']}")

    def sign_single_user(self, user_id):
        if self._is_batch_signing:
            self.log_label.setText("⚠️ 批量签到进行中，请稍候")
            return

        user = next((u for u in self.data_manager.users if u["id"] == user_id), None)
        if not user:
            return

        if self.data_manager.is_signed_today(user_id):
            self.log_label.setText(f"✅ {user['nickname']} 今日已签到")
            return

        self.log_label.setText(f"⏳ 正在为 {user['nickname']} 签到...")
        worker = SignWorker(user, self.data_manager)
        worker.finished.connect(self.on_sign_finished)
        self.sign_workers.append(worker)
        worker.start()

    def sign_all(self):
        if self._is_batch_signing:
            self.log_label.setText("⚠️ 批量签到进行中，请稍候")
            return

        if not self.data_manager.users:
            self.log_label.setText("⚠️ 请先添加用户")
            QMessageBox.information(self, "提示", "还没有添加用户，请先点击「添加用户」按钮添加。")
            return

        unsigned_users = self.data_manager.get_unsigned_users()
        if not unsigned_users:
            self.log_label.setText("✅ 所有用户今日均已签到")
            self.tray.showMessage("夸克网盘签到助手", "所有用户今日均已签到", QSystemTrayIcon.MessageIcon.Information, 2000)
            return

        self._is_batch_signing = True
        self.log_label.setText(f"⏳ 正在批量签到 {len(unsigned_users)} 个用户...")
        self.batch_worker = BatchSignWorker(unsigned_users, self.data_manager)
        self.batch_worker.single_finished.connect(self.on_sign_finished)
        self.batch_worker.all_finished.connect(self.on_batch_finished)
        self.batch_worker.start()

    def sign_selected(self):
        if self._is_batch_signing:
            self.log_label.setText("⚠️ 批量签到进行中，请稍候")
            return

        if not self.data_manager.users:
            self.log_label.setText("⚠️ 请先添加用户")
            QMessageBox.information(self, "提示", "还没有添加用户，请先点击「添加用户」按钮添加。")
            return

        dialog = SelectUsersDialog(self.data_manager.users, self.data_manager, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_ids = dialog.get_selected_users()
            if not selected_ids:
                QMessageBox.information(self, "提示", "没有选择任何用户。")
                return
            selected_users = [u for u in self.data_manager.users if u["id"] in selected_ids]
            self._is_batch_signing = True
            self.log_label.setText(f"⏳ 正在签到 {len(selected_users)} 个用户...")
            self.batch_worker = BatchSignWorker(selected_users, self.data_manager)
            self.batch_worker.single_finished.connect(self.on_sign_finished)
            self.batch_worker.all_finished.connect(self.on_batch_finished)
            self.batch_worker.start()

    def on_sign_finished(self, user_id, message, detail, success):
        self.sign_workers = [w for w in self.sign_workers if w.isRunning()]

        if user_id in self.user_cards:
            self.user_cards[user_id].update_status(self.data_manager.is_signed_today(user_id))
        self.update_user_count()

        if success:
            self.log_label.setText(message)
            if not self._is_batch_signing and detail:
                dlg = ResultDialog(message, detail, self)
                dlg.exec()
        else:
            self.log_label.setText(message)
            if not self._is_batch_signing:
                dlg = ResultDialog("签到失败", detail or message, self)
                dlg.exec()

    def on_batch_finished(self, summary):
        self._is_batch_signing = False
        self.batch_worker = None
        self._schedule_next_sign()
        self.log_label.setText("✅ 批量签到完成")
        self.tray.showMessage("夸克网盘签到助手", summary, QSystemTrayIcon.MessageIcon.Information, 5000)
        dlg = ResultDialog("批量签到结果", summary, self)
        dlg.exec()

    def _startup_check(self):
        self._calibrate_registry()

        if not self.data_manager.users:
            self.log_label.setText("👋 欢迎使用，请先添加用户")
            self._schedule_next_sign()
            return

        self._do_check_and_sign()

    def _calibrate_registry(self):
        if not self.data_manager.settings.get("auto_start", False):
            return
        exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
        expected_cmd = f'"{exe_path}"' if not exe_path.endswith('.py') else f'pythonw "{exe_path}"'
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_READ)
            try:
                current_cmd, _ = winreg.QueryValueEx(key, REGISTRY_KEY)
            except FileNotFoundError:
                current_cmd = None
            winreg.CloseKey(key)

            if current_cmd != expected_cmd:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(key, REGISTRY_KEY, 0, winreg.REG_SZ, expected_cmd)
                winreg.CloseKey(key)
        except FileNotFoundError:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_PATH, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, REGISTRY_KEY, 0, winreg.REG_SZ, expected_cmd)
            winreg.CloseKey(key)
        except Exception:
            pass

    def check_and_sign(self):
        self._do_check_and_sign()

    def _do_check_and_sign(self):
        if self._is_batch_signing:
            return

        if not self.data_manager.users:
            self.log_label.setText("👋 请先添加用户")
            self._schedule_next_sign()
            return

        unsigned = self.data_manager.get_unsigned_users()
        if unsigned:
            self.log_label.setText(f"⏳ 自动签到：{len(unsigned)} 个用户待签到")
            self._is_batch_signing = True
            self.batch_worker = BatchSignWorker(unsigned, self.data_manager)
            self.batch_worker.single_finished.connect(self.on_sign_finished)
            self.batch_worker.all_finished.connect(self._on_auto_batch_finished)
            self.batch_worker.start()
        else:
            self.log_label.setText("✅ 所有用户今日均已签到")
            self._schedule_next_sign()

    def _on_auto_batch_finished(self, summary):
        self._is_batch_signing = False
        self.batch_worker = None
        self._schedule_next_sign()
        self.log_label.setText("✅ 自动签到完成")
        self.tray.showMessage("夸克网盘签到助手", summary, QSystemTrayIcon.MessageIcon.Information, 5000)

    def _schedule_next_sign(self):
        ms = ms_until_next_target(0, 30)
        self._precise_timer.start(ms)
        target_ts = int((datetime.now() + timedelta(milliseconds=ms)).timestamp() * 1000)
        self.data_manager.set_next_sign_target(target_ts)

    def _safety_check(self):
        if not self.data_manager.users:
            return
        if self._is_batch_signing:
            return
        if not self._precise_timer.isActive():
            self._schedule_next_sign()
        self._do_check_and_sign()

    def on_power_resume(self):
        if not self.data_manager.users:
            return
        self.log_label.setText("⚡ 检测到系统唤醒，检查签到状态...")
        self._do_check_and_sign()


def main():
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("QuarkAutoCheckIn")

    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\QuarkAutoCheckIn_Mutex")
    if ctypes.windll.kernel32.GetLastError() == 183:
        ctypes.windll.user32.MessageBoxW(None, "程序已在运行中，请检查系统托盘。", "夸克网盘签到助手", 0x40)
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    app.setStyleSheet("""
        QMessageBox {
            background-color: #1e1e2e;
        }
        QMessageBox QLabel {
            color: #cdd6f4;
        }
        QMessageBox QPushButton {
            background-color: #45475a;
            color: #cdd6f4;
            border-radius: 6px;
            padding: 6px 16px;
            min-width: 60px;
        }
        QMessageBox QPushButton:hover {
            background-color: #585b70;
        }
    """)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

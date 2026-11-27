"""
Bridge to Android system APIs: accessibility + notification-listener state.

Safe to import on desktop; every function fails soft so the UI can show a
friendly message instead of crashing.
"""
import re
import sys

IS_ANDROID = "android" in sys.modules or hasattr(sys, "getandroidapilevel")

PACKAGE = "com.autoaccount"
ACCESSIBILITY_SERVICE_CLASS = "com.autoaccount.AutoAccountAccessibilityService"
NOTIFICATION_SERVICE_CLASS = "com.autoaccount.AutoAccountNotificationService"

SERVICE_DESCRIPTION = (
    "开启后，全自动记账本可以在你打开支付宝、微信、银行等应用的支付/收款页面时，"
    "读取页面文字识别金额与商户，先弹窗让你确认，确认后才写入账本。"
    "不会上传任何屏幕内容。"
)


def _split_components(setting_value: str) -> list:
    """系统把多个组件用冒号串在一个字符串里，这里拆开、去空。"""
    if not setting_value:
        return []
    return [c.strip() for c in re.split(r"[:,]", setting_value) if c.strip()]


def _is_component_enabled(setting_value: str, full_class: str) -> bool:
    """匹配本应用的某个服务是否在已开启列表里。

    Android 存进 Settings 的是 ComponentName 的简写形式（同包时为
    ``包名/.类名``），个别情况下也可能是全限定 ``包名/包名.类名``，
    两种都要认，否则明明开了也会被判成未开启。
    """
    simple_class = full_class.rsplit(".", 1)[-1]
    for comp in _split_components(setting_value):
        if "/" not in comp:
            continue
        comp_pkg, comp_cls = comp.split("/", 1)
        if comp_pkg != PACKAGE:
            continue
        if comp_cls in (full_class, "." + simple_class, simple_class):
            return True
    return False


def _autoclass(name):
    from jnius import autoclass

    return autoclass(name)


def _activity():
    try:
        PythonActivity = _autoclass("org.kivy.android.PythonActivity")
        return PythonActivity.mActivity
    except Exception:
        from android import mActivity

        return mActivity


def _enabled_services(setting_name: str) -> str:
    Settings = _autoclass("android.provider.Settings")
    resolver = _activity().getContentResolver()
    value = Settings.Secure.getString(resolver, setting_name)
    return value or ""


def check_accessibility_permission() -> bool:
    """Whether this app's accessibility service is enabled."""
    try:
        Settings = _autoclass("android.provider.Settings")
        enabled = _enabled_services(Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES)
        return _is_component_enabled(enabled, ACCESSIBILITY_SERVICE_CLASS)
    except Exception as exc:
        print(f"[android_bridge] 读取无障碍状态失败：{exc}")
        return False


def check_notification_permission() -> bool:
    """Whether this app is allowed to read notifications."""
    try:
        Settings = _autoclass("android.provider.Settings")
        enabled = _enabled_services(Settings.Secure.ENABLED_NOTIFICATION_LISTENERS)
        return _is_component_enabled(enabled, NOTIFICATION_SERVICE_CLASS)
    except Exception as exc:
        print(f"[android_bridge] 读取通知监听状态失败：{exc}")
        return False


def open_accessibility_settings() -> bool:
    """Open the system accessibility settings page."""
    return _open_settings(
        "ACTION_ACCESSIBILITY_SETTINGS",
        "android.settings.ACCESSIBILITY_SETTINGS",
    )


def open_notification_settings() -> bool:
    """Open the notification-access settings page."""
    try:
        return _open_settings(
            "ACTION_NOTIFICATION_LISTENER_SETTINGS",
            "android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS",
        )
    except RuntimeError:
        return _open_settings("ACTION_SETTINGS", "android.settings.SETTINGS")


def _open_settings(constant_name: str, fallback_action: str) -> bool:
    action = fallback_action
    try:
        Settings = _autoclass("android.provider.Settings")
        action = getattr(Settings, constant_name, fallback_action)
    except Exception:
        pass
    try:
        Intent = _autoclass("android.content.Intent")
        intent = Intent(action)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        _activity().startActivity(intent)
        return True
    except Exception as exc:
        raise RuntimeError(f"无法打开系统设置：{exc}") from exc

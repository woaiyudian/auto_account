"""
Bridge to Android system APIs: accessibility + notification-listener state.

Safe to import on desktop; every function fails soft so the UI can show a
friendly message instead of crashing.
"""
import sys

IS_ANDROID = "android" in sys.modules or hasattr(sys, "getandroidapilevel")

ACCESSIBILITY_COMPONENT = (
    "com.autoaccount/com.autoaccount.AutoAccountAccessibilityService"
)
NOTIFICATION_COMPONENT = (
    "com.autoaccount/com.autoaccount.AutoAccountNotificationService"
)

SERVICE_DESCRIPTION = (
    "开启后，全自动记账本可以在你打开支付宝、微信、银行等应用的支付/收款页面时，"
    "读取页面文字识别金额与商户，先弹窗让你确认，确认后才写入账本。"
    "不会上传任何屏幕内容。"
)


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
        return ACCESSIBILITY_COMPONENT in enabled
    except Exception:
        return False


def check_notification_permission() -> bool:
    """Whether this app is allowed to read notifications."""
    try:
        Settings = _autoclass("android.provider.Settings")
        enabled = _enabled_services(Settings.Secure.ENABLED_NOTIFICATION_LISTENERS)
        if not enabled:
            return False
        return (
            NOTIFICATION_COMPONENT in enabled
            or "com.autoaccount" in enabled
        )
    except Exception:
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

[app]
title = 全自动记账本
package.name = autoaccount
package.domain = com

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,ttf,otf
source.exclude_dirs = tests,bin,venv,.venv,__pycache__,.git,.idea,.vscode,data,tmp,android

version = 1.0.0

# kivy only – no extra native deps needed for the core app
# requests 由 p4a 配方自动带入，无需在本声明固定（版本会被解析阶段剥除）
requirements = python3,kivy==2.3.2

# 使用 CI 工作流里预先克隆并打过补丁的 p4a（跳过 host venv 无法安装的安卓编译轮）
p4a.source_dir = p4a-local

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,FOREGROUND_SERVICE,POST_NOTIFICATIONS,WAKE_LOCK,RECEIVE_BOOT_COMPLETED,CAMERA,VIBRATE
android.api = 34
android.minapi = 24
android.ndk_api = 24
# 复用 CI 镜像自带的 Android SDK（已含 android-34 平台与 build-tools）。
# 注意：buildozer 里 android.sdk 已废弃，必须用 android.sdk_path 才生效。
android.sdk_path = /usr/local/lib/android/sdk
# 个人自用先只编 arm64-v8a，把首遍编译时间砍掉一半
android.archs = arm64-v8a
android.enable_androidx = True
android.allow_backup = True
# 首次构建时自动接受 SDK 许可，否则 CI 里会卡住
android.accept_sdk_license = True

# Java sources for the accessibility service / receivers
# 源码根目录必须是包含 com/autoaccount 的那一层
android.add_src = android/src/main/java

# Extra XML merged directly under <manifest>（如 <queries>）。
# 注意：p4a 模板里没有在 <application> 内部放置自定义 service/receiver 的槽位，
# 因此自定义服务/广播先不写进清单，等主包能出 APK 后再用其他方式接入。
android.extra_manifest_xml = android/res/extra_manifest.xml

# App resources: 服务名称等字符串；无障碍配置 xml
android.add_resources = android/src/main/res/values:values
android.res_xml = android/res/xml/accessibility_service_config.xml

# ---- 自用签名（不是上架）--------------------------------------------------
# 固定一套签名，保证以后重新打包能「覆盖升级」而不丢数据。
# 这是个人自用密钥，密码公开无妨；但绝不可用于上架任何应用商店。
android.release_keystore = android/autoaccount.keystore
android.release_keyalias = autoaccount
android.release_keystore_passwd = autoaccount
android.release_keyalias_passwd = autoaccount
android.release_artifact = apk

android.logcat_filters = *:S python:D

[buildozer]
log_level = 2
warn_on_root = 0

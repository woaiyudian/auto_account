[app]
title = 全自动记账本
package.name = autoaccount
package.domain = com

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,ttf,otf
source.exclude_dirs = tests,bin,venv,.venv,__pycache__,.git,.idea,.vscode,data,tmp,android

version = 1.0.0

# kivy only – no extra native deps needed for the core app
requirements = python3,kivy

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,FOREGROUND_SERVICE,POST_NOTIFICATIONS,WAKE_LOCK,RECEIVE_BOOT_COMPLETED,CAMERA,VIBRATE
android.api = 33
android.minapi = 24
android.ndk_api = 24
android.archs = arm64-v8a,armeabi-v7a
android.private_storage = True
android.enable_androidx = True
android.allow_backup = True

# Java sources for the accessibility service / receivers
android.add_src = android/src

# Extra XML merged into <manifest> and <application>
android.extra_manifest_xml = android/res/extra_manifest.xml
android.extra_application_xml = android/res/extra_application.xml

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
warn_on_root = 1

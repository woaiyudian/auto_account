"""给 python-for-android 的 build.py 打一个最小补丁。

背景：p4master 在「纯 Python 模块安装阶段」会用 host 侧 venv 里的 pip 安装
配方自动带入的依赖（requests、urllib3 等）。解析阶段（--dry-run）能认出
安卓 arm64 的编译轮，但 host venv 的 pip 按 x86_64 校验轮子平台标签，会拒绝
安装 `*-android_arm64_v8a.whl`，导致整个构建在最后一步失败。

补丁只做一件事：把「不是平台无关（py3-none-any）」的轮子从安装清单里跳过，
不再写进 requirements.txt。我们项目本身不依赖这些第三方库，跳过其中的编译
轮子不影响主程序运行。

用法：
    python scripts/patch_p4a.py p4a-local/pythonforandroid/build.py
"""
import sys
from pathlib import Path


def main() -> None:
    target = Path(sys.argv[1])
    text = target.read_text(encoding="utf-8")

    old = (
        '        if pure_python:\n'
        '            processed_modules.append(module["download_info"]["url"])'
    )
    new = (
        '        if pure_python and is_wheel_platform_independent(filename):\n'
        '            processed_modules.append(module["download_info"]["url"])'
    )

    count = text.count(old)
    if count != 1:
        print(f"[patch] 未找到预期的补丁位置（匹配次数={count}），中止以防误改")
        sys.exit(1)

    target.write_text(text.replace(old, new), encoding="utf-8")
    print(f"[patch] 已给 {target} 打上纯 Python 轮子跳过补丁")


if __name__ == "__main__":
    main()

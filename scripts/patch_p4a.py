"""给本地克隆的 python-for-android 打两个最小补丁。

补丁一（build.py）：
    纯 Python 模块安装阶段，host venv 的 pip 会按 x86_64 校验轮子平台标签，
    拒绝安装 `*-android_arm64_v8a.whl`。补丁把非平台无关（py3-none-any）的
    轮子从安装清单里跳过。项目本身不依赖这些第三方库，跳过编译轮不影响主程序。

补丁二（AndroidManifest 模板）：
    p4a 的 sdl2 模板没有在 <application> 内部放自定义 service/receiver 的槽位，
    本脚本把仓库里的 extra_application.xml（服务、广播声明）插到 <application>
    开标签结束之后，作为合法的 application 子元素。

用法：
    python scripts/patch_p4a.py <build.py> <AndroidManifest.tmpl.xml> <extra_application.xml>
"""
import sys
from pathlib import Path


def patch_build_py(target: Path) -> None:
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
        print(f"[patch] build.py 未找到预期补丁位置（匹配次数={count}），中止以防误改")
        sys.exit(1)

    target.write_text(text.replace(old, new), encoding="utf-8")
    print(f"[patch] 已给 {target} 打上纯 Python 轮子跳过补丁")


def patch_manifest_template(template: Path, fragment: Path) -> None:
    text = template.read_text(encoding="utf-8")

    # 幂等：已经注入过就不再重复插入
    if "com.autoaccount" in text:
        print(f"[patch] {template.name} 已包含自定义服务/广播，跳过注入")
        return

    anchor = 'android:extractNativeLibs="true" >'
    if anchor not in text:
        print("[patch] 清单模板里没找到 <application> 开标签锚点，中止以防误改")
        sys.exit(1)

    fragment_lines = [
        line for line in fragment.read_text(encoding="utf-8").strip().splitlines()
    ]
    # 作为 application 的子元素，整体再加 4 空格缩进
    injected = ["    " + line if line.strip() else "" for line in fragment_lines]

    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if anchor in line:
            lines[index + 1:index + 1] = ["\n"] + [
                l + "\n" for l in injected
            ]
            break

    template.write_text("".join(lines), encoding="utf-8")
    print(f"[patch] 已把服务/广播注入 {template}")


def main() -> None:
    build_py = Path(sys.argv[1])
    manifest_tmpl = Path(sys.argv[2])
    fragment = Path(sys.argv[3])

    patch_build_py(build_py)
    patch_manifest_template(manifest_tmpl, fragment)


if __name__ == "__main__":
    main()

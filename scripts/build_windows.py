"""在Windows构建公开原创桌面EXE；先校验题库，所有输出与源码分开。"""
from pathlib import Path
import argparse
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT.parent / (ROOT.name + "-windows-build"))
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("该构建入口需要Windows；其它系统可运行源码。")
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        parser.error("输出目录须在源码目录外，避免生成文件影响再次校验。")
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/check_public_release.py")], cwd=ROOT, check=True)
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
               "--onefile", "--windowed", "--noupx", "--name", "小圆爱刷题MAX",
               "--icon", str(ROOT / "assets/app.ico"),
               "--distpath", str(output), "--workpath", str(output / "build"),
               "--specpath", str(output), "--collect-data", "customtkinter"]
    for path, destination in [("data/questions.json", "data"), ("data/campaign.json", "data"), ("assets", "assets")]:
        command.extend(["--add-data", str(ROOT / path) + ";" + destination])
    for name in ["store", "books", "game", "game_ui", "game_art", "game_skills", "game_shop", "finance", "finance_ui", "PIL._tkinter_finder"]:
        command.extend(["--hidden-import", name])
    command.append(str(ROOT / "src/main.py"))
    subprocess.run(command, cwd=ROOT, check=True)
    print(output / "小圆爱刷题MAX.exe")


if __name__ == "__main__":
    main()

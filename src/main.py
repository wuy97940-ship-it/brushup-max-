"""打包入口。"""
import sys
from pathlib import Path

# 把当前目录加入 sys.path，便于打包后 import store/app
sys.path.insert(0, str(Path(__file__).resolve().parent))

from game_ui import main  # noqa: E402

if __name__ == "__main__":
    main()

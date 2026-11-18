"""打包入口。"""
import sys
import argparse
import os
from pathlib import Path

# 把当前目录加入 sys.path，便于打包后 import store/app
sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == "__main__":
    # 必须在任何游戏/UI模块导入之前选定存档；隔离环境变量优先。
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--data-dir')
    parser.add_argument('--verify-desktop',action='store_true')
    parser.add_argument('--qa-dir')
    parser.add_argument('--qa-fail-fast',action='store_true')
    parser.add_argument('--qa-steps')
    parser.add_argument('--qa-materials-only',action='store_true')
    parser.add_argument('--trace-storage')
    options, _ = parser.parse_known_args()
    if options.data_dir and not os.environ.get('XY_SHUATI_DATA_DIR'):
        os.environ['XY_SHUATI_DATA_DIR'] = str(Path(options.data_dir).expanduser().resolve())
    if options.trace_storage:
        from desktop_storage_diagnostics import install
        install(options.trace_storage)
    from game_ui import main
    main()

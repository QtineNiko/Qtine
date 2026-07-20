#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VIRUS PET - 病毒宠物游戏
一个仿病毒风格的电子宠物游戏，你的病毒可能比你更有控制权...
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game.engine import GameEngine


def main():
    print("=" * 50)
    print("  VIRUS PET - 病毒宠物")
    print("=" * 50)
    print()
    print("正在初始化系统...")
    
    try:
        game = GameEngine()
        print("系统初始化完成！")
        print()
        print("操作说明:")
        print("  [1] 喂食   [2] 训练")
        print("  [3] 玩耍   [4] 升级")
        print("  [S] 保存   [ESC] 菜单/退出")
        print()
        print("警告：你的病毒可能会有自己的想法...")
        print("=" * 50)
        print()
        
        game.run()
        
    except KeyboardInterrupt:
        print("\n游戏已中断")
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

import sys
from PySide6.QtWidgets import QApplication, QDialog

from game.city_asset_manager import ensure_city_assets
from game.portrait_generator import ensure_default_portrait_resources
from ui.login_dialog import LoginDialog
from ui.main_window import MainWindow


def main():
    # 启动前按需补齐默认主角立绘资源（首次运行或资源缺失时生成）
    generated_count, total_count = ensure_default_portrait_resources()
    if generated_count:
        print(f"已自动生成默认立绘：{generated_count}/{total_count}")

    # 启动前按需补齐城市场景化 UI 资源（背景图与建筑图）
    bg_generated, building_generated = ensure_city_assets()
    if bg_generated or building_generated:
        print(f"已自动生成城市资源：{bg_generated} 张背景，{building_generated} 组建筑")

    # 创建 Qt 应用实例，管理整个应用的事件循环和全局设置
    app = QApplication(sys.argv)

    # 显示登录 / 主菜单界面，按用户选择决定启动方式
    login = LoginDialog()
    if login.exec() != QDialog.Accepted:
        # 用户点击关闭按钮（X）退出
        sys.exit(0)
    action = login.selected_action
    if action == LoginDialog.QUIT:
        sys.exit(0)

    if action == LoginDialog.NEW_GAME:
        window = MainWindow(start_mode="new", slot=login.new_slot_name)
    elif action == LoginDialog.LOAD:
        window = MainWindow(start_mode="load", slot=login.selected_slot)
    else:
        window = MainWindow()

    # 显示主窗口
    window.show()

    # 进入 Qt 事件循环，等待用户交互
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

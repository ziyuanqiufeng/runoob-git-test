# -*- coding: utf-8 -*-
"""玩法指南弹窗：快速上手 / 系统总览 / AI 功能 / 常见问题。"""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QTextBrowser

_BODY_STYLE = """
<style>
body { font-family: "Microsoft YaHei", sans-serif; font-size: 13px; color: #2c3e50; line-height: 1.7; }
h2 { color: #8a6d3b; border-bottom: 1px solid #e8e0cc; padding-bottom: 4px; }
b.key { color: #b8860b; }
li { margin-bottom: 4px; }
.tip { color: #2f9e44; }
.warn { color: #c92a2a; }
</style>
"""

_TAB_QUICK = _BODY_STYLE + """
<h2>三分钟上手</h2>
<li><b class="key">创建角色</b>：输入道号、选性别，可点「捏脸…」定制形象（AI 立绘或拼装部件），随后完成灵根觉醒与流派选择。</li>
<li><b class="key">核心循环</b>：<b>闭关</b>涨修为 → 修为攒满<b>突破</b> → 大境界需渡天劫（小心心魔）→ 换更凶险的地图<b>游历</b>。</li>
<li><b class="key">游历</b>：会随机遭遇奇遇、危机、商人与妖兽；开启 AI 剧情时，稍后还会追加一段专属剧情（✨ AI 剧情）。</li>
<li><b class="key">成长目标</b>：从练气一层修至元婴期，最终飞升成仙——或走出完全不同的结局。</li>
<p class="tip">小贴士：突破前记得存够气血与丹药；野外比城池危险得多。</p>
"""

_TAB_SYSTEMS = _BODY_STYLE + """
<h2>系统入口地图</h2>
<li><b class="key">头像右键</b>：捏脸（重捏形象）/ 更换立绘。</li>
<li><b class="key">菜单栏 · 设置</b>：音量、功能开关（15 项模块自助开关）、测试 AI 连接、难度模式。</li>
<li><b class="key">登录页 · 选择存档</b>：载入 / 删除 / <b>导出</b> / <b>导入</b>（zip 分享包，含立绘）。</li>
<li><b class="key">左侧面板</b>：状态与装备总览，点「详情」展开任务与灵根信息。</li>
<li><b class="key">右侧操作面板</b>：闭关、游历、宗门、家族、领地、坊市、拍卖、图鉴等——部分功能随境界渐进解锁。</li>
<p class="tip">提示：大境界突破会解锁新的操作与地点。</p>
"""

_TAB_AI = _BODY_STYLE + """
<h2>AI 功能说明</h2>
<li><b class="key">AI 动态事件</b>：游历事件的文案会按你的地点、心境动态改写；关闭后使用固定文案。</li>
<li><b class="key">AI 剧情增强</b>：游历后后台调用大模型生成专属剧情，完成后以「✨ AI 剧情」追加到日志——等待期间可继续操作。</li>
<li><b class="key">AI 立绘 / 捏脸</b>：按特征生成整张立绘（约 1 分钟），或用 25 个水墨部件即时拼装头像。</li>
<li><b class="key">诊断</b>：设置 → 「测试 AI 连接」，一键检查 key、网络与图模型可用性。</li>
<p class="warn">注意：AI 功能需要联网；服务繁忙时会自动重试，实在不行会回退到离线文案，不影响游戏进行。</p>
"""

_TAB_FAQ = _BODY_STYLE + """
<h2>常见问题</h2>
<li><b>AI 剧情没有出现？</b><br>
检查 设置 → 功能开关 中「AI 剧情增强」是否开启；AI 文案是生成完成后<b>稍后追加</b>的，不是立即出现。</li>
<li><b>AI 生图失败了？</b><br>
点「测试 AI 连接」自查；服务繁忙（队列满）会自动重试 3 次。也可到捏脸界面用「拼装捏脸」即时出形象。</li>
<li><b>突破后头像没变？</b><br>
捏过脸的角色会保留自定义形象；想要高阶立绘请到捏脸界面重新生成。</li>
<li><b>想把角色分享给朋友？</b><br>
登录页 → 选择存档 → 选中槽位 → 「导出」生成 zip；对方「导入」即可，立绘和捏脸一并带走。</li>
<li><b>存档会坏吗？</b><br>
存档采用原子写入，另有最近 5 份滚动备份在 saves/backups/ 下，出问题可手动回滚。</li>
"""


class HelpDialog(QDialog):
    """玩法指南：快速上手 / 系统总览 / AI 功能 / 常见问题。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("玩法指南")
        self.resize(560, 500)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._tab(_TAB_QUICK), "快速上手")
        tabs.addTab(self._tab(_TAB_SYSTEMS), "系统总览")
        tabs.addTab(self._tab(_TAB_AI), "AI 功能")
        tabs.addTab(self._tab(_TAB_FAQ), "常见问题")
        layout.addWidget(tabs)

    @staticmethod
    def _tab(html):
        browser = QTextBrowser()
        browser.setHtml(html)
        browser.setOpenExternalLinks(False)
        browser.setStyleSheet("QTextBrowser { background: transparent; border: none; }")
        return browser

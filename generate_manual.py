"""
生成项目说明书的 Word 文档。
格式要求：
- 标题：黑体三号（16pt），1.5倍行距
- 正文：宋体四号（14pt），首行缩进2字符，单倍行距
"""

import os

from docx import Document
from docx.shared import Pt, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn


def set_run_font(run, font_name, font_size):
    """设置单个 run 的中文字体与字号。"""
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn('w:eastAsia'), font_name)
    run.font.size = Pt(font_size)


def add_heading(doc, text, level=1):
    """添加标题：黑体三号、1.5倍行距、加粗。"""
    p = doc.add_heading(level=level)
    run = p.add_run(text)
    set_run_font(run, '黑体', 16)
    run.bold = True
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    return p


def add_subheading(doc, text):
    """添加二级标题：黑体四号、1.5倍行距、加粗。"""
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_run_font(run, '黑体', 14)
    run.bold = True
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(3)
    return p


def add_body(doc, text):
    """添加正文：宋体四号、首行缩进2字符、单倍行距。"""
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_run_font(run, '宋体', 14)
    p.paragraph_format.first_line_indent = Cm(0.74)  # 约2字符
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.space_after = Pt(3)
    return p


def add_list_item(doc, text):
    """添加列表项：宋体四号、单倍行距、无首行缩进。"""
    p = doc.add_paragraph(style='List Bullet')
    run = p.add_run(text)
    set_run_font(run, '宋体', 14)
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.space_after = Pt(2)
    return p


def main():
    doc = Document()

    # 页面边距设置
    sections = doc.sections[0]
    sections.top_margin = Cm(2.54)
    sections.bottom_margin = Cm(2.54)
    sections.left_margin = Cm(3.17)
    sections.right_margin = Cm(3.17)

    # 文档标题
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run('《问道长生》项目说明书')
    set_run_font(run, '黑体', 22)
    run.bold = True
    title.paragraph_format.line_spacing = 1.5
    title.paragraph_format.space_after = Pt(18)

    # 1. 项目概述
    add_heading(doc, '一、项目概述')
    add_body(doc,
             '本项目是一款以东方修仙文化为背景的模拟经营类单机游戏，项目代号与游戏名称为《问道长生》。玩家将在游戏中体验从凡人到渡劫飞升、再入轮回的完整修仙生命周期：历经练气、筑基、金丹、元婴、化神、炼虚共 22 级境界，在修炼、洞府经营、势力社交、城池政治与世界事件中做出关键抉择，最终冲击天门试炼白日飞升，并开启前世羁绊延续的多周目轮回。项目采用配置驱动的设计思路，大量数值、事件、对话与地图通过 JSON 文件维护，便于后续持续扩展与平衡调整。')

    # 2. 技术架构
    add_heading(doc, '二、技术架构')
    add_subheading(doc, '2.1 技术栈')
    add_list_item(doc, '编程语言：Python 3.10')
    add_list_item(doc, '图形界面框架：PySide6 6.6.3（Qt 绑定）')
    add_list_item(doc, '图像处理：Pillow（资源生成与立绘处理）')
    add_list_item(doc, '配置格式：JSON（境界、灵根、技能、NPC、任务、对话等）')
    add_list_item(doc, '测试框架：pytest')

    add_subheading(doc, '2.2 程序分层')
    add_body(doc,
             '项目代码按职责划分为四层：配置层负责纯数据加载与校验；管理层负责单一系统逻辑，不直接操作 UI；引擎层组合各 Manager，提供月度推进与跨系统接口；UI 层仅负责展示与玩家输入，通过引擎调用逻辑。')

    # 3. 核心系统
    add_heading(doc, '三、核心系统')

    add_subheading(doc, '3.1 修炼系统')
    add_body(doc,
             '修炼系统以境界成长为主线。当前已配置的境界共 22 级：练气期一到九层、筑基初/中/后/圆满、金丹初/中/后/圆满、元婴期、化神期与化神圆满、炼虚期与炼虚圆满（终局链）。每个境界拥有最大真气值、突破成功率与寿命加成；元婴之后需求线性递增，月收入随境界成长（realm_qi_scale 系数），无卡死路径。玩家每月选择修炼、闭关或探索，积累修为并尝试突破；大境界突破触发渡劫（雷劫 + 心魔考验），失败可能走火入魔。')

    add_subheading(doc, '3.1.1 天门试炼（飞升终局）')
    add_body(doc,
             '炼虚圆满攒满修为后，突破进入三阶段天门试炼：问心（心魔 80 以上直接走火入魔，50 以上道基不稳）、渡雷（天道注视 90 以上直接天道降罚）、天门一跃（概率判定：基础 50%，受心魔、天道注视、道心 80 以上加成、飞升丹 30% 加成影响；每次尝试燃烧一半灵石）。普通失败为兵解重创（修为七成折损、寿元减三十年、天道注视加深），可重整再战；仅两条红线触发坏结局。成功即飞升，按业力分入飞升成仙、魔道登天或大道独行三种结局。试炼全程以结算面板逐阶段演出。')

    add_subheading(doc, '3.2 灵根系统')
    add_body(doc,
             '灵根分为五行灵根（金、木、水、火、土）与变异灵根（雷、冰、风）。灵根数量越多，修炼所需经验越高；灵根纯度越高，对应属性技能伤害越高。特殊融合灵根如“雷火交加”“冰风双生”等可解锁专属神通。五行之间存在克制关系：金克木、木克土、土克水、水克火、火克金；变异灵根也存在额外克制：雷克金、冰克火、风克木。')

    add_subheading(doc, '3.3 流派系统')
    add_body(doc,
             '游戏提供十种修炼流派：法修、体修、剑修、邪修、丹修、器修、御兽修、魂修、阵修、符修。每个流派拥有独立属性修正、专属资源与专属技能。流派之间存在克制关系，切换流派需通过“道师”NPC，代价是遗忘专属技能并清空流派资源。流派与灵根之间还存在协同加成，例如剑修配金灵根可提升 20% 伤害。')

    add_subheading(doc, '3.4 战斗系统')
    add_body(doc,
             '战斗采用回合制，结算时考虑五行与流派克制、控制效果、暴击、闪避等要素。被克制时伤害降低，克制敌方时伤害提升。高境界角色对低境界角色具有压制效果。战斗结果影响玩家声望、掉落与后续事件。')

    add_subheading(doc, '3.5 城池系统')
    add_body(doc,
             '城池是月度决策中枢，采用 2.5D 全景背景配合透明热点的方式呈现建筑。主要建筑包括城主府、客栈、坊市、演武场、炼丹阁、洞府与宗门办事处等。玩家可在城中接取任务、交易、打听消息、参与城主竞选、颁布城池政策。不同城池有独特氛围，例如玄水城水系资源丰富，赤焰城对丹修与火系修炼友好。')

    add_subheading(doc, '3.6 洞府系统')
    add_body(doc,
             '洞府是修炼与经营的重要场所。城中洞府采用租赁制，提供固定修炼加成与闭关场所；高境界后可在野外占据灵脉建立私人洞府，拥有药园、炼丹室、炼器台、灵兽园、聚灵阵等设施，并可升级提升产出与防御。洞府每月可能触发灵气潮汐、妖兽袭扰或 NPC 访客事件。')

    add_subheading(doc, '3.7 社交与 NPC 系统')
    add_body(doc,
             'NPC 拥有好感度、势力标签、作息规律与关系网络。玩家可通过送礼、论道、双修、收徒等方式建立关系。关系链会相互影响，击杀 NPC 可能引发其亲友、宗门或道侣的复仇。阵营分为正道、魔道与中立，影响 NPC 对玩家的初始态度与可加入势力。')

    add_subheading(doc, '3.7.1 NPC 记忆与主动事件（AI 角色引擎）')
    add_body(doc,
             'NPC 拥有跨时间的共同经历记忆：结道侣、双修、论道、收徒、传艺等动作自动写入记忆（每个 NPC 保留最近五条），对话窗口以共同回忆时间线展示；游历事件的 AI 剧情生成会自动携带这些记忆，使笔下角色带着与玩家的真实历史。NPC 还会依据关系状态主动发起事件：亲密度达标的道侣定期赠丹、在册弟子定期聆教、恩怨未解的宿敌随机寻衅（小额伤害、不致死）。事件频率、门槛与惩罚全部配置化于 social_events.json。')

    add_subheading(doc, '3.7.2 轮回系统（多周目）')
    add_body(doc,
             '达成任意结局后可转世重修：按前世成就结算继承点（境界分乘系数 + 名望分 + 转世次数加成 + 业力修正），自由兑换灵根保留（带纯度衰减）、天赋、属性加成、携带物品、关系保留与业力洗涤，也可空手转世。前世羁绊最深的道侣或挚友将转世为重逢 NPC——初见触发重逢演出，前世情分化为好感加成；修行年谱完整保留每一世的记录，实现跨世史诗。跨世继承业力、遗物链与转世次数；恩怨、社交与成就随新世重新积累。')

    add_subheading(doc, '3.8 事件系统')
    add_body(doc,
             '事件按触发层级分为随机遭遇、城池事件、宗门事件、世界事件与个人剧情，共 38 个随机事件（28 地点 × 事件差异化权重全覆盖）。其中神游太虚、天门遗音、虚空炼形为终局专属事件，带境界门槛（化神 19 级以上、炼虚 21 级以上），低境界玩家不可见。世界 BOSS 定期刷新，玩家可参与讨伐。历史年表记录世界大事与玩家抉择，跨转世完整延续，作为结局结算、成就解锁与转世继承的依据。')

    add_subheading(doc, '3.9 经济系统')
    add_body(doc,
             '经济循环涵盖任务奖励、摆摊、拍卖、洞府产出、宗门俸禄与劫掠护送等收入来源；消耗出口包括租金、突破丹药、装备强化、设施升级、社交送礼与传送费用。城池政策、世界事件与天气会影响物价，形成套利空间。')

    # 4. 配置系统
    add_heading(doc, '四、配置系统')
    add_body(doc,
             '项目强调配置驱动，所有核心数据均存放于 config 目录下，并通过 tools/validate_configs.py 进行统一校验。主要配置包括：')
    add_list_item(doc, '核心配置：spiritual_roots.json（灵根）、cultivation_paths.json（流派）、realms.json（境界，22 级）、skills.json（技能）、mind_methods.json（心法）')
    add_list_item(doc, '世界配置：locations.json（地点，28×38 事件权重矩阵）、npcs.json（NPC）、sects.json（宗门）、city_maps.json（城市地图）')
    add_list_item(doc, '事件配置：events.json、city_events.json、world_events.json、quests.json、dialogues.json')
    add_list_item(doc, '经济配置：items.json、recipes.json（含飞升丹/化婴丹方）、economy.json、market_npcs.json')
    add_list_item(doc, '终局与轮回：ascension.json（天门试炼参数）、reincarnation.json（转世继承规则）、social_events.json（NPC 主动事件）')
    add_list_item(doc, '其他配置：weather.json、achievements.json、reputation.json、ai_config.json 等')

    # 5. 项目结构
    add_heading(doc, '五、项目结构')
    add_body(doc,
             '项目根目录下包含以下主要目录：')
    add_list_item(doc, 'assets/：美术资源，包括城市全景背景、建筑热点图与角色立绘')
    add_list_item(doc, 'config/：JSON 配置文件，覆盖游戏全部数值与内容')
    add_list_item(doc, 'docs/：设计文档，包括 GDD 目录与整体设计概览')
    add_list_item(doc, 'game/：游戏逻辑层，包含各类 Manager 与 Engine')
    add_list_item(doc, 'ui/：用户界面层，包含主窗口与各类 Dialog')
    add_list_item(doc, 'tools/：辅助工具，包括配置校验、城市资源生成、热点编辑')
    add_list_item(doc, 'tests/：pytest 测试用例，覆盖主要系统')

    # 6. 当前状态与路线图
    add_heading(doc, '六、当前状态与路线图')
    add_subheading(doc, '6.1 已完成')
    add_list_item(doc, '修炼、突破、渡劫与 22 级境界终局链（含终局丹药与化婴丹产出）')
    add_list_item(doc, '天门试炼三阶段飞升终局（含结算演出面板）')
    add_list_item(doc, '轮回系统：继承选择、前世羁绊、转世重逢 NPC、宿慧叙事、年谱跨世延续')
    add_list_item(doc, 'AI 角色引擎三步：NPC 记忆、主动事件、剧情喂料')
    add_list_item(doc, '城市地图与建筑交互；洞府租赁与闭关')
    add_list_item(doc, '摆摊、拍卖、客栈传闻、演武场、妖兽攻城、城主政策')
    add_list_item(doc, '多结局系统（8 种）与多周目模式（夺舍重生/天道轮回等）')

    add_subheading(doc, '6.2 质量与实测基线')
    add_list_item(doc, '测试：1249 用例全绿（含轮回全链路集成测试与转世状态语义矩阵）')
    add_list_item(doc, '性能：单月结算 0.02ms、存档原子写 8ms、事件抽取 14.2 微秒')
    add_list_item(doc, '平衡：总通关约 565 年（纯闭关带丹 + 天门试炼期望），无卡死路径，详见 docs/balance_report_20260916.md')

    add_subheading(doc, '6.3 可扩展方向')
    add_list_item(doc, '更多终局专属事件与演出打磨')
    add_list_item(doc, 'NPC 主动事件池扩容（师门互动、江湖奇遇）')
    add_list_item(doc, '多周目特殊模式深度内容')

    # 7. 验收标准
    add_heading(doc, '七、验收标准')
    add_body(doc,
             '新玩家应能在 10 分钟内理解核心循环；每个大境界都解锁新系统以保持新鲜感；任何系统改动后需通过 tools/validate_configs.py 与 pytest tests/（1249 用例）全部测试；配置占比不低于 70%，关键数值调整不应依赖代码修改。')

    # 保存
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs', '《问道长生》项目说明书.docx')
    doc.save(output_path)
    print(f'说明书已生成：{output_path}')


if __name__ == '__main__':
    main()

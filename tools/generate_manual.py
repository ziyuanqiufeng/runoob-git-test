# -*- coding: utf-8 -*-
"""
修仙模拟器操作说明书生成器
标题：黑体3号，1.5倍行间距
正文：宋体4号，首行缩进2字符，单倍行间距
"""
from docx import Document
from docx.shared import Pt, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def set_cell_shading(cell, fill_color):
    """设置单元格背景色"""
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), fill_color)
    cell._tc.get_or_add_tcPr().append(shading)


def add_heading_custom(doc, text, level=1):
    """添加自定义格式标题"""
    p = doc.add_heading('', level=level)
    run = p.add_run(text)
    run.font.name = '黑体'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
    if level == 1:
        run.font.size = Pt(16)  # 3号
    elif level == 2:
        run.font.size = Pt(14)  # 4号
    elif level == 3:
        run.font.size = Pt(12)  # 5号
    p.paragraph_format.line_spacing = 1.5 if level == 1 else 1.0
    return p


def add_para(doc, text, indent=True, bold=False):
    """添加正文段落"""
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.name = '宋体'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    run.font.size = Pt(14)  # 4号
    p.paragraph_format.line_spacing = 1.0
    if indent:
        p.paragraph_format.first_line_indent = Cm(0.74)  # 2字符
    if bold:
        run.bold = True
    return p


def add_table(doc, headers, rows):
    """添加表格"""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = 'Table Grid'

    # 表头
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ''
        p = cell.paragraphs[0]
        run = p.add_run(h)
        run.font.name = '黑体'
        run._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
        run.font.size = Pt(10.5)  # 6号
        p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_cell_shading(cell, 'D9E2F3')

    # 数据行
    for r_idx, row_data in enumerate(rows):
        for c_idx, cell_data in enumerate(row_data):
            cell = table.rows[r_idx + 1].cells[c_idx]
            cell.text = ''
            p = cell.paragraphs[0]
            run = p.add_run(str(cell_data))
            run.font.name = '宋体'
            run._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
            run.font.size = Pt(10.5)
            p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER if c_idx == 0 else WD_ALIGN_PARAGRAPH.LEFT

    return table


def create_manual():
    doc = Document()

    # 设置文档默认字体
    style = doc.styles['Normal']
    style.font.name = '宋体'
    style._element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    style.font.size = Pt(14)

    # 标题
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run('修仙模拟器操作说明书')
    run.font.name = '黑体'
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
    run.font.size = Pt(22)  # 1号
    title.paragraph_format.line_spacing = 1.5

    doc.add_paragraph()

    # 一、游戏概述
    add_heading_custom(doc, '一、游戏概述', 1)
    add_para(doc, '本游戏为一款文字修仙模拟器，玩家扮演一名初入仙途的修士，通过修炼、战斗、社交、经营等方式逐步提升实力，最终渡劫飞升。游戏采用"菜单驱动 + 月推进"模式，所有事件以月份为时间单位推进，操作入口集中在主窗口顶部导航栏与各功能弹窗中。')

    # 二、核心属性
    add_heading_custom(doc, '二、核心属性', 1)
    headers = ['属性', '英文标识', '说明']
    rows = [
        ['境界', 'realm_id', '修为层次，从炼气初期至渡劫期，共22级'],
        ['气血', 'qi', '修炼经验值，达到阈值可尝试突破境界'],
        ['生命值', 'health', '战斗与行动消耗，归零时强制休息'],
        ['灵石', 'spirit_stone', '通用货币，用于购买道具、建造、交易'],
        ['悟道点', 'enlightenment_points', '高境界获得，用于领悟神通'],
        ['道心值', 'mental_state', '0~100，影响心境等级与心魔触发概率'],
        ['心魔值', 'heart_demon', '0~100，超过阈值触发心魔劫'],
    ]
    add_table(doc, headers, rows)
    doc.add_paragraph()

    # 三、境界与突破
    add_heading_custom(doc, '三、境界与突破', 1)
    add_heading_custom(doc, '3.1 境界列表', 2)
    headers = ['境界 ID', '境界名称']
    rows = [
        ['foundation_early', '炼气初期'],
        ['foundation_mid', '炼气中期'],
        ['foundation_late', '炼气后期'],
        ['foundation_peak', '炼气巅峰'],
        ['qi_condensation_early', '筑基初期'],
        ['qi_condensation_mid', '筑基中期'],
        ['qi_condensation_late', '筑基后期'],
        ['qi_condensation_peak', '筑基巅峰'],
        ['golden_core_early', '金丹初期'],
        ['golden_core_mid', '金丹中期'],
        ['golden_core_late', '金丹后期'],
        ['golden_core_peak', '金丹巅峰'],
        ['nascence_formation_early', '元婴初期'],
        ['nascence_formation_mid', '元婴中期'],
        ['nascence_formation_late', '元婴后期'],
        ['nascence_formation_peak', '元婴巅峰'],
        ['void_glorification_early', '化神初期'],
        ['void_glorification_mid', '化神中期'],
        ['void_glorification_late', '化神后期'],
        ['void_glorification_peak', '化神巅峰'],
        ['tribulation_early', '渡劫初期'],
        ['tribulation_late', '渡劫后期'],
    ]
    add_table(doc, headers, rows)
    doc.add_paragraph()

    add_heading_custom(doc, '3.2 突破方式', 2)
    add_para(doc, '突破需要满足以下全部条件：')
    add_para(doc, '（1）气血达到该境界的 breakthrough_qi_required 阈值；', indent=False)
    add_para(doc, '（2）境界未达到当前上限；', indent=False)
    add_para(doc, '（3）心境满足要求（部分高阶境界需要特定道心等级）；', indent=False)
    add_para(doc, '（4）消耗 breakthrough_cost 灵石。', indent=False)
    add_para(doc, '突破有失败概率，失败后气血扣减，心境可能下降。')

    # 四、修炼系统
    add_heading_custom(doc, '四、修炼系统', 1)
    add_heading_custom(doc, '4.1 修仙流派', 2)
    add_para(doc, '玩家选择一个修仙流派，不同流派影响修炼速度、加成与技能获得。选定后不可更改。')
    headers = ['流派 ID', '名称', '核心特性']
    rows = [
        ['sword', '剑宗', '攻击加成高，剑意积累快'],
        ['demon', '魔道', '杀戮收益高，心境下降快'],
        ['zhengdao', '正道', '道心稳定，被动防御高'],
        ['alchemy', '丹宗', '炼丹成功率加成'],
        ['artifact', '器宗', '炼器品质加成'],
        ['array', '阵道', '阵法效果增强'],
    ]
    add_table(doc, headers, rows)
    doc.add_paragraph()

    add_heading_custom(doc, '4.2 灵根', 2)
    add_para(doc, '灵根决定修炼速度与属性加成，常见类型：')
    add_para(doc, '（1）heavenly（天灵根）：修炼速度最快；', indent=False)
    add_para(doc, '（2）earthly（地灵根）：修炼速度中等；', indent=False)
    add_para(doc, '（3）mortal（凡灵根）：修炼速度较慢。', indent=False)
    doc.add_paragraph()

    add_heading_custom(doc, '4.3 修炼操作', 2)
    add_para(doc, '点击主窗口「修炼」按钮，可选择修炼方式：')
    add_para(doc, '（1）打坐：恢复气血，消耗灵石；', indent=False)
    add_para(doc, '（2）闭关：在洞府或宗门秘境中加速修炼；', indent=False)
    add_para(doc, '（3）参悟：消耗时间领悟技能。', indent=False)

    # 五、战斗系统
    add_heading_custom(doc, '五、战斗系统', 1)
    add_heading_custom(doc, '5.1 战斗类型', 2)
    headers = ['类型', '触发方式', '说明']
    rows = [
        ['野外战斗', '地点探索事件', '随机遭遇敌人'],
        ['宗门战', '宗门弹窗→战争标签', '与敌对宗门争夺灵脉'],
        ['世界BOSS', '宗门弹窗→世界BOSS标签', '挑战上古神兽/血魔尊者'],
        ['擂台挑战', '擂台系统', '与其他修士PK'],
        ['领地守卫', '领地系统月度结算', '抵御妖兽袭扰'],
    ]
    add_table(doc, headers, rows)
    doc.add_paragraph()

    add_heading_custom(doc, '5.2 战斗结果结算', 2)
    add_para(doc, '胜利：获得修为（qi）、灵石、物品掉落（从敌人配置中随机掉落）。')
    add_para(doc, '失败：扣除生命值，可能被俘或被迫逃跑，继续在同一地点探索时仍可再次挑战。')
    doc.add_paragraph()

    add_heading_custom(doc, '5.3 世界BOSS挑战条件', 2)
    add_para(doc, '（1）境界须达到 min_realm_order 要求；', indent=False)
    add_para(doc, '（2）BOSS活跃时才可挑战（击败后进入重生冷却）；', indent=False)
    add_para(doc, '（3）击败后获得固定参与奖励+掉落奖励。', indent=False)

    # 六、宗门系统
    add_heading_custom(doc, '六、宗门系统', 1)
    add_heading_custom(doc, '6.1 加入宗门', 2)
    add_para(doc, '点击主窗口「宗门」按钮→选择「加入宗门」→选择目标宗门并提交申请（需消耗贡献或灵石）。')
    doc.add_paragraph()

    add_heading_custom(doc, '6.2 宗门职位', 2)
    headers = ['职位', '解锁功能']
    rows = [
        ['outer（外门弟子）', '基础修炼'],
        ['inner（内门弟子）', '可参与宗门战、外交任务'],
        ['elder（长老）', '可管理领地、发动战争'],
        ['leader（宗主）', '可签订结盟、分配资源'],
    ]
    add_table(doc, headers, rows)
    doc.add_paragraph()

    add_heading_custom(doc, '6.3 贡献、声望与忠诚度', 2)
    add_para(doc, '贡献：通过战斗、任务、宗门活动获得，用于晋升职位。')
    add_para(doc, '声望：影响NPC态度与世界事件触发。')
    add_para(doc, '忠诚度：影响宗门战成功率加成。')
    doc.add_paragraph()

    add_heading_custom(doc, '6.4 宗门战', 2)
    add_para(doc, '内门弟子以上可发起。胜率计算公式：')
    add_para(doc, '胜率 = 基础胜率 + 贡献加成 + 宗门战参与加成 + 同盟加成 - 对方难度', indent=False)
    add_para(doc, '胜利：获得贡献、声望，夺取灵脉控制权。失败：损失健康、忠诚度下降，关系恶化。')
    doc.add_paragraph()

    add_heading_custom(doc, '6.5 灵脉争夺', 2)
    add_para(doc, '灵脉是宗门间的战略资源，控制灵脉可提升洞府修炼加成。灵脉按地点分布，战败方失去控制权，胜方获得。')

    # 七、外交系统
    add_heading_custom(doc, '七、外交系统', 1)
    add_heading_custom(doc, '7.1 宗门关系', 2)
    headers = ['关系值范围', '状态']
    rows = [
        ['-100 ~ -51', '死敌'],
        ['-50 ~ -1', '敌对'],
        ['0', '中立'],
        ['1 ~ 49', '友好'],
        ['50 ~ 100', '至交'],
    ]
    add_table(doc, headers, rows)
    doc.add_paragraph()

    add_heading_custom(doc, '7.2 外交任务', 2)
    add_para(doc, '点击宗门弹窗→「外交」标签，可接取外交任务：')
    headers = ['任务ID', '名称', '目标关系', '职位', '消耗']
    rows = [
        ['gift_to_friend', '结交友好宗门', '友好', '内门', '300贡献'],
        ['sabotage_enemy', '破坏敌对宗门', '敌对', '内门', '400贡献'],
        ['mediate_neutral', '游说中立宗门', '中立', '外门', '200贡献'],
    ]
    add_table(doc, headers, rows)
    doc.add_paragraph()
    add_para(doc, '任务成功：提升/降低目标宗门关系，获得贡献与忠诚度奖励。')
    add_para(doc, '任务失败：关系变化幅度缩小，无额外奖励。')
    doc.add_paragraph()

    add_heading_custom(doc, '7.3 结盟', 2)
    add_para(doc, '（1）与友好宗门（关系≥50）可签订同盟；', indent=False)
    add_para(doc, '（2）消耗5000贡献；', indent=False)
    add_para(doc, '（3）同盟有效期30个月，到期自动解除；', indent=False)
    add_para(doc, '（4）同盟期间：商店折扣+10%，宗门战胜率+10%；', indent=False)
    add_para(doc, '（5）可单方面解除同盟（关系归零）。', indent=False)

    # 八、洞府系统
    add_heading_custom(doc, '八、洞府系统', 1)
    add_heading_custom(doc, '8.1 洞府类型', 2)
    headers = ['类型', '解锁条件', '说明']
    rows = [
        ['租借洞府', '初始可用', '花费灵石短期租用'],
        ['私人洞府', '拥有后解锁', '永久建筑，可升级'],
        ['野外洞府', '探索发现', '占领野生洞府'],
    ]
    add_table(doc, headers, rows)
    doc.add_paragraph()

    add_heading_custom(doc, '8.2 洞府设施', 2)
    add_para(doc, '修炼室：修炼速度加成；药园：种植灵草，产出炼丹材料；炼丹房：炼制丹药；炼器房：锻造法器；闭关室：快速恢复状态。')
    doc.add_paragraph()

    add_heading_custom(doc, '8.3 洞府占领', 2)
    add_para(doc, '野外存在可占领洞府，占领后需消耗灵石与时间建设，成功后成为永久私人洞府。占领时需通过战斗击退原主人。')

    # 九、家族系统
    add_heading_custom(doc, '九、家族系统', 1)
    add_heading_custom(doc, '9.1 创建家族', 2)
    add_para(doc, '（1）境界≥金丹初期（order 14）；（2）消耗5000灵石+200声望；（3）可自定义家族名、家训、阵营。')
    doc.add_paragraph()

    add_heading_custom(doc, '9.2 家族成员', 2)
    add_para(doc, '成员类型：后裔（自动繁衍）、收徒（手动收徒）、联姻（与其他家族联姻获得配偶）。')
    add_para(doc, '成员任务分配：cultivate（修炼）、manage（经营）、explore（探索）、diplomacy（外交）。')
    doc.add_paragraph()

    add_heading_custom(doc, '9.3 家族月度结算', 2)
    add_para(doc, '每月自动结算家族产出（灵石、修为、声望），同时触发随机家族事件。')

    # 十、社交系统
    add_heading_custom(doc, '十、社交系统', 1)
    add_heading_custom(doc, '10.1 NPC交互', 2)
    add_para(doc, '在地点中可遇到NPC，进行以下交互：')
    add_para(doc, '（1）论道：与NPC讨论道法，获得悟道点或心境变化；', indent=False)
    add_para(doc, '（2）双修：与道侣双修，提升双方修为（需道侣关系）；', indent=False)
    add_para(doc, '（3）收徒：收NPC为徒弟，徒弟可继承家族；', indent=False)
    add_para(doc, '（4）恩怨：建立或解除恩怨关系，影响后续战斗与任务。', indent=False)
    doc.add_paragraph()

    add_heading_custom(doc, '10.2 恩怨系统', 2)
    add_para(doc, '每个NPC与玩家有独立恩怨值（-100~100）。击杀/帮助NPC会改变恩怨；恩怨过深时NPC可能派杀手报复；恩怨过深时无法与该NPC的宗门结盟。')
    doc.add_paragraph()

    add_heading_custom(doc, '10.3 伴侣系统', 2)
    add_para(doc, '可通过特定事件或NPC互动结识伴侣；伴侣提供被动加成（修炼速度、战斗能力等）；可生育后裔，后裔继承部分属性；伴侣死亡会导致道心大幅下降。')

    # 十一、物品系统
    add_heading_custom(doc, '十一、物品系统', 1)
    add_heading_custom(doc, '11.1 物品类型', 2)
    headers = ['类型', '说明']
    rows = [
        ['消耗品', '丹药、符箓、卷轴，使用后立即生效'],
        ['装备', '武器、防具、饰品，提供被动加成'],
        ['材料', '灵草、矿石、兽核，用于炼丹/炼器'],
        ['货币', '灵石，通用交易媒介'],
        ['任务物品', '完成任务所需的特定道具'],
    ]
    add_table(doc, headers, rows)
    doc.add_paragraph()

    add_heading_custom(doc, '11.2 购买渠道', 2)
    add_para(doc, '坊市：使用灵石购买基础道具；宗门商店：使用贡献购买，同盟宗门有折扣；拍卖行：与其他玩家交易稀有物品；掉落：战斗击败敌人后随机掉落。')

    # 十二、炼丹与炼器
    add_heading_custom(doc, '十二、炼丹与炼器', 1)
    add_heading_custom(doc, '12.1 炼丹', 2)
    add_para(doc, '需要「炼丹房」建筑；消耗灵草+灵石，产出丹药；丹药品级：凡丹→灵丹→仙丹；品质影响丹药效果（修为加成、治疗效果等）。')
    doc.add_paragraph()

    add_heading_custom(doc, '12.2 炼器', 2)
    add_para(doc, '需要「炼器房」建筑；消耗矿石+灵石，产出法器；法器品级：凡器→灵器→神器；品质影响攻击力、防御力等属性。')
    doc.add_paragraph()

    add_heading_custom(doc, '12.3 品质判定', 2)
    add_para(doc, '品质由以下因素决定：玩家炼丹/炼器技能等级、建筑等级加成、灵草/矿石品质、随机幸运判定。')

    # 十三、秘境与探索
    add_heading_custom(doc, '十三、秘境与探索', 1)
    add_heading_custom(doc, '13.1 秘境类型', 2)
    headers = ['秘境ID', '名称', '解锁条件']
    rows = [
        ['qingyun_secret', '青云秘境', '加入天剑宗'],
        ['jiuyuan_secret', '九幽秘境', '加入血煞宗'],
        ['zixiao_secret', '紫霄秘境', '加入紫霄宫'],
    ]
    add_table(doc, headers, rows)
    doc.add_paragraph()

    add_heading_custom(doc, '13.2 探索操作', 2)
    add_para(doc, '（1）点击「探索」按钮；（2）选择目标地点（有解锁条件的地点需满足条件）；（3）探索触发随机事件（战斗、发现、奇遇等）；（4）事件结果影响修为、物品、心境等。')

    # 十四、心境与道心
    add_heading_custom(doc, '十四、心境与道心', 1)
    add_heading_custom(doc, '14.1 道心值', 2)
    add_para(doc, '道心值（0~100）反映修士的精神状态：高道心提升悟道成功率，降低心魔触发概率；低道心修炼速度下降，易生心魔。')
    doc.add_paragraph()

    add_heading_custom(doc, '14.2 心魔', 2)
    add_para(doc, '当心魔值超过阈值时触发心魔劫，进入幻境挑战。心魔劫可通过以下行为积累：杀戮（尤其正道修士）、道侣陨落、重大挫折。')
    doc.add_paragraph()

    add_heading_custom(doc, '14.3 心境特质', 2)
    add_para(doc, '达到一定道心后，可领悟心境特质，提供被动加成：坚韧（提升生命值）、冷静（提升战斗闪避）、顿悟（提升悟道点获取）、无畏（提升战斗伤害）。')

    # 十五、渡劫飞升
    add_heading_custom(doc, '十五、渡劫飞升', 1)
    add_heading_custom(doc, '15.1 渡劫条件', 2)
    add_para(doc, '（1）境界达到渡劫期（tribulation_early）；（2）道心值达到要求；（3）完成所有前置任务与试炼。')
    doc.add_paragraph()

    add_heading_custom(doc, '15.2 渡劫流程', 2)
    add_para(doc, '（1）选择渡劫时间（需在灵气充沛的地点）；（2）触发渡劫事件，进入战斗（天劫）；（3）渡劫成功：飞升仙界，游戏胜利；（4）渡劫失败：境界跌落，道心重置，进入轮回。')
    doc.add_paragraph()

    add_heading_custom(doc, '15.3 轮回系统', 2)
    add_para(doc, '渡劫失败后可选择轮回：保留部分悟道点、保留部分心境特质、以新身份重新开局。')

    # 十六、世界事件
    add_heading_custom(doc, '十六、世界事件', 1)
    add_heading_custom(doc, '16.1 事件类型', 2)
    add_para(doc, '世界事件是全局性宏观事件，影响所有玩家：灵气潮汐（提升全服修炼速度）、魔道入侵（增加敌对NPC数量）、兽潮（妖兽大规模迁徙，提升野外危险度）、天灾（地点环境恶化，探索风险增加）。')
    doc.add_paragraph()

    add_heading_custom(doc, '16.2 事件生命周期', 2)
    add_para(doc, '（1）触发：满足条件后随机或定时触发；（2）持续：持续指定月份，期间持续生效；（3）结束：到期后恢复，部分事件有冷却期。')

    # 十七、操作导航
    add_heading_custom(doc, '十七、操作导航', 1)
    add_heading_custom(doc, '17.1 主窗口按钮', 2)
    headers = ['按钮', '功能']
    rows = [
        ['修炼', '打开修炼弹窗，选择修炼方式'],
        ['探索', '打开探索弹窗，选择目的地'],
        ['战斗', '手动发起战斗'],
        ['宗门', '打开宗门弹窗，管理宗门事务'],
        ['家族', '打开家族弹窗，管理家族事务'],
        ['社交', '打开社交弹窗，与NPC交互'],
        ['洞府', '打开洞府弹窗，管理建筑设施'],
        ['炼丹', '打开炼丹弹窗，炼制丹药'],
        ['炼器', '打开炼器弹窗，锻造法器'],
        ['任务', '查看当前任务与历史任务'],
        ['背包', '查看与管理背包物品'],
        ['商店', '打开商店，购买道具'],
        ['擂台', '打开擂台，挑战其他修士'],
        ['领地', '打开领地弹窗，管理领地建设'],
        ['神通', '打开神通弹窗，领悟神通'],
        ['心境', '查看当前心境状态'],
    ]
    add_table(doc, headers, rows)
    doc.add_paragraph()

    add_heading_custom(doc, '17.2 月度推进', 2)
    add_para(doc, '点击「下月」按钮推进时间，触发月度结算：家族产出结算、外交任务进度推进、同盟到期检查、世界BOSS刷新检查、随机事件触发。')

    # 十八、配置说明
    add_heading_custom(doc, '十八、配置说明', 1)
    add_heading_custom(doc, '18.1 配置文件结构', 2)
    headers = ['文件', '作用']
    rows = [
        ['realms.json', '境界配置'],
        ['cultivation_paths.json', '修仙流派配置'],
        ['spiritual_roots.json', '灵根配置'],
        ['items.json', '物品配置'],
        ['sectors.json', '地点配置'],
        ['sects.json', '宗门配置'],
        ['quests.json', '任务配置'],
        ['events.json', '随机事件配置'],
        ['world_events.json', '世界事件配置'],
        ['enemies.json', '敌人配置'],
        ['world_bosses.json', '世界BOSS配置'],
        ['diplomatic_missions.json', '外交任务配置'],
        ['residences.json', '洞府配置'],
        ['factions.json', '阵营配置'],
        ['divine_arts.json', '神通配置'],
        ['mental_state.json', '心境配置'],
        ['territory/', '领地建筑配置目录'],
        ['family/', '家族配置目录'],
    ]
    add_table(doc, headers, rows)
    doc.add_paragraph()

    add_heading_custom(doc, '18.2 扩展新系统', 2)
    add_para(doc, '新增系统建议遵循以下范式：')
    add_para(doc, '（1）在 game/ 下新建 xxx_manager.py，实现核心逻辑；', indent=False)
    add_para(doc, '（2）在 config/ 下新建 xxx.json，实现数据驱动；', indent=False)
    add_para(doc, '（3）在 ui/ 下新建 xxx_dialog.py，实现UI弹窗；', indent=False)
    add_para(doc, '（4）在 engine.py 中注册月度 tick 与入口方法；', indent=False)
    add_para(doc, '（5）在 main_window.py 中添加导航按钮；', indent=False)
    add_para(doc, '（6）在 tests/ 下编写单元测试。', indent=False)

    # 十九、常见问题
    add_heading_custom(doc, '十九、常见问题', 1)
    add_para(doc, 'Q：如何提升境界？', bold=True)
    add_para(doc, 'A：通过修炼（打坐/闭关）积累气血，气血达到阈值后点击突破按钮。')
    doc.add_paragraph()
    add_para(doc, 'Q：如何加入宗门？', bold=True)
    add_para(doc, 'A：点击「宗门」按钮→选择「加入宗门」→选择目标宗门并提交申请。')
    doc.add_paragraph()
    add_para(doc, 'Q：世界BOSS无法挑战？', bold=True)
    add_para(doc, 'A：检查境界是否达到BOSS的min_realm_order要求，且BOSS当前处于活跃状态。')
    doc.add_paragraph()
    add_para(doc, 'Q：宗门战胜率如何提高？', bold=True)
    add_para(doc, 'A：提升境界、增加宗门贡献、提升宗门战参与次数、签订结盟、控制更多灵脉。')
    doc.add_paragraph()
    add_para(doc, 'Q：如何解除外交任务？', bold=True)
    add_para(doc, 'A：点击「宗门」→「外交」标签→选择当前任务→点击「取消任务」。')
    doc.add_paragraph()
    add_para(doc, 'Q：道心值过低怎么办？', bold=True)
    add_para(doc, 'A：避免杀戮行为，进行论道、参悟等提升道心的活动，或购买恢复道具。')

    # 二十、游戏目标
    add_heading_custom(doc, '二十、游戏目标', 1)
    add_para(doc, '（1）短期目标：提升境界，掌握战斗与修炼技能；', indent=False)
    add_para(doc, '（2）中期目标：加入或创建宗门/家族，建立势力；', indent=False)
    add_para(doc, '（3）长期目标：渡劫飞升，成就仙人之位。', indent=False)
    add_para(doc, '游戏支持多周目轮回，每次轮回保留部分悟道点与心境特质，逐渐变强。')

    # 保存
    output_path = r'd:\ziyuanqiufeng\docs\修仙模拟器操作说明书.docx'
    doc.save(output_path)
    print(f'说明书已生成：{output_path}')


if __name__ == '__main__':
    create_manual()

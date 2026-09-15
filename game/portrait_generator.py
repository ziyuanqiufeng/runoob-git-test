# -*- coding: utf-8 -*-
"""主角立绘生成器。

支持根据玩家属性（性别、灵根、流派、境界）构建提示词，
调用 Agnes AI 文生图接口（agnes-image-2.1-flash）生成专属头像；
若接口不可用或未配置 API key，则回退到本地占位图。
"""
import json
import os
import time
import urllib.request
import urllib.error
from PIL import Image, ImageDraw, ImageFont


# Agnes AI 文生图配置（API key 复用 config/ai_config.json，也可由环境变量 AGNES_API_KEY 覆盖）
_AGNES_IMAGE_API = "https://apihub.agnes-ai.com/v1/images/generations"
_AGNES_IMAGE_MODEL = "agnes-image-2.1-flash"

# 默认提示词模板（config/portrait_prompt_template.json 不存在时使用）
_DEFAULT_PROMPT_TEMPLATE = {
    "positive_template": "A {gender_desc} Chinese fantasy cultivator, {path_desc}, {root_desc}, {realm_desc}, {style}, portrait, detailed face, traditional xianxia robe, serene expression, soft lighting",
    "style": "ink wash painting style, ethereal atmosphere",
    "negative_template": "low quality, blurry, deformed hands, extra fingers, modern clothes, western style, cartoon, 3d render",
    "negative_format": " (negative prompt: {negative})",
    "root_template": "{elements} spiritual roots",
    "no_root_desc": "no spiritual roots",
    "gender_desc": {
        "male": "handsome young man",
        "female": "beautiful young woman",
    },
    "path_desc": {
        "fa": "spell cultivator", "ti": "body cultivator", "jian": "sword cultivator",
        "xie": "demonic cultivator", "dan": "alchemy cultivator", "qi": "artifact cultivator",
        "shou": "beast cultivator", "hun": "soul cultivator", "zhen": "formation cultivator",
        "fu": "talisman cultivator",
    },
    "realm_desc": {
        "qi_refining": "Qi Refining", "foundation": "Foundation Establishment",
        "golden_core": "Golden Core", "nascent_soul": "Nascent Soul",
    },
    "element_names": {
        "metal": "metal", "wood": "wood", "water": "water", "fire": "fire", "earth": "earth",
        "thunder": "thunder", "ice": "ice", "wind": "wind",
    },
}

# 属性中文映射（占位图显示用）
_ELEMENT_NAMES = {
    "metal": "金", "wood": "木", "water": "水", "fire": "火", "earth": "土",
    "thunder": "雷", "ice": "冰", "wind": "风",
}

# 境界中文映射
_REALM_NAMES = {
    "qi_refining": "练气期", "foundation": "筑基期",
    "golden_core": "金丹期", "nascent_soul": "元婴期",
}

# 默认立绘资源生成用配色与文本
_REALM_COLORS = {
    "foundation": (46, 204, 113),    # 筑基：绿
    "golden_core": (241, 196, 15),   # 金丹：金
    "nascent_soul": (155, 89, 182),  # 元婴：紫
}

_PATH_COLORS = {
    "fa": (52, 152, 219), "ti": (230, 126, 34), "jian": (241, 196, 15),
    "xie": (155, 89, 182), "dan": (46, 204, 113), "qi": (149, 165, 166),
    "shou": (211, 84, 0), "hun": (142, 68, 173), "zhen": (22, 160, 133),
    "fu": (192, 57, 43),
}

_PATH_NAMES_CN = {
    "fa": "法修", "ti": "体修", "jian": "剑修", "xie": "邪修",
    "dan": "丹修", "qi": "器修", "shou": "御兽修", "hun": "魂修",
    "zhen": "阵修", "fu": "符修",
}

_REALM_NAMES_SHORT = {
    "foundation": "筑基", "golden_core": "金丹", "nascent_soul": "元婴",
}

_GENDER_NAMES_CN = {
    "male": "男", "female": "女",
}


def _get_realm_prefix(realm_id):
    """从境界 ID 提取前缀。"""
    for prefix in _REALM_NAMES:
        if realm_id.startswith(prefix):
            return prefix
    return "qi_refining"


def load_prompt_template(config_dir="config"):
    """加载提示词模板配置；文件不存在或格式错误时返回默认模板。"""
    path = os.path.join(config_dir, "portrait_prompt_template.json")
    if not os.path.exists(path):
        return dict(_DEFAULT_PROMPT_TEMPLATE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            template = json.load(f)
        # 合并默认值，防止用户漏写关键字段
        merged = dict(_DEFAULT_PROMPT_TEMPLATE)
        merged.update(template)
        return merged
    except (json.JSONDecodeError, IOError):
        return dict(_DEFAULT_PROMPT_TEMPLATE)


# 大境界突破后自动切换的高阶头像资源（按境界前缀查找）
_MAJOR_REALM_PORTRAITS = {
    "foundation": "assets/portraits/protagonist_foundation.png",
    "golden_core": "assets/portraits/protagonist_golden_core.png",
    "nascent_soul": "assets/portraits/protagonist_nascent_soul.png",
}

# 更丰富的头像资源匹配规则：按 境界/流派/性别 组合查找
_PORTRAIT_RESOURCE_PATTERNS = [
    # 最精确：境界前缀 + 流派 + 性别
    "assets/portraits/protagonist_{realm_prefix}_{path_id}_{gender}.png",
    # 境界前缀 + 流派
    "assets/portraits/protagonist_{realm_prefix}_{path_id}.png",
    # 境界前缀 + 性别
    "assets/portraits/protagonist_{realm_prefix}_{gender}.png",
    # 仅境界前缀
    "assets/portraits/protagonist_{realm_prefix}.png",
]


def get_major_realm_portrait_path(realm_id):
    """根据境界 ID 返回对应高阶头像路径；文件不存在则返回 None。"""
    prefix = _get_realm_prefix(realm_id)
    path = _MAJOR_REALM_PORTRAITS.get(prefix)
    if path and os.path.exists(path):
        return path
    return None


def find_best_portrait_resource(player):
    """
    根据玩家境界、流派、性别寻找最匹配的头像资源。
    返回找到的文件路径；无匹配则返回默认头像路径。
    """
    realm_prefix = _get_realm_prefix(getattr(player, "realm_id", "qi_refining_1"))
    path_id = getattr(player, "cultivation_path", "fa")
    gender = getattr(player, "gender", "male")

    for pattern in _PORTRAIT_RESOURCE_PATTERNS:
        candidate = pattern.format(
            realm_prefix=realm_prefix,
            path_id=path_id,
            gender=gender,
        )
        if os.path.exists(candidate):
            return candidate

    default = "assets/portraits/protagonist_default.png"
    return default if os.path.exists(default) else None


def build_prompt(player, config_dir="config"):
    """根据玩家属性和模板配置构建文生图英文提示词（含负面提示词）。"""
    template = load_prompt_template(config_dir)

    gender = "male" if getattr(player, "gender", "male") == "male" else "female"
    gender_desc = template["gender_desc"].get(gender, "young cultivator")

    roots = getattr(player, "spiritual_roots", [])
    element_map = template.get("element_names", _DEFAULT_PROMPT_TEMPLATE["element_names"])
    root_names = [element_map.get(r, r) for r in roots]
    if root_names:
        root_template = template.get("root_template", "{elements} spiritual roots")
        root_desc = root_template.format(elements=", ".join(root_names))
    else:
        root_desc = template.get("no_root_desc", "no spiritual roots")

    path_id = getattr(player, "cultivation_path", "fa")
    path_desc = template["path_desc"].get(path_id, "cultivator")

    realm_id = getattr(player, "realm_id", "qi_refining_1")
    realm_prefix = _get_realm_prefix(realm_id)
    realm_desc = template["realm_desc"].get(realm_prefix, "Qi Refining")

    style = template.get("style", "")

    prompt = template["positive_template"].format(
        gender_desc=gender_desc,
        path_desc=path_desc,
        root_desc=root_desc,
        realm_desc=realm_desc,
        style=style,
    )

    # 追加负面提示词（若模板配置了 negative_template 与 negative_format）
    negative_template = template.get("negative_template", "")
    negative_format = template.get("negative_format", "")
    if negative_template and negative_format:
        prompt += negative_format.format(negative=negative_template)

    return prompt


def _generate_placeholder(prompt, output_path, size=512):
    """当文生图接口不可用时，生成本地占位图（带有关键词文字）。"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img = Image.new("RGB", (size, size), color=(45, 55, 72))
    draw = ImageDraw.Draw(img)

    # 背景渐变圆
    draw.ellipse(
        [size // 8, size // 8, size * 7 // 8, size * 7 // 8],
        fill=(70, 85, 110),
        outline=(150, 170, 200),
        width=8,
    )

    # 文字
    try:
        font_large = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", size // 10)
        font_small = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", size // 24)
    except Exception:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text(
        (size // 2, size // 2 - size // 20),
        "AI 立绘",
        fill=(220, 230, 255),
        font=font_large,
        anchor="mm",
    )
    # 简要提示词
    short_prompt = prompt[:60] + "..." if len(prompt) > 60 else prompt
    draw.text(
        (size // 2, size // 2 + size // 12),
        short_prompt,
        fill=(180, 190, 210),
        font=font_small,
        anchor="mm",
    )
    img.save(output_path)
    return output_path


def _load_ai_api_key(config_dir="config"):
    """读取 Agnes API key：环境变量 AGNES_API_KEY 优先，其次 config/ai_config.json。"""
    env_key = os.environ.get("AGNES_API_KEY")
    if env_key:
        return env_key
    try:
        with open(os.path.join(config_dir, "ai_config.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("api_key", "") if isinstance(data, dict) else ""
    except (json.JSONDecodeError, OSError):
        return ""


def _generate_via_agnes(prompt, output_path, timeout=180, config_dir="config", image_size="512x512",
                        max_retries=3, retry_delay=5):
    """调用 Agnes 文生图接口生成并下载图片；任何失败返回 None（由调用方回退占位图）。

    Agnes 服务端队列满会返回 HTTP 503（text image queue is full），
    该情况自动重试，最多 max_retries 次，每次间隔 retry_delay 秒。
    """
    api_key = _load_ai_api_key(config_dir)
    if not api_key:
        return None
    payload = {
        "model": _AGNES_IMAGE_MODEL,
        "prompt": prompt,
        "n": 1,
        "size": image_size,
    }

    body = None
    last_error = "未知错误"
    for attempt in range(max_retries):
        req = urllib.request.Request(
            _AGNES_IMAGE_API,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
            break
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}"
            # 仅队列满（503）值得重试
            if e.code == 503 and attempt < max_retries - 1:
                time.sleep(retry_delay)
                continue
            print(f"Agnes 文生图失败（{last_error}），使用本地占位图。")
            return None
        except Exception as e:
            print(f"Agnes 文生图失败（{e}），使用本地占位图。")
            return None

    if body is None:
        print(f"Agnes 文生图失败（{last_error}），使用本地占位图。")
        return None

    # 解析响应并下载图片
    try:
        parsed = json.loads(body)
        items = parsed.get("data") or []
        url = items[0].get("url") if items else None
        if not url:
            return None
        dl_req = urllib.request.Request(url, headers={"User-Agent": "wendao-changsheng/1.0"})
        with urllib.request.urlopen(dl_req, timeout=max(60, timeout)) as resp2:
            chunk = resp2.read()
        if not chunk:
            return None
        with open(output_path, "wb") as f:
            f.write(chunk)
        # 简单校验是否为有效图片
        with Image.open(output_path) as img:
            img.verify()
        return output_path
    except Exception as e:
        print(f"Agnes 文生图失败（{e}），使用本地占位图。")
        return None


def generate_portrait(player, output_dir="assets/portraits", use_ai=True, timeout=180, config_dir="config"):
    """生成主角头像。

    use_ai 为真时调用 Agnes 文生图接口（model agnes-image-2.1-flash）；
    未配置 API key、接口失败或下载失败时，自动回退到本地占位图。

    Args:
        player: Player 实例
        output_dir: 输出生成图片的目录
        use_ai: 是否尝试调用文生图接口
        timeout: 接口请求超时（秒），Agnes 文生图较慢，建议 >= 180
        config_dir: 提示词模板配置目录

    Returns:
        (成功标志, 图片路径)
    """
    prompt = build_prompt(player, config_dir=config_dir)
    os.makedirs(output_dir, exist_ok=True)
    timestamp = int(time.time())
    output_path = os.path.join(output_dir, f"generated_{timestamp}.png")

    if use_ai:
        result = _generate_via_agnes(
            prompt, output_path, timeout=max(timeout, 180), config_dir=config_dir
        )
        if result:
            return True, output_path

    _generate_placeholder(prompt, output_path)
    return True, output_path


def generate_portrait_from_prompt(prompt, output_dir="assets/portraits", timeout=180, config_dir="config"):
    """按给定英文提示词生成一张立绘（供捏脸等调用方使用）。

    生成成功返回 (True, 图片路径)；失败返回 (False, None)——
    与 generate_portrait 不同，本函数失败时不回退占位图，
    由调用方决定降级策略（捏脸场景需明确区分成功与失败）。
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = int(time.time())
    output_path = os.path.join(output_dir, f"generated_{timestamp}.png")
    result = _generate_via_agnes(
        prompt, output_path, timeout=max(timeout, 180), config_dir=config_dir
    )
    if result:
        return True, output_path
    return False, None


def _draw_gradient_background(draw, size, top_color, bottom_color):
    """用水平色带模拟从上到下的渐变背景。"""
    for y in range(size):
        ratio = y / max(size - 1, 1)
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b))


def generate_default_portrait_resource(realm_prefix, path_id, gender, output_dir="assets/portraits", size=128):
    """按 境界/流派/性别 生成一张默认占位立绘。

    文件名格式：protagonist_{realm_prefix}_{path_id}_{gender}.png，
    与 _PORTRAIT_RESOURCE_PATTERNS 最精确规则对应。
    画面包含渐变背景、人物剪影与装饰圆环。
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = f"protagonist_{realm_prefix}_{path_id}_{gender}.png"
    output_path = os.path.join(output_dir, filename)

    bg_top = _REALM_COLORS.get(realm_prefix, (45, 55, 72))
    # 底部比顶部稍暗，形成渐变
    bg_bottom = tuple(max(0, c - 40) for c in bg_top)
    silhouette_color = _PATH_COLORS.get(path_id, (150, 170, 200))
    silhouette_dark = tuple(max(0, c - 60) for c in silhouette_color)

    img = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(img)

    # 渐变背景
    _draw_gradient_background(draw, size, bg_top, bg_bottom)

    cx, cy = size // 2, size // 2

    # 装饰圆环（体现境界光环）
    ring_margin = size // 12
    draw.ellipse(
        [ring_margin, ring_margin, size - ring_margin, size - ring_margin],
        outline=(255, 255, 255, 128),
        width=max(2, size // 32),
    )

    # 人物剪影：头部圆形
    head_r = size // 7
    head_cy = cy - size // 12
    draw.ellipse(
        [cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r],
        fill=silhouette_color,
    )

    # 人物剪影：肩部/衣袍（用多边形模拟）
    shoulder_y = head_cy + head_r - size // 40
    robe_points = [
        (cx - size // 3, size - size // 12),
        (cx - size // 5, shoulder_y),
        (cx, shoulder_y - size // 20),
        (cx + size // 5, shoulder_y),
        (cx + size // 3, size - size // 12),
    ]
    draw.polygon(robe_points, fill=silhouette_dark)

    # 文字标签（底部）
    try:
        font_large = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", size // 8)
        font_small = ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", size // 12)
    except Exception:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    realm_text = _REALM_NAMES_SHORT.get(realm_prefix, realm_prefix)
    path_text = _PATH_NAMES_CN.get(path_id, path_id)
    gender_text = _GENDER_NAMES_CN.get(gender, gender)

    draw.text(
        (cx, size - size // 8),
        f"{realm_text}·{path_text}",
        fill=(255, 255, 255),
        font=font_large,
        anchor="mm",
        stroke_width=1,
        stroke_fill=(0, 0, 0),
    )
    draw.text(
        (cx, size - size // 18),
        gender_text,
        fill=(230, 230, 230),
        font=font_small,
        anchor="mm",
        stroke_width=1,
        stroke_fill=(0, 0, 0),
    )

    img.save(output_path)
    return output_path


def generate_all_default_portrait_resources(output_dir="assets/portraits", size=128):
    """生成筑基/金丹/元婴 × 十大流派 × 男/女 的完整默认立绘资源包。

    练气期使用已有的 protagonist_default.png，不重复生成。
    """
    paths = []
    for realm_prefix in _REALM_NAMES:
        if realm_prefix == "qi_refining":
            continue
        for path_id in _PATH_NAMES_CN:
            for gender in _GENDER_NAMES_CN:
                path = generate_default_portrait_resource(
                    realm_prefix, path_id, gender, output_dir=output_dir, size=size
                )
                paths.append(path)
    return paths


def ensure_default_portrait_resources(output_dir="assets/portraits", size=128):
    """按需检测并补齐缺失的默认立绘资源。

    用于游戏首次启动或资源被删除后自动修复，避免全部重新生成。
    返回 (本次生成数量, 应存在总数)。
    """
    expected_paths = []
    missing_paths = []
    for realm_prefix in _REALM_NAMES:
        if realm_prefix == "qi_refining":
            continue
        for path_id in _PATH_NAMES_CN:
            for gender in _GENDER_NAMES_CN:
                filename = f"protagonist_{realm_prefix}_{path_id}_{gender}.png"
                path = os.path.join(output_dir, filename)
                expected_paths.append(path)
                if not os.path.exists(path):
                    missing_paths.append((realm_prefix, path_id, gender))

    for realm_prefix, path_id, gender in missing_paths:
        generate_default_portrait_resource(
            realm_prefix, path_id, gender, output_dir=output_dir, size=size
        )

    return len(missing_paths), len(expected_paths)

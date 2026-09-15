import json
import os
import shutil
from datetime import datetime

from game.player import Player
from game.world import World


class SaveManager:
    """存档管理器：支持多存档槽位，同时向后兼容旧的单一 save.json。"""

    # 当前存档格式版本号
    # 每次不兼容的字段变更时递增，并在 _migrate 中添加迁移逻辑
    SAVE_VERSION = 3

    # 多存档存放目录
    DEFAULT_SAVE_DIR = "saves"
    # 旧的单一存档文件路径（向后兼容）
    LEGACY_PATH = "save.json"
    # 旧存档在槽位列表中的特殊标识
    LEGACY_SLOT = "__legacy__"
    # 滚动备份保留份数（每次覆盖保存前，把旧档备份到 backups/）
    BACKUP_KEEP = 5

    def __init__(self, save_path="save.json", save_dir=DEFAULT_SAVE_DIR):
        self.save_path = save_path
        self.save_dir = save_dir
        # 当前活动槽位；None 表示使用 save_path（旧单存档）
        self.active_slot = None

    # ---------------- 路径解析 ----------------
    def _resolve_path(self, slot=None):
        """根据槽位名解析实际文件路径。"""
        slot = slot or self.active_slot
        if slot == self.LEGACY_SLOT:
            return self.save_path
        if slot:
            return os.path.join(self.save_dir, f"{slot}.json")
        return self.save_path

    # ---------------- 保存 ----------------
    def save(self, player, world, slot=None):
        """保存玩家与世界状态到指定槽位（原子写入 + 滚动备份）。

        先写临时文件再 os.replace 原子替换，避免写入中途崩溃/断电导致
        存档损坏；替换前将现有旧档滚动备份到同目录 backups/ 下，
        保留最近 BACKUP_KEEP 份。
        """
        path = self._resolve_path(slot)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        data = {
            "version": self.SAVE_VERSION,
            "player": player.to_dict(),
            "world": world.to_dict(),
            "player_name": getattr(player, "name", "无名散修"),
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        # 滚动备份旧档（备份失败不阻断保存）
        if os.path.exists(path):
            self._backup_existing(path)
        # 原子写：临时文件 + os.replace（同分区替换为原子操作）
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        return path

    def _backup_existing(self, path):
        """将现有存档复制到同目录 backups/ 下，滚动保留最近 BACKUP_KEEP 份。"""
        try:
            backup_dir = os.path.join(os.path.dirname(path) or ".", "backups")
            os.makedirs(backup_dir, exist_ok=True)
            slot = os.path.splitext(os.path.basename(path))[0]
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"{slot}_{stamp}.json")
            shutil.copy2(path, backup_path)
            # 只保留最近 BACKUP_KEEP 份（文件名含时间戳，字典序即时间序）
            prefix = slot + "_"
            backups = sorted(
                f for f in os.listdir(backup_dir)
                if f.startswith(prefix) and f.endswith(".json")
            )
            for old in backups[:-self.BACKUP_KEEP]:
                try:
                    os.remove(os.path.join(backup_dir, old))
                except OSError:
                    pass
        except OSError:
            # 备份失败不应阻断正常保存
            pass

    # ---------------- 读取 ----------------
    def load(self, item_library, config_dir="config", slot=None):
        """读取指定槽位，返回 (player, world)；不存在返回 None。"""
        path = self._resolve_path(slot)
        if not os.path.exists(path):
            return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 先进行版本迁移，确保旧存档字段兼容
        data = self._migrate(data)

        # 缺失核心字段的损坏存档：返回 None，避免 KeyError 崩溃
        player_data = data.get("player")
        world_data = data.get("world")
        if not isinstance(player_data, dict) or not isinstance(world_data, dict):
            return None

        player = Player.from_dict(player_data, item_library)
        world = World.from_dict(world_data, config_dir=config_dir)
        return player, world

    def _migrate(self, data):
        """根据存档版本号执行字段迁移。"""
        version = data.get("version", 0)
        if version < 1:
            # 旧存档没有 version 字段，补充新系统所需的默认值
            player = data.get("player", {})
            player.setdefault("mental_state", 50)
            player.setdefault("heart_demon", 0)
            player.setdefault("mental_state_traits", [])
            player.setdefault("residence", None)
            player.setdefault("companions", [])
            data["player"] = player
            world = data.get("world", {})
            data["world"] = world
        if version < 2:
            # 新增心法、神通、灵植、成就、年表、支线、声望、探索、社交、图鉴等字段
            player = data.get("player", {})
            defaults = {
                "learned_mind_methods": [],
                "equipped_mind_method": None,
                "divine_arts": [],
                "enlightenment_points": 0,
                "awakened_roots": [],
                "mutated_roots": [],
                "farm_plots": [],
                "personal_beasts": [],
                "achievements": [],
                "achievement_progress": {},
                "chronicle": [],
                "active_side_quests": {},
                "completed_side_quests": [],
                "reputation": {},
                "unlocked_secret_realms": [],
                "explored_ruins": {},
                "unlocked_teleports": [],
                "treasure_maps": [],
                "location_event_cooldowns": {},
                "world_boss_kills": [],
                "master_id": None,
                "disciples": [],
                "sworn_brothers": [],
                "revenge_targets": [],
                "killed_npcs": [],
                "bestiary": {},
                "item_compendium": [],
                "skill_compendium": [],
                "letters": [],
                "heard_rumors": [],
                "combat_stats": {
                    "total_battles": 0, "wins": 0, "losses": 0,
                    "total_damage_dealt": 0, "total_damage_taken": 0, "highest_damage": 0,
                },
                "debate_record": {"wins": 0, "losses": 0},
                "reincarnation_count": 0,
                "karma": 0,
                "past_life_talents": [],
            }
            for key, value in defaults.items():
                player.setdefault(key, value)
            data["player"] = player
        if version < 3:
            # 新增委托悬赏字段
            player = data.get("player", {})
            player.setdefault("active_bounties", [])
            data["player"] = player
        # 后续版本在此继续追加 elif 分支
        data["version"] = self.SAVE_VERSION
        return data

    def exists(self, slot=None):
        """判断指定槽位（或默认存档）是否存在。"""
        return os.path.exists(self._resolve_path(slot))

    # ---------------- 槽位管理 ----------------
    def list_slots(self):
        """列出所有可用存档槽位，含向后兼容的旧 save.json。

        返回按保存时间倒序的列表，每项：
            {"name", "path", "player_name", "saved_at", "exists"}
        """
        slots = []
        if os.path.isdir(self.save_dir):
            for fn in sorted(os.listdir(self.save_dir)):
                if fn.endswith(".json"):
                    slot = fn[:-5]
                    meta = self._read_meta(os.path.join(self.save_dir, fn))
                    slots.append({
                        "name": slot,
                        "path": os.path.join(self.save_dir, fn),
                        "player_name": meta.get("player_name", "无名散修"),
                        "saved_at": meta.get("saved_at", ""),
                        "realm_id": meta.get("realm_id"),
                        "exists": True,
                    })
        # 向后兼容：根目录下的旧 save.json
        if os.path.exists(self.save_path):
            if not any(s["path"] == self.save_path for s in slots):
                meta = self._read_meta(self.save_path)
                slots.append({
                    "name": self.LEGACY_SLOT,
                    "path": self.save_path,
                    "player_name": meta.get("player_name", "无名散修"),
                    "saved_at": meta.get("saved_at", ""),
                    "realm_id": meta.get("realm_id"),
                    "exists": True,
                })
        # 按保存时间倒序（空时间排最后）
        slots.sort(key=lambda s: s.get("saved_at") or "", reverse=True)
        return slots

    def _read_meta(self, path):
        """轻量读取存档的道号、境界与保存时间，避免加载整个世界。"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"player_name": "无名散修", "saved_at": "", "realm_id": None}
            player = data.get("player", {})
            name = player.get("name", "无名散修") if isinstance(player, dict) else "无名散修"
            realm_id = player.get("realm_id") if isinstance(player, dict) else None
            return {
                "player_name": name,
                "saved_at": data.get("saved_at", ""),
                "realm_id": realm_id,
            }
        except Exception:
            return {"player_name": "无名散修", "saved_at": "", "realm_id": None}

    def read_slot_detail(self, slot=None):
        """读取指定槽位的详细元信息，供存档预览展示。

        返回 dict：player_name/realm_id/location_id/spirit_stones/age/year/month/
        ending_id/main_story_step/saved_at；不存在或损坏返回 None。
        """
        path = self._resolve_path(slot)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return None
            player = data.get("player", {}) or {}
            world = data.get("world", {}) or {}
            spirit_stones = 0
            for it in player.get("inventory", []) or []:
                if isinstance(it, dict) and it.get("id") == "spirit_stone":
                    spirit_stones += it.get("count", 0)
            return {
                "player_name": player.get("name", "无名散修"),
                "realm_id": player.get("realm_id"),
                "location_id": player.get("location_id"),
                "spirit_stones": spirit_stones,
                "age": player.get("age"),
                "year": world.get("year"),
                "month": world.get("month"),
                "ending_id": player.get("ending_id"),
                "main_story_step": player.get("main_story_step"),
                "saved_at": data.get("saved_at", ""),
            }
        except Exception:
            return None

    def export_slot(self, slot, dest_path):
        """把指定槽位导出为可分享的 zip 包（存档 JSON + 当前立绘）。

        立绘文件若存在则一并打包为 portrait.png；默认图等本机资源不打包。
        成功返回导出的存档数据 dict；槽位不存在/读取失败返回 None。
        """
        import zipfile

        path = self._resolve_path(slot)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "player" not in data:
                return None
            os.makedirs(os.path.dirname(os.path.abspath(dest_path)) or ".", exist_ok=True)
            with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("save.json", json.dumps(data, ensure_ascii=False, indent=2))
                portrait = (data.get("player") or {}).get("portrait")
                if portrait and os.path.exists(portrait):
                    zf.write(portrait, "portrait.png")
            return data
        except (json.JSONDecodeError, OSError):
            return None

    def import_slot(self, zip_path, base_name=None):
        """从 zip 包导入存档为新槽位。

        zip 需含 save.json（player/world 结构）；若包含 portrait.png 则将其
       释放到 assets/portraits/imported_<ts>.png 并修复存档内的立绘路径。
        槽位名默认取 base_name（缺省用 zip 文件名），冲突时自动加序号。
        成功返回槽位名；包无效返回 None。
        """
        import time
        import zipfile

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                if "save.json" not in names:
                    return None
                data = json.loads(zf.read("save.json").decode("utf-8"))
                if not isinstance(data, dict) or "player" not in data:
                    return None
                if "portrait.png" in names:
                    portrait_dir = os.path.join("assets", "portraits")
                    os.makedirs(portrait_dir, exist_ok=True)
                    dest = os.path.join(
                        portrait_dir, f"imported_{int(time.time())}.png"
                    )
                    with zf.open("portrait.png") as src, open(dest, "wb") as out:
                        out.write(src.read())
                    if isinstance(data.get("player"), dict):
                        data["player"]["portrait"] = dest.replace("\\", "/")
        except (zipfile.BadZipFile, json.JSONDecodeError, KeyError, OSError):
            return None

        if not base_name:
            base_name = os.path.splitext(os.path.basename(zip_path))[0]
        slot = self.allocate_slot(base_name)
        slot_path = self._resolve_path(slot)
        os.makedirs(os.path.dirname(slot_path) or ".", exist_ok=True)
        with open(slot_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return slot

    def allocate_slot(self, base_name):
        """基于道号/名称生成唯一槽位名（冲突时追加序号）。"""
        base = (base_name or "修仙存档").strip() or "修仙存档"
        # 清理非法文件名字符
        safe = "".join(c for c in base if c not in '\\/:*?"<>|').strip()
        if not safe:
            safe = "修仙存档"
        existing = set()
        if os.path.isdir(self.save_dir):
            existing |= {fn[:-5] for fn in os.listdir(self.save_dir) if fn.endswith(".json")}
        slot = safe
        i = 1
        while slot in existing:
            slot = f"{safe}_{i}"
            i += 1
        return slot

    def delete_slot(self, slot):
        """删除指定槽位（LEGACY_SLOT 即删除旧 save.json）。

        返回 True 表示删除成功；文件不存在或删除失败（被占用/权限不足等）
        均返回 False，不抛出异常，由调用方给出友好提示。
        """
        path = self._resolve_path(slot)
        if not os.path.exists(path):
            return False
        try:
            os.remove(path)
            return True
        except OSError:
            return False

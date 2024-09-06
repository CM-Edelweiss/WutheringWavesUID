from pathlib import Path
from typing import Union

from PIL import Image, ImageDraw
from pydantic import BaseModel

from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img
from gsuid_core.utils.image.image_tools import crop_center_img
from ..utils.api.model import AccountBaseInfo, RoleDetailData, WeaponData
from ..utils.calculate import calc_phantom_score, get_total_score_bg
from ..utils.char_info_utils import get_all_role_detail_info
from ..utils.error_reply import WAVES_CODE_102
from ..utils.fonts.waves_fonts import waves_font_30, waves_font_25, waves_font_26, waves_font_42, waves_font_15, \
    waves_font_22, waves_font_40, waves_font_24
from ..utils.hint import error_reply
from ..utils.image import get_waves_bg, get_event_avatar, add_footer, GOLD, GREY, get_attribute, get_square_avatar, \
    get_square_weapon, SPECIAL_GOLD
from ..utils.resource.download_file import get_skill_img
from ..utils.waves_api import waves_api
from ..utils.weapon_detail import get_breach
from ..wutheringwaves_charinfo import refresh_char

TEXT_PATH = Path(__file__).parent / 'texture2d'


class WavesCharRank(BaseModel):
    roleId: int  # 角色id
    roleName: str  # 角色名字
    starLevel: int  # 角色星级
    level: int  # 角色等级
    chain: int  # 命座
    score: float  # 角色评分
    score_bg: str  # 评分背景


async def draw_char_list_img(uid: str, ev: Event) -> Union[str, bytes]:
    ck = await waves_api.get_ck(uid)
    if not ck:
        return error_reply(WAVES_CODE_102)
    # 账户数据
    succ, account_info = await waves_api.get_base_info(uid, ck)
    if not succ:
        return account_info
    account_info = AccountBaseInfo(**account_info)

    await refresh_char(uid, ck=ck)

    # 根据面板数据获取详细信息
    all_role_detail = await get_all_role_detail_info(uid)
    if not all_role_detail:
        return '角色信息获取失败，请检查UID是否正确'

    waves_char_rank = []
    for char_name, role_detail in all_role_detail.items():
        phantom_score = 0
        if role_detail.phantomData and role_detail.phantomData.equipPhantomList:
            equipPhantomList = role_detail.phantomData.equipPhantomList
            for i, _phantom in enumerate(equipPhantomList):
                if _phantom and _phantom.phantomProp:
                    props = []
                    if _phantom.mainProps:
                        props.extend(_phantom.mainProps)
                    if _phantom.subProps:
                        props.extend(_phantom.subProps)
                    _score, _bg = calc_phantom_score(char_name, props, _phantom.cost)
                    phantom_score += _score

        wcr = WavesCharRank(**{
            "roleId": role_detail.role.roleId,
            "roleName": role_detail.role.roleName,
            "starLevel": role_detail.role.starLevel,
            "level": role_detail.level,
            "chain": role_detail.get_chain_num(),
            "score": phantom_score,
            "score_bg": get_total_score_bg(char_name, phantom_score)
        })
        waves_char_rank.append(wcr)

    waves_char_rank.sort(key=lambda i: (i.score, i.starLevel, i.level, i.chain, i.roleId), reverse=True)

    avatar_h = 230
    info_bg_h = 260
    bar_star_h = 110
    h = avatar_h + info_bg_h + len(waves_char_rank) * bar_star_h + 80
    card_img = get_waves_bg(1000, h, 'bg3')

    # 基础信息 名字 特征码
    base_info_bg = Image.open(TEXT_PATH / 'base_info_bg.png')
    base_info_draw = ImageDraw.Draw(base_info_bg)
    base_info_draw.text((275, 120), f'{account_info.name[:7]}', 'white', waves_font_30, 'lm')
    base_info_draw.text((226, 173), f'特征码:  {account_info.id}', GOLD, waves_font_25, 'lm')
    card_img.paste(base_info_bg, (15, 20), base_info_bg)

    # 头像 头像环
    avatar = await draw_pic_with_ring(ev)
    avatar_ring = Image.open(TEXT_PATH / 'avatar_ring.png')
    card_img.paste(avatar, (25, 70), avatar)
    avatar_ring = avatar_ring.resize((180, 180))
    card_img.paste(avatar_ring, (35, 80), avatar_ring)

    # 账号基本信息，由于可能会没有，放在一起
    if account_info.is_full:
        title_bar = Image.open(TEXT_PATH / 'title_bar.png')
        title_bar_draw = ImageDraw.Draw(title_bar)
        title_bar_draw.text((660, 125), '账号等级', GREY, waves_font_26, 'mm')
        title_bar_draw.text((660, 78), f'Lv.{account_info.level}', 'white', waves_font_42, 'mm')

        title_bar_draw.text((810, 125), '世界等级', GREY, waves_font_26, 'mm')
        title_bar_draw.text((810, 78), f'Lv.{account_info.worldLevel}', 'white', waves_font_42, 'mm')
        card_img.paste(title_bar, (-20, 70), title_bar)

    # 简单描述
    info_bg = Image.open(TEXT_PATH / 'info_bg.png')
    card_img.paste(info_bg, (0, avatar_h), info_bg)

    for index, _rank in enumerate(waves_char_rank):
        role_detail: RoleDetailData = all_role_detail[_rank.roleName]
        bar_star = Image.open(TEXT_PATH / f'bar_{_rank.starLevel}star.png')
        bar_star_draw = ImageDraw.Draw(bar_star)
        role_avatar = await draw_pic(role_detail.role.roleId)

        bar_star.paste(role_avatar, (60, 0), role_avatar)

        role_attribute = await get_attribute(role_detail.role.attributeName, is_simple=True)
        role_attribute = role_attribute.resize((40, 40)).convert('RGBA')
        bar_star.alpha_composite(role_attribute, (170, 20))
        bar_star_draw.text((180, 83), f'Lv.{_rank.level}', GREY, waves_font_22, 'mm')

        # 评分
        score_bg = Image.open(TEXT_PATH / f'score_{_rank.score_bg}.png')
        bar_star.alpha_composite(score_bg, (200, 2))

        # 技能
        skill_img_temp = Image.new('RGBA', (1500, 300))
        for i, _skill in enumerate(role_detail.skillList):
            temp = Image.new('RGBA', (120, 140))
            skill_bg = Image.open(TEXT_PATH / 'skill_bg.png')
            temp.alpha_composite(skill_bg)

            skill_img = await get_skill_img(role_detail.role.roleId, _skill.skill.name, _skill.skill.iconUrl)
            skill_img = skill_img.resize((70, 70))
            temp.alpha_composite(skill_img, (25, 25))

            temp_draw = ImageDraw.Draw(temp)
            temp_draw.text((62, 115), f'{_skill.skill.type}', 'white', waves_font_15, 'mm')
            temp_draw.text((62, 132), f'Lv.{_skill.level}', 'white', waves_font_15, 'mm')

            _x = i * 70
            skill_img_temp.alpha_composite(temp.resize((70, 82)), dest=(_x, 0))
        bar_star.alpha_composite(skill_img_temp, dest=(300, 10))

        # 武器
        weapon_bg_temp = Image.new('RGBA', (600, 300))

        weaponData: WeaponData = role_detail.weaponData
        weapon_icon = await get_square_weapon(weaponData.weapon.weaponId)
        weapon_icon = crop_center_img(weapon_icon, 110, 110)
        weapon_icon_bg = get_weapon_icon_bg(weaponData.weapon.weaponStarLevel)
        weapon_icon_bg.paste(weapon_icon, (10, 20), weapon_icon)

        weapon_bg_temp_draw = ImageDraw.Draw(weapon_bg_temp)
        weapon_bg_temp_draw.text((200, 30), f'{weaponData.weapon.weaponName}', SPECIAL_GOLD, waves_font_40, 'lm')
        weapon_bg_temp_draw.text((203, 75), f'Lv.{weaponData.level}/90', 'white', waves_font_30, 'lm')

        _x = 220 + 43 * len(weaponData.weapon.weaponName)
        _y = 37
        weapon_bg_temp_draw.rounded_rectangle([_x - 15, _y - 15, _x + 50, _y + 15], radius=7,
                                              fill=(128, 138, 135, int(0.8 * 255)))
        weapon_bg_temp_draw.text((_x, _y), f'精{weaponData.resonLevel}', 'white',
                                 waves_font_24, 'lm')

        weapon_breach = get_breach(weaponData.breach, weaponData.level)
        for i in range(0, weapon_breach):
            promote_icon = Image.open(TEXT_PATH / 'promote_icon.png')
            weapon_bg_temp.alpha_composite(promote_icon, dest=(200 + 40 * i, 100))

        weapon_bg_temp.alpha_composite(weapon_icon_bg, dest=(45, 0))

        bar_star.alpha_composite(weapon_bg_temp.resize((260, 130)), dest=(700, 25))

        card_img.paste(bar_star, (0, avatar_h + info_bg_h + index * bar_star_h), bar_star)

    card_img = add_footer(card_img)
    card_img = await convert_img(card_img)
    return card_img


async def draw_pic_with_ring(ev: Event):
    pic = await get_event_avatar(ev)

    mask_pic = Image.open(TEXT_PATH / 'avatar_mask.png')
    img = Image.new('RGBA', (180, 180))
    mask = mask_pic.resize((160, 160))
    resize_pic = crop_center_img(pic, 160, 160)
    img.paste(resize_pic, (20, 20), mask)

    return img


async def draw_pic(roleId):
    pic = await get_square_avatar(roleId)
    pic_temp = Image.new('RGBA', pic.size)
    pic_temp.paste(pic.resize((160, 160)), (10, 10))

    mask_pic = Image.open(TEXT_PATH / 'avatar_mask.png')
    mask_pic_temp = Image.new('RGBA', mask_pic.size)
    mask_pic_temp.paste(mask_pic, (-20, -45), mask_pic)

    img = Image.new('RGBA', (180, 180))
    mask_pic_temp = mask_pic_temp.resize((160, 160))
    resize_pic = pic_temp.resize((160, 160))
    img.paste(resize_pic, (0, 0), mask_pic_temp)

    return img


def get_weapon_icon_bg(star: int = 3) -> Image.Image:
    if star < 3:
        star = 3
    bg_path = TEXT_PATH / f'weapon_icon_bg_{star}.png'
    bg_img = Image.open(bg_path)
    return bg_img

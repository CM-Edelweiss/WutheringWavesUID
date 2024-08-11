import re

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV
from .draw_gachalogs import draw_card
from .get_gachalogs import save_gachalogs
from ..utils.database.models import WavesBind, WavesUser
from ..utils.error_reply import WAVES_CODE_103, ERROR_CODE, WAVES_CODE_105
from ..wutheringwaves_config import PREFIX

sv_gacha_log = SV('waves抽卡记录')
sv_get_gachalog_by_link = SV('waves导入抽卡链接', area='DIRECT')


@sv_get_gachalog_by_link.on_command(f'{PREFIX}导入抽卡链接')
async def get_gacha_log_by_link(bot: Bot, ev: Event):
    await bot.logger.info(f'开始执行[{PREFIX}导入抽卡链接]')

    # 没有uid 就别导了吧
    uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
    if not uid:
        return await bot.send(ERROR_CODE[WAVES_CODE_103])

    raw = ev.text.strip()
    text = re.sub(r'["\n\t ]+', '', raw)
    if "https://" in text:
        # 使用正则表达式匹配参数
        match_record_id = re.search(r'record_id=([a-zA-Z0-9]+)', text)
        match_player_id = re.search(r'player_id=(\d+)', text)
    elif "{" in text:
        match_record_id = re.search(r'recordId:([a-zA-Z0-9]+)', text)
        match_player_id = re.search(r'playerId:(\d+)', text)
    else:
        match_record_id = re.search(r'recordId=([a-zA-Z0-9]+)', text)
        match_player_id = re.search(r'playerId=(\d+)', text)

    # 提取参数值
    record_id = match_record_id.group(1) if match_record_id else None
    player_id = match_player_id.group(1) if match_player_id else None

    if not record_id:
        return await bot.send('请给出正确的抽卡记录链接')

    if player_id and player_id != uid:
        logger.info(f'[鸣潮]用户：{ev.user_id} 当前抽卡链接与当前绑定的UID不匹配 player_id:{player_id} uid:{uid}')
        return await bot.send('当前抽卡链接与当前绑定的UID不匹配')

    is_force = False
    if ev.command.startswith('强制'):
        await bot.logger.info('[WARNING]本次为强制刷新')
        is_force = True
    await bot.send(
        f'UID{uid}开始执行[刷新抽卡记录],需要一定时间...请勿重复触发!'
    )
    im = await save_gachalogs(ev, uid, record_id, is_force)
    return await bot.send(im)


@sv_gacha_log.on_fullmatch(
    (f"{PREFIX}刷新抽卡记录", f'{PREFIX}更新抽卡记录'),
)
async def send_refresh_gachalog_msg(bot: Bot, ev: Event):
    uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
    if not uid:
        return await bot.send(ERROR_CODE[WAVES_CODE_103])

    user = await WavesUser.get_user_by_attr(ev.user_id, ev.bot_id, 'uid', uid)
    if not user or not user.record_id:
        return await bot.send(ERROR_CODE[WAVES_CODE_105])

    await bot.send(f"开始刷新{uid}抽卡记录，需要一定时间，请勿重复执行.....")
    im = await save_gachalogs(ev, uid, user.record_id)
    return await bot.send(im)


@sv_gacha_log.on_fullmatch(f'{PREFIX}抽卡记录')
async def send_gacha_log_card_info(bot: Bot, ev: Event):
    await bot.logger.info(f'[鸣潮]开始执行 {PREFIX}抽卡记录')
    uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
    if not uid:
        return await bot.send(ERROR_CODE[WAVES_CODE_103])

    user = await WavesUser.get_user_by_attr(ev.user_id, ev.bot_id, 'uid', uid)
    if not user or not user.record_id:
        return await bot.send(ERROR_CODE[WAVES_CODE_105])

    im = await draw_card(user, ev)
    await bot.send(im)
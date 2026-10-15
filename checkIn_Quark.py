'''
本脚本实现夸克网盘每日自动签到，签到可获得网盘容量奖励。
不需要账号密码登录：复用手机端抓包链接里的 kps/sign/vcode 三个鉴权参数，
脚本携带它们请求官方的查询(info)和签到(sign)接口，奖励由服务端自动入账。
参数有时效，失效后重新抓包更新配置即可；支持多账号，每个账号单独抓取一条链接。

Docker版说明：
    账号配置通过环境变量 COOKIE_QUARK 注入（docker-compose.yml）
    网络请求带自动重试，防止定时执行时偶发断网漏签。

抓包流程：
    【手机端】
    ①打开抓包软件，手机端访问网盘签到界面，执行签到
    ②找到url为 https://drive-member.quark.cn/1/clouddrive/capacity/growth 的请求信息
    ③复制整段url，该链接后面必须要有的参数: kps sign vcode，粘贴到环境变量
    环境变量名为 COOKIE_QUARK 多账户用 回车 或 && 分开
    user字段是用户名 (可是随意填写，多账户方便区分)
    例如: user=张三; url=https://drive-member.quark.cn/1/clouddrive/capacity/growth?xxxxxx=xxxxxx&kps=abcdefg&sign=hijklmn&vcode=111111111;
    旧版环境变量格式也兼容，例如: user=张三; kps=abcdefg; sign=hijklmn; vcode=111111111;

Author: Zh
源码改编自 [@BNDou](https://github.com/BNDou/Auto_Check_In) 的脚本
'''


import os
import re
import sys
import time
import requests
from datetime import datetime

# 重试配置：网络抖动时自动重试，避免偶尔断网漏签
MAX_RETRIES = 3       # 最大重试次数
RETRY_DELAY = 60      # 重试间隔（秒）

##############################################################################
# 用户配置说明
# 本脚本支持多用户自动签到，只需在 COOKIE_QUARK 环境变量中配置账号信息
# （在 docker-compose.yml 的 environment 中设置）
#
# 配置格式：每个账号一行 user=用户名; url=签到链接;
# 多用户用 回车 或 && 分隔，例如：
#   user=张三; url=https://drive-member.quark.cn/1/clouddrive/capacity/growth/info?kps=xxx&sign=xxx&vcode=xxx;
#   user=李四; url=https://drive-member.quark.cn/1/clouddrive/capacity/growth/info?kps=yyy&sign=yyy&vcode=yyy;
#
# 注意事项：
# 1. url 只要包含 kps、sign、vcode 三个参数即可，域名和其余参数会被脚本丢弃
# 2. 用户名可以是任意字符，用于区分不同账号
# 3. 参数有时效，提示"获取成长信息失败"时重新抓包更新 compose 配置并重建容器
##############################################################################


# 获取环境变量
def get_env():
    '''
    从环境变量中获取夸克账号配置

    支持多用户配置，格式说明：
    - 单用户：user=用户名; url=签到链接;
    - 多用户：使用 \n 或 && 分隔多个账号

    返回：账号配置列表
    '''
    # 判断 COOKIE_QUARK是否存在于环境变量
    if "COOKIE_QUARK" in os.environ:
        # 读取系统变量以 \n 或 && 分割变量（支持多用户）
        cookie_list = re.split('\n|&&', os.environ.get('COOKIE_QUARK'))
        # 过滤空字符串
        cookie_list = [cookie.strip() for cookie in cookie_list if cookie.strip()]
    else:
        print('错误: 未设置 COOKIE_QUARK 环境变量，请在 docker-compose.yml 中配置后重新部署')
        # 脚本退出
        sys.exit(0)

    return cookie_list


class Quark:
    '''
    Quark类封装了签到、查询签到状态的方法（奖励由服务端自动入账，无领取接口）
    '''
    def __init__(self, user_data):
        '''
        初始化方法
        :param user_data: 用户信息，用于后续的请求
        '''
        self.param = user_data

    def convert_bytes(self, b):
        '''
        将字节转换为 MB GB TB
        :param b: 字节数
        :return: 返回 MB GB TB
        '''
        units = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = 0
        while b >= 1024 and i < len(units) - 1:
            b /= 1024
            i += 1
        return f"{b:.2f} {units[i]}"

    def _api_get(self, url, params):
        '''带重试的 GET 请求'''
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(url=url, params=params, timeout=15).json()
                return resp
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    print(f"  网络异常，{RETRY_DELAY}秒后重试 ({attempt + 1}/{MAX_RETRIES}): {e}")
                    time.sleep(RETRY_DELAY)
                else:
                    print(f"  网络请求失败，已重试{MAX_RETRIES}次: {e}")
                    return None

    def _api_post(self, url, params, data):
        '''带重试的 POST 请求'''
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(url=url, json=data, params=params, timeout=15).json()
                return resp
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    print(f"  网络异常，{RETRY_DELAY}秒后重试 ({attempt + 1}/{MAX_RETRIES}): {e}")
                    time.sleep(RETRY_DELAY)
                else:
                    print(f"  网络请求失败，已重试{MAX_RETRIES}次: {e}")
                    return None

    def get_growth_info(self):
        '''
        获取用户当前的签到信息
        :return: 返回一个字典，包含用户当前的签到信息
        '''
        url = "https://drive-member.quark.cn/1/clouddrive/capacity/growth/info"
        querystring = {
            "pr": "ucpro",
            "fr": "android",
            "kps": self.param.get('kps'),
            "sign": self.param.get('sign'),
            "vcode": self.param.get('vcode')
        }
        response = self._api_get(url, querystring)
        if response and response.get("data"):
            return response["data"]
        return False

    def get_growth_sign(self):
        '''
        执行签到
        :return: (成功标志, 奖励或错误信息)
        '''
        url = "https://drive-member.quark.cn/1/clouddrive/capacity/growth/sign"
        querystring = {
            "pr": "ucpro",
            "fr": "android",
            "kps": self.param.get('kps'),
            "sign": self.param.get('sign'),
            "vcode": self.param.get('vcode')
        }
        data = {"sign_cyclic": True}
        response = self._api_post(url, querystring, data)
        if response and response.get("data"):
            return True, response["data"]["sign_daily_reward"]
        elif response:
            return False, response.get("message", "未知错误")
        return False, "网络连接失败"

    def do_sign(self):
        '''
        执行签到任务
        :return: 返回一个字符串，包含签到结果
        '''
        growth_info = self.get_growth_info()
        if not growth_info:
            return (
                f"  {self.param.get('user')}\n"
                f"  获取成长信息失败: kps/sign/vcode 可能已过期，请重新抓包更新\n"
            )

        cap_sign = growth_info["cap_sign"]
        # 签到前拿到的累计天数不含今天
        total_days = growth_info.get('cap_growth', {}).get('cur_total_sign_day', 0)
        sign_reward = growth_info['cap_composition'].get('sign_reward', 0)
        log = (
            f"  {self.param.get('user')} ({'88VIP' if growth_info['88VIP'] else '普通用户'})\n"
            f"  账号信息: 总容量 {self.convert_bytes(growth_info['total_capacity'])}"
            f" | 签到累计容量 {self.convert_bytes(sign_reward)}\n"
        )
        if cap_sign["sign_daily"]:
            # 今日已签到，无需再请求，容量与上面一致
            log += (
                f"  今日已签到 +{self.convert_bytes(cap_sign['sign_daily_reward'])}"
                f" | 连签进度({cap_sign['sign_progress']}/{cap_sign['sign_target']})"
                f" | 累计签到{total_days}天\n"
                f"  当前总容量 {self.convert_bytes(growth_info['total_capacity'])}"
                f" | 签到累计容量 {self.convert_bytes(sign_reward)}\n"
            )
        else:
            sign, sign_return = self.get_growth_sign()
            if not sign:
                return log + f"  签到失败: {sign_return}\n"
            log += (
                f"  签到成功 +{self.convert_bytes(sign_return)}"
                f" | 连签进度({cap_sign['sign_progress'] + 1}/{cap_sign['sign_target']})"
                f" | 累计签到{total_days + 1}天\n"
            )
            # 重新获取，显示签到入账后的最新容量
            updated_info = self.get_growth_info() or growth_info
            log += (
                f"  当前总容量 {self.convert_bytes(updated_info['total_capacity'])}"
                f" | 签到累计容量 {self.convert_bytes(updated_info['cap_composition'].get('sign_reward', 0))}\n"
            )
        return log


def extract_params(url):
    '''
    从URL中提取所需的参数
    :param url: 包含参数的URL
    :return: 返回一个字典，包含所需的参数
    '''
    # 提取URL中的查询参数部分（?后面的内容）
    query_start = url.find('?')
    query_string = url[query_start + 1:] if query_start != -1 else ''

    # 解析查询参数
    params = {}
    for param in query_string.split('&'):
        if '=' in param:
            key, value = param.split('=', 1)
            params[key] = value

    # 返回所需的参数
    return {
        'kps': params.get('kps', ''),
        'sign': params.get('sign', ''),
        'vcode': params.get('vcode', '')
    }


def get_checkin_mode():
    '''
    根据命令行参数判断签到类型
    :return: 签到类型标签
    '''
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == 'scheduled':
            return '定时签到'
        elif arg == 'startup':
            return '启动签到'
    return '手动签到'


def main():
    '''
    主函数
    '''
    msg = ""
    global cookie_quark
    cookie_quark = get_env()

    # 分界线（带时间戳和签到类型，便于区分每次签到）
    mode = get_checkin_mode()
    line = "=" * 70
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg += f"{line}\n  夸克网盘{mode}  {now}\n{line}\n"

    for i, cookie in enumerate(cookie_quark, start=1):
        # 获取user_data参数
        user_data = {}  # 用户信息
        for a in cookie.replace(" ", "").split(';'):
            if not a == '':
                user_data.update({a[0:a.index('=')]: a[a.index('=') + 1:]})

        # 从url参数中提取kps/sign/vcode
        if 'url' in user_data:
            user_data.update(extract_params(user_data['url']))

        msg += f"[账号{i}]\n"
        msg += Quark(user_data).do_sign() + "\n"

    msg += f"{line}\n"
    print(msg)
    return msg[:-1]


if __name__ == "__main__":
    main()

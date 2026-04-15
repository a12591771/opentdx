from datetime import date, datetime
import struct
from typing import override

from opentdx.parser.baseParser import BaseParser, register_parser
from opentdx.utils.log import log


@register_parser(0x2) # Login后
class ExchangeAnnouncement(BaseParser):
    @override
    def deserialize(self, data):
        v, = struct.unpack('<B', data[:1])
        return {
            'v': v,
            'content': data[1:].decode('gbk')
        }

@register_parser(0x4) # 心跳包15秒
class HeartBeat(BaseParser):
    @override
    def deserialize(self, data):
        (_, date) = struct.unpack('<6sI', data[:10])
        return date

@register_parser(0xa) # 服务商公告
class Announcement(BaseParser):
    def __init__(self):
        self.body = struct.pack('<54x')
    @override
    def deserialize(self, data):
        had, = struct.unpack('<B', data[:1])
        if had == 0x01:
            (expire_date, title_len, author_len, conntent_len) = struct.unpack('<IHHH', data[1:11])
            (title, author, content) = struct.unpack(f'<{title_len}s{author_len}s{conntent_len}s', data[11:11+title_len+author_len+conntent_len])
            expire_date = date(expire_date // 10000, expire_date % 10000 // 100, expire_date % 100)
            return {
                'expire_date': expire_date,
                'title': title.decode('gbk'),
                'author': author.decode('gbk'),
                'content': content.decode('gbk')
            }
        else:
            return None


@register_parser(0xb)#TODO: 未完成
class TodoB(BaseParser):
    def __init__(self):
        self.body = bytearray.fromhex('' \
        'e53878ee8bd8dbb8'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '901a1266bd9f62d9'\
        '6810db2bdf3e50a1'\
        '9e93269128ddf91f'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '27fd50435e32ca0d'\
        '8872a27c327343f1'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '749933ae27700357'\
        '7c8810a76fd73daf')

    @override
    def deserialize(self, data):
        return data

@register_parser(0xd)
class Login(BaseParser):
    def __init__(self):
        self.body = struct.pack('<B', 1)

    @override
    def deserialize(self, data):
        (_, year, day, month, minute, hour, _, second, \
        unknown1, unknown2, unknown3, \
        date, a1, b1, date2, a2, b2, \
        unknown4, unknown5, unknown6, \
        server_name, web_site, unknown7, category) = struct.unpack('<BHBBBBBB16s16sBIHHIHHHH5s22s64s6s30s', data)

        info = {
            "datetime": datetime(year, month, day, hour, minute, second).strftime('%Y-%m-%d %H:%M:%S'),
            "server_name": server_name.decode('gbk').replace('\x00', ''),
            "web_site": web_site.decode('gbk').replace('\x00', ''),
            "category": category.decode('gbk').replace('\x00', ''),
        }
        return info

@register_parser(0x15)
class Info(BaseParser):
    def __init__(self):
        self.body = bytearray()

    @override
    def deserialize(self, data):
        # Region: 可能是大区？， 东区100：上海、深圳  北区90：北京  南区80：上海、广州 中区25：武汉  西区56：成都
        maybe_delay, unknown_aH, _, unknown_bH, info, unknown10s, content, server_sign, date1, unknown_cH, unknown_dH, unknown6s, \
            _, Region, unknown_fH, _, maybe_switch, \
                date_now, time_now, date3, date4, date5, date6, date7, z  = struct.unpack('<IH8sH55s10s255s20sIHH6s19sHHHHIIIIIIIH', data[:427])

        log.debug("server info raw: delay=%s, region=%s", maybe_delay, Region)
        time_now = datetime(date_now // 10000, date_now % 10000 // 100, date_now % 100, time_now // 10000, time_now % 10000 // 100, time_now % 100)
        return {
            "delay": maybe_delay,
            "info": info.decode('gbk').replace('\x00', ''),
            "content": content.decode('gbk').replace('\x00', ''),
            "server_sign": server_sign.decode('gbk').replace('\x00', ''),
            "time_now": time_now.strftime('%Y-%m-%d %H:%M:%S'),
            "unknown1": [unknown_aH, unknown_bH, unknown10s.hex()],
            "unknown2": [unknown_cH, unknown_dH, unknown6s.hex()],
            "unknown3": [Region, unknown_fH, maybe_switch],
        }

@register_parser(0xfde)
class TodoFDE(BaseParser):
    @override
    def deserialize(self, data):
        (u1, u2, u3, u4) = struct.unpack('<IH165s16s', data[:187])
        return {
            "unknown": [u1, u2, u4.hex()]
        }

@register_parser(0xfdb)
class UpgradeTip(BaseParser):
    def __init__(self):
        self.body = bytearray(struct.pack('<8s', 'tdxlevel'.encode('gbk')))
        self.body.extend(bytearray().fromhex('00 00 00 a4 70 f5 40 07 00 00 00 00 00 00 00 00 00 00 00 00 00 05'))

    @override
    def deserialize(self, data):
        (had, unknow2, tips, unknow5, link) = struct.unpack('<BH50s5s120s', data[:178])
        tips = tips.decode('gbk').replace('\x00', '')
        link = link.decode('gbk').replace('\x00', '')
        msg = data[178:].decode('gbk', 'ignore').replace('\x00', '') if had == 0x01 else None
        return {
            "had": had,
            "unknown": [unknow2, unknow5.hex()],
            "tips": tips,
            "link": link,
            "msg": msg
        }

@register_parser(0x264b)
class f264b(BaseParser):
    def __init__(self):
        self.body = struct.pack('BB', 0, 100)

@register_parser(0x26ac)
class f26ac(BaseParser):
    def __init__(self):
        self.body = struct.pack('<BBH24xBBBB6sHHH', 0, 100, 1234, 192, 168, 0, 1, 'macadd'.encode('gbk'), 40, 1864, 0)

@register_parser(0x26ad)
class f26ad(BaseParser):
    def __init__(self):
        # 'OPr2IHZ5r3luK9Ka'
        # 'QuLKjb7430URZYtI'
        # 'ebwTfYqmoQHTx2G2'
        self.body = struct.pack('<BB16s24xBBBB6s16sHHHHB17sBB', 0, 100, 'TDXW'.encode('gbk'), 192, 168, 0, 1, 'macadd'.encode('gbk'), 'TDXW'.encode('gbk'), 40, 1864, 0, 1234, 1, 'OPr2IHZ5r3luK9Ka'.encode('gbk'), 2, 1)

# > ae26 0064 59f6aec4f951e48c8c6a649f38b763385c6a2c94ad01c51f5c6a2c94ad01c51f5c6a2c94ad01c51f5c6a2c94ad01c51f5c6a2c94ad01c51f5c6a2c94ad01c51faba98d80b1364335a4d90b527b9572fc57ad0899b02c0e1e75b541d0adf6e6b491a0e869e6ca3d93fe00ca61488b1e80a3f7a04fb524be6bfb8f0cd0148b3c919f2db921d790dadb959a9be45a11b8465c6a2c94ad01c51f5c6a2c94ad01c51f5c6a2c94ad01c51f5c6a2c94ad01c51f5c6a2c94ad01c51f5c6a2c94ad01c51f5c6a2c94ad01c51f5c6a2c94ad01c51f5c6a2c94ad01c51f5c6a2c94ad01c51f5c6a2c94ad01c51f5c6a2c94ad01c51f5c6a2c94ad01c51f5c6a2c94ad01c51f83ce069ed4ec72ca909d23aa82fba2d93b556f338afb258a0e8354d4e54d285a5a6c7d5f11a2c8e3748b530ea6f861f4bf17a28e4beb0e133586b04736f49baee90bb56abaa8a5074941da93c03eb1006fed55a40ae99da7bd98b3c0c8381a4534a971367d882543bceb48270ef2769d8776b0af8156b90989c4a2ffd8178514d6cac89c79d907ec1b31118a693ca54159e03e079073e920b5e8b651b4e675c1b9713b5c26603f6b
# > ae26 0064 9bc438726b7ea1c155210d268c627652fa8188015115e860fa8188015115e860fa8188015115e860fa8188015115e860fa8188015115e860fa8188015115e860b16bc275862e8e63dde4d91b7acb2eeccae0cd6762f2a7fe19be949805b193d625750dee35e2b7002cad4c32798119aba708e2577b1354e6a97c64ff5862f936cd46c569bda5f39bb07a84dc88c4b6b4fa8188015115e860fa8188015115e860fa8188015115e860fa8188015115e860fa8188015115e860fa8188015115e860fa8188015115e860fa8188015115e860fa8188015115e860fa8188015115e860fa8188015115e860fa8188015115e860fa8188015115e860fa8188015115e860e00b108d4f144860e1cb3414a38b5985f936b2a4a439d4b280e4e92205f35a6697ed338c1bdf06b615e5257e823600c012f4749e82c35dec8e606e60f16f33f982c2382d663bbd6d8a270fb464ce4465baee96e1be3a73f33418630159be64f4c2ffb321618ef6165daed0c4aead204053a57dc455678008a087d6554d4c4760397a9f8df523b9c8fe795280e12cbb8b9af7872bef09e42c1e37846fbb03aa7c47a3133e1e89be03
# > ae26 0064 bb3c579522b924ad95c1676d839f2386f1644413d24f292cf1644413d24f292cf1644413d24f292cf1644413d24f292cf1644413d24f292cf1644413d24f292c9518d4dad139e3116345d76b55716fb6828f3e92780665aa42c0b00ed7ae70814981f976c31cff30c09d08822809acb169e1f0025e2e4b9fe820f838e3c0cbf7eace6ad35843f57b477c6633320d3f0cf1644413d24f292cf1644413d24f292cf1644413d24f292cf1644413d24f292cf1644413d24f292cf1644413d24f292cf1644413d24f292cf1644413d24f292cf1644413d24f292cf1644413d24f292cf1644413d24f292cf1644413d24f292cf1644413d24f292cf1644413d24f292cf78031347d274c53fd14f7557ce3de225f46fcbb108df4100286fc532bea3fad5f6e5c98780b42926ef2cb900530e3e5432ac4876d5275ef5b341ea1bf7a6ed432f1399f7957d629ed83009297077ba483ac5c0102fddd6a0e3a542180913e42a30230110669e1ebf38b5ace283d75c84b095ba50fcb4240871c1f6fa20ee649f8b20cec02d6db2c179ad41262206a1cf247429d563878d324ca4a43fe031ef53f6656fbfaaf6e6b
@register_parser(0x26ae)
class f26ae(BaseParser):
    def __init__(self):
        self.body = struct.pack('<BB', 0, 100)

@register_parser(0x26b1)
class f26b1(BaseParser):
    def __init__(self):
        self.body = struct.pack('<BBB', 0, 100, 0)

#!/usr/bin/env python3
"""中文小说角色分析 + 自动配音标注"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "voices.json"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 说话动词 (长优先) ──
SPEECH_VERBS = sorted([
    "冷笑道", "微笑道", "苦笑道", "低声道", "沉声道", "厉声道", "柔声道", "高声道",
    "低声说", "大声说", "轻声说", "小声说",
    "怒道", "笑道", "冷道", "喝道", "叹道", "惊道", "急道", "忙道",
    "说道", "问道", "答道", "喊道", "骂道", "叫道", "吼道", "哭道",
    "感叹道", "嘀咕道", "轻叹道",
    "说", "道", "问", "答", "喊", "叫", "吼", "骂",
    "嘟囔", "嘀咕", "咕哝", "嚷", "喃喃", "呢喃",
    "开口", "接口", "插嘴", "回答", "反驳", "质问", "追问",
    "感叹", "惊呼", "怒吼", "低吟", "轻叹", "冷哼", "提醒",
], key=len, reverse=True)

VERB_RE = re.compile("(" + "|".join(re.escape(v) for v in SPEECH_VERBS) + ")")

# 修饰词 (出现在人名和说话动词之间)
MODIFIERS = [
    "平静地", "冷冷地", "淡淡地", "缓缓地", "轻轻地", "慢慢地", "温柔地", "焦急地",
    "认真地", "严肃地", "随意地", "无奈地", "苦涩地", "坚定地", "得意地",
    "犹豫了一下", "沉默了一会儿", "想了想", "笑了笑", "叹了口气",
    "揉了揉太阳穴", "摇了摇头", "点了点头", "皱了皱眉", "长叹一声",
    "忍不住", "不禁", "不由得",
    "微微", "轻声", "低声", "高声", "沉声", "冷冷", "淡淡", "缓缓",
    "也", "又", "便", "就", "还", "却", "也跟着", "接着", "随即",
    "率先", "突然", "忽然", "果然", "终于",
    "愣了一下", "一愣",
]
MOD_RE = re.compile("(?:" + "|".join(re.escape(m) for m in sorted(MODIFIERS, key=len, reverse=True)) + ")")

# 非人名词
NOT_NAMES = {
    "什么", "怎么", "如何", "为何", "因为", "所以", "但是", "然而", "虽然",
    "不过", "可是", "只是", "于是", "然后", "接着", "随后", "突然", "忽然",
    "果然", "居然", "竟然", "终于", "已经", "正在", "马上", "立刻", "赶紧",
    "一个", "一声", "一番", "一阵", "这个", "那个", "自己", "对方",
    "众人", "大家", "别人", "有人", "旁人",
    "心中", "心里", "脸上", "身上", "手中", "面前",
    "此时", "这时", "那时", "当时", "如今", "现在",
    "不禁", "不由", "只好", "只得", "身后", "远处",
    # 对白内容首字被误当人名
    "我知", "你知", "我不知", "你不", "我们", "你们", "我要", "你要",
    "我会", "你会", "我能", "你能", "我是", "你是", "我的", "你的",
    "不知", "知道", "不要", "不会", "不能", "不是", "没有",
    "好的", "是的", "对的", "行了", "够了", "算了",
    # 常见动作/描写误匹配
    "后轻声", "柔的声", "温柔的", "声音", "微笑了", "点了点", "摇了摇",
    "皱了皱", "叹了口", "长叹一", "忍不住", "一阵",
    "了一下", "了一会", "了很久", "了半天",
    # 更多动作/状态词
    "轻声说", "大声说", "小声说", "冷冷地", "淡淡地", "缓缓地",
    "微笑", "苦笑", "冷笑", "轻笑", "讪笑", "嘲笑",
    "沉默了", "愣了", "停了", "站在", "坐在", "走到",
    "身后传", "远处传", "前面是", "后面是",
    "寂静的", "安静的", "漆黑的", "明亮的",
    "柔的", "的声音", "的语气", "的口吻",
    # 策略4/5 宽泛匹配可能产生的误识别
    "他低下", "她低下", "他抬起", "她抬起", "他转身", "她转身",
    "他站起", "她站起", "他坐下", "她坐下", "他走到", "她走到",
    "投资人", "服务员", "收银员", "保安", "路人",
    "必须接", "额工资", "活了下", "调整策", "京到这",
    "北京了", "上海了", "回来了", "出去了", "进来了",
    "钟楼下", "桌子上", "床上", "地上", "门口", "窗前", "路边",
    # 真实生产中高频误匹配 2 字词
    "简介", "结果", "回答", "沉默", "犹豫", "淡水", "细声", "咬牙",
    "她知", "他知", "谁知", "班长", "同学", "老板", "店长", "医生",
    "护士", "老头", "小弟", "大佬", "兄弟", "妹妹", "姐姐", "哥哥",
    "弟弟", "叔叔", "阿姨", "奶奶", "爷爷", "妈妈", "爸爸",
    "对方", "彼此", "两人", "几人", "众人", "旁人", "那人",
}

MALE_INDICATORS = {"他", "先生", "大哥", "兄弟", "爷", "叔", "伯", "爸", "父亲",
                   "公子", "少爷", "将军", "大人", "老爷", "哥哥", "弟弟", "总", "王爷"}
FEMALE_INDICATORS = {"她", "小姐", "姐姐", "妹妹", "姑娘", "夫人", "娘", "妈", "母亲",
                     "嫂", "婆", "公主", "皇后", "姐", "仙子", "雪", "雨", "月", "花",
                     "晓", "婷", "婉", "淑", "芳", "兰", "莲", "凤"}

# ── 引号处理 ──
QUOTE_PAIRS = [("\u201c", "\u201d"), ("\u300c", "\u300d"), ("\u300e", "\u300f"), ('"', '"')]


def find_quotes(text):
    """找所有引号对白 [(start, end), ...]"""
    results = []
    for oq, cq in QUOTE_PAIRS:
        i = 0
        while i < len(text):
            s = text.find(oq, i)
            if s == -1:
                break
            e = text.find(cq, s + 1)
            if e == -1:
                break
            results.append((s, e + 1))
            i = e + 1
    results.sort()
    # 去重叠
    cleaned = []
    last_end = -1
    for s, e in results:
        if s >= last_end:
            cleaned.append((s, e))
            last_end = e
    return cleaned


def _strip_name(raw):
    """清理提取到的原始名字"""
    if not raw:
        return None
    # 精确匹配
    if raw in NOT_NAMES:
        return None
    # 前缀匹配: "后轻声问" 里包含 NOT_NAMES 的 "后轻声"
    for banned in NOT_NAMES:
        if raw.startswith(banned) or banned.startswith(raw):
            return None
    # 单字排除（单字很少是人名，容易误匹配）
    if len(raw) == 1 and raw not in {"他", "她"}:
        return None
    # 去掉常见前缀: "财务总监张伟" → "张伟", "秘书小刘" → "小刘"
    prefixes = ["财务总监", "总经理", "副总", "董事长", "秘书", "投资人", "老板",
                "服务员", "司机", "老师", "教授", "医生", "护士", "警察"]
    for p in prefixes:
        if raw.startswith(p) and len(raw) > len(p):
            raw = raw[len(p):]
            break
    if raw in NOT_NAMES:
        return None
    return raw


def _extract_name_before_verb(s):
    """从 'XX修饰词verb' 的前缀中提取人名"""
    s = MOD_RE.sub('', s).strip()
    if not s:
        return None
    nm = re.search(r'([\u4e00-\u9fff]{1,4})$', s)
    return _strip_name(nm.group(1)) if nm else None


def extract_speaker(text, q_start, q_end):
    """
    提取某段对白的说话人。
    策略优先级: 引号前verb → 引号后verb → 分裂对白 → 冒号引出 → 引号后旁白中人名
    """
    before_raw = text[max(0, q_start - 50):q_start]
    after_raw = text[q_end:q_end + 50]

    # ── 策略1: 引号前 "XX[修饰]verb[：，]" ──
    before_clean = re.sub(r'[：:，,。；!\s]+$', '', before_raw)
    verb_m = None
    for m in VERB_RE.finditer(before_clean):
        verb_m = m
    if verb_m:
        name = _extract_name_before_verb(before_clean[:verb_m.start()])
        if name:
            return name

    # ── 策略2: 引号后 "..."XX verb ──
    # 只看到行尾，不跨行
    after_line = after_raw.split("\n")[0][:30]
    for verb in SPEECH_VERBS:
        idx = after_line.find(verb)
        if idx <= 0:
            continue
        candidate = after_line[:idx]
        # 去掉修饰词
        candidate = MOD_RE.sub('', candidate).strip()
        candidate = re.sub(r'[地着了]$', '', candidate)
        if candidate:
            nm = re.search(r'([\u4e00-\u9fff]{1,4})$', candidate)
            if nm:
                name = _strip_name(nm.group(1))
                if name:
                    return name
        break  # 只用第一个找到的 verb

    # ── 策略3: 引号前 "XX + [修饰/动作] + ：" ──
    # 匹配: 林晓雪轻笑一声：/ 父亲声音虚弱：/ 王总拍了拍桌子，
    colon_m = re.search(r'[:：]\s*$', before_raw)
    if colon_m:
        cut = colon_m.start()
        segment = before_raw[:cut].rstrip()
        # 从后往前找，先去掉动作/修饰词
        segment = MOD_RE.sub('', segment).strip()
        # 去掉末尾动作短语: 轻笑一声 / 叹了口气 / 拍了拍桌子 / 声音虚弱
        ACTION_TAIL = re.compile(
            r'(?:轻笑一声|微笑一声|冷笑一声|长叹一声|叹了口气|摇了摇头|点了点头'
            r'|拍了拍桌子|皱了皱眉|挥了挥手|握了握拳|揉了揉太阳穴'
            r'|说完|走来|跑来|走过来|站起来|坐下来|转过身|回过头'
            r'|声音虚弱|声音低沉|声音沙哑|语气平淡|语气冰冷|神色焦急|面色凝重'
            r'|轻声|低声|高声|沉声|冷冷|淡淡|缓缓|狠狠|急忙|连忙|赶紧'
            r')$'
        )
        segment = ACTION_TAIL.sub('', segment).strip()
        # 截断到第一个逗号/句号前（只取主语部分）
        segment = re.split(r'[，,。]', segment)[0].strip()
        # 再去掉残留动作
        segment = re.sub(r'[\u4e00-\u9fff]{0,6}(?:躺在|站在|坐在|走到|跑到|来到|回到|看着|望着|对着|靠在)[\u4e00-\u9fff]*$', '', segment).strip()
        if segment:
            nm = re.search(r'([\u4e00-\u9fff]{2,4})$', segment)
            if nm:
                name = _strip_name(nm.group(1))
                if name:
                    return name

    # ── 策略4: 分裂对白 "..."XX + 精确动作 + ，"..." ──
    after_30 = after_raw[:40]
    split_verbs = r'(?:揉了|点了|拍了|摇了|皱了|叹了|笑了|摸了|握了|挥了|拿了|放了|站起|坐下|走到|转过|抬起|低下|说完|接过|转身|回头)'
    nm = re.match(r'([\u4e00-\u9fff]{2,3}?)' + split_verbs, after_30)
    if nm:
        name = _strip_name(nm.group(1))
        if name:
            return name

    # ── 策略5: 引号后直接跟已知姓氏开头的人名 ──
    COMMON_SURNAMES = set("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华"
                         "金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方"
                         "俞任袁柳酆鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅"
                         "皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧"
                         "计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵季贾路娄危江童颜"
                         "郭梅盛林刁锺徐邱骆高夏蔡田樊胡凌霍虞万支柯管卢莫经房裘缪"
                         "宫桂白诸欧上司南长慕东公")
    # 先试 2 字名（姓+单名，后面非中文或跟动作），再试 3 字名
    nm2 = re.match(r'([\u4e00-\u9fff]{2})', after_30)
    if nm2:
        c = nm2.group(1)
        rest = after_30[2:3] if len(after_30) > 2 else ""
        # 2 字名后面跟非中文字、或者跟常见动词/助词
        post_is_action = rest and rest in "的了着过被把给让向得地边站坐走跑转抬低摇点揉拍握推拉看望叹愣停起说道冷笑轻高沉从忍连赶却脱挑晃撒掏双噗声音手头身眼面口心"
        if c[0] in COMMON_SURNAMES and _strip_name(c) and (not rest or ord(rest) < 0x4e00 or post_is_action):
            return c
    # 3 字名（只在 2 字没成功时尝试）
    nm3 = re.match(r'([\u4e00-\u9fff]{3})', after_30)
    if nm3:
        c = nm3.group(1)
        if c[0] in COMMON_SURNAMES and _strip_name(c) and RoleAnalyzer._looks_like_name(c):
            return c

    return None


def detect_pronoun_near(text, pos, window=15):
    """检测位置附近的代词性别"""
    snippet = text[max(0, pos - window):pos]
    he = snippet.count("他")
    she = snippet.count("她")
    if she > he:
        return "female"
    if he > she:
        return "male"
    return None


def infer_gender_for_name(name, text):
    """通过全文上下文推断角色性别"""
    # 先检查名字本身
    for kw in FEMALE_INDICATORS:
        if kw in name:
            return "female"
    for kw in MALE_INDICATORS:
        if kw in name:
            return "male"

    # 常见男性人名末字
    male_last_chars = {"伟", "强", "军", "刚", "明", "宇", "辉", "杰", "鹏", "勇", "磊", "涛"}
    # 常见女性人名末字
    female_last_chars = {"萍", "芳", "燕", "玲", "娟", "静", "敏", "丽", "艳", "秀", "琴", "霞"}
    if len(name) >= 2:
        last = name[-1]
        if last in female_last_chars:
            return "female"
        if last in male_last_chars:
            return "male"

    # 找全文中 "name" 附近的代词
    he_score = 0
    she_score = 0
    for m in re.finditer(re.escape(name), text):
        ctx = text[max(0, m.start() - 30):m.end() + 30]
        he_score += ctx.count("他")
        she_score += ctx.count("她")

    if she_score > he_score:
        return "female"
    if he_score > she_score:
        return "male"
    return None


class RoleAnalyzer:
    def __init__(self, config, text):
        self.config = config
        self.text = text
        self.roles_map = config["roles"]
        self.char_count = Counter()
        self.char_gender = {}
        self.last_speaker = None
        self.prev_speakers = []  # 最近2个不同说话人

    @staticmethod
    def _looks_like_name(s):
        """粗判是否像人名/称呼（2-4 中文字，不含常见非名字模式）"""
        if not s or len(s) < 2 or len(s) > 4:
            return False
        # 全中文
        if not re.match(r'^[\u4e00-\u9fff]+$', s):
            return False
        # 排除明显非名字
        # 含这些字的不可能是人名
        bad_chars = set("了的在着过被把给让向得地上下来去起到不能别再就都也还"
                        "很太更最才刚已这那哪每各某几多少大小好坏新旧"
                        "是有没会要想能可以吗呢吧啊哦嗯呀边跑跳"
                        "脱挑晃撒冷拉推拍打踢撞扑抓扔踩蹲"
                        "看见听闻知说道问答叫喊哭笑怒骂吃喝走站坐")
        if any(ch in bad_chars for ch in s):
            return False
        # 4 字候选更严格: 排除动词结尾和常见描述模式
        if len(s) == 4:
            bad_tails = ["闻言", "知道", "四周", "一边", "面前", "后面", "旁边",
                         "中间", "跑道", "介绍", "结果", "简介", "答案", "比赛"]
            for tail in bad_tails:
                if s.endswith(tail):
                    return False
            # 4 字名带常见姓氏才接受
            common_surnames = set("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华"
                                  "金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方"
                                  "俞任袁柳酆鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅"
                                  "皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧"
                                  "计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵季贾路娄危江童颜"
                                  "郭梅盛林刁锺徐邱骆高夏蔡田樊胡凌霍虞万支柯管卢莫经房裘缪"
                                  "宫桂白诸葛欧阳上官司马夏侯南宫长孙慕容东方公孙")
            if s[0] not in common_surnames:
                return False
        return True

    def first_pass(self):
        """第一遍: 扫描全文收集所有角色及性别"""
        quotes = find_quotes(self.text)
        for qs, qe in quotes:
            sp = extract_speaker(self.text, qs, qe)
            if sp and self._looks_like_name(sp):
                self.char_count[sp] += 1

        # 推断性别 (基于全文上下文)
        for name in self.char_count:
            g = infer_gender_for_name(name, self.text)
            if g:
                self.char_gender[name] = g

    def get_role(self, name):
        if not name:
            return "narrator"
        gender = self.char_gender.get(name)
        same = [n for n, _ in self.char_count.most_common() if self.char_gender.get(n) == gender]
        rank = same.index(name) if name in same else 999
        if gender == "male":
            return ["male_main", "male_side", "male_extra"][min(rank, 2)]
        elif gender == "female":
            return ["female_main", "female_side", "female_extra"][min(rank, 2)]
        return "unknown"

    def track(self, speaker):
        if speaker and speaker != self.last_speaker:
            if self.last_speaker:
                self.prev_speakers = [self.last_speaker, speaker]
            self.last_speaker = speaker

    def guess_alternating(self):
        if len(self.prev_speakers) == 2:
            return self.prev_speakers[1] if self.last_speaker == self.prev_speakers[0] else self.prev_speakers[0]
        return None

    def resolve_pronoun(self, gender):
        for n, _ in self.char_count.most_common():
            if self.char_gender.get(n) == gender:
                return n
        return None

    def second_pass(self):
        """第二遍: 生成标注段落"""
        segments = []
        quotes = find_quotes(self.text)
        lines = self.text.split("\n")
        line_positions = []
        pos = 0
        for line in lines:
            idx = self.text.find(line, pos)
            if idx == -1:
                idx = pos
            line_positions.append((idx, idx + len(line)))
            pos = idx + len(line) + 1

        for line, (lstart, lend) in zip(lines, line_positions):
            stripped = line.strip()
            if not stripped:
                continue

            # 本行内的引号
            lq = [(qs, qe) for qs, qe in quotes if qs >= lstart and qe <= lend]

            if not lq:
                segments.append(("narrator", stripped))
                continue

            cursor = lstart
            for qs, qe in lq:
                # 引号前旁白
                before_raw = self.text[cursor:qs].strip()

                # 提取说话人
                speaker = extract_speaker(self.text, qs, qe)
                if speaker:
                    speaker_registered = speaker
                else:
                    speaker_registered = None
                    # 后验: 引号后文本是否包含已知角色名
                    if not speaker_registered:
                        after_text = self.text[qe:qe + 30]
                        for known_name in self.char_count:
                            if after_text.startswith(known_name):
                                speaker_registered = known_name
                                break
                    # 代词推断
                    if not speaker_registered:
                        pg = detect_pronoun_near(self.text, qs)
                        if pg:
                            speaker_registered = self.resolve_pronoun(pg)
                    # 对话交替：只在前面有明确的两人对话时才用
                    if not speaker_registered and len(self.prev_speakers) == 2:
                        speaker_registered = self.guess_alternating()
                    # 最终回退：继承上一个说话人
                    if not speaker_registered:
                        speaker_registered = self.last_speaker

                # 清理旁白中的归属描写
                narr = self._clean_narration(before_raw)
                if narr and len(narr) > 1:
                    segments.append(("narrator", narr))

                # 对白
                dialogue = self.text[qs:qe]
                role = self.get_role(speaker_registered)
                segments.append((role, dialogue))

                if speaker_registered:
                    self.track(speaker_registered)

                cursor = qe

            # 行尾
            tail = self.text[cursor:lend].strip()
            if tail:
                tail_clean = self._clean_narration(tail)
                if tail_clean and len(tail_clean) > 1:
                    segments.append(("narrator", tail_clean))

        return segments

    def _clean_narration(self, text):
        """从旁白中去掉说话归属词 (XX说/XX道)"""
        # 去掉 "XX说：" / "XX道，"
        cleaned = text
        for verb in SPEECH_VERBS[:25]:
            cleaned = re.sub(
                r'[\u4e00-\u9fff]{1,6}?' + re.escape(verb) + r'[：:，,。]?\s*$',
                '', cleaned
            ).strip()
            cleaned = re.sub(
                r'^([\u4e00-\u9fff]{1,6})' + re.escape(verb) + r'[：:，,。]?\s*',
                '', cleaned
            ).strip()
        return cleaned


def segments_to_tagged(segments):
    """合并相邻同角色段"""
    result = []
    cur_role = None
    cur_texts = []
    for role, text in segments:
        if role == cur_role:
            cur_texts.append(text)
        else:
            if cur_role is not None and cur_texts:
                result.append(f"[{cur_role}]{' '.join(cur_texts)}[/{cur_role}]")
            cur_role = role
            cur_texts = [text]
    if cur_role is not None and cur_texts:
        result.append(f"[{cur_role}]{' '.join(cur_texts)}[/{cur_role}]")
    return "\n".join(result)


def analyze_text(text, config=None):
    if config is None:
        config = load_config()
    analyzer = RoleAnalyzer(config, text)
    analyzer.first_pass()
    segments = analyzer.second_pass()
    tagged = segments_to_tagged(segments)

    used = set(r for r, _ in segments)
    assignments = {}
    for r in used:
        if r not in config["roles"]:
            continue
        role_cfg = config["roles"][r]
        if isinstance(role_cfg, dict):
            assignments[r] = role_cfg  # {"voice": "...", "lang_code": "z"}
        else:
            assignments[r] = {"voice": role_cfg, "lang_code": "z"}
    role_counts = Counter(r for r, _ in segments)

    report = {
        "characters": dict(analyzer.char_count.most_common()),
        "character_genders": dict(analyzer.char_gender),
        "role_distribution": dict(role_counts),
        "voice_assignments": {k: v.get("voice", v) for k, v in assignments.items()},
        "total_segments": len(segments),
    }
    return tagged, assignments, report


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("-o", "--output")
    p.add_argument("--report", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()

    tagged, assignments, report = analyze_text(text)

    if args.report:
        print("=== 角色分析报告 ===")
        print(f"总分段数: {report['total_segments']}")
        print(f"\n识别到的角色:")
        for name, count in report["characters"].items():
            g = report["character_genders"].get(name, "未知")
            print(f"  {name}: {count}次 ({g})")
        print(f"\n角色分布:")
        for role, count in sorted(report["role_distribution"].items(), key=lambda x: -x[1]):
            voice = report["voice_assignments"].get(role, "?")
            print(f"  {role}: {count}段 -> {voice}")
    elif args.json:
        print(json.dumps({"tagged_text": tagged, "voice_assignments": assignments, "report": report},
                         ensure_ascii=False, indent=2))
    else:
        out = tagged
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(out)
            print(f"已保存: {args.output}", file=sys.stderr)
        else:
            print(out)

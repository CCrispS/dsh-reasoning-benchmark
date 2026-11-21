# -*- coding: utf-8 -*-
"""分镜内容：一个实体，五个名字（93 镜 / 约 16 分 42 秒）。

事实来源：技能 facts.md（154 行）+ assets.json 截图 + 2026-11-21 抓取的公开网页。
口径：只呈现记录与双方原话；所有推断一律写成带问号的猜测。
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMO = os.path.join(ROOT, "assets", "emoji")
TITLE = "一个实体，五个名字"


def e(cp):
    return os.path.join(EMO, cp + ".png")


def media(sid, type_, narr, sfx=None, **scene):
    d = scene
    d["type"] = type_
    return dict(id=sid, kind="media", sfx=sfx or [], scene=d, narration=narr)


def pic(sid, images, caption, narr, motion="push", sfx=None):
    return dict(id=sid, kind="image", images=images, caption=caption, motion=motion,
                narration=narr, sfx=sfx or [])


SHOTS = []
A = SHOTS.append

# ---------------------------------------------------------------- 0 开场

A(media("S01", "title",
        "先说清楚：这支片子只用三种东西——当事人自己发的原文、可以逐条核对的登记记录、以及他们自己网站上写着的字。"
        "每一处证据，画面上都会标出来源和日期；凡是我们自己的推断，都会打上问号。",
        kicker="2026 · 公开记录 · 逐条可核", title="一个实体，五个名字",
        sub="Chrono Divide · vera20k · 网页红警", foot="全部材料可公开核验 · 不含未证实指控",
        seed=31, warm=0.08, sfx=["impact-low"]))

A(media("S02", "network",
        "一个在 B 站叫「网页红警」、在 Discord 叫 dogemoon、在抖音叫「王二火大」、在 GitHub 叫 huangkaoya 的运营方，"
        "到底是什么？先别急着下结论。我们把线，一根一根接起来。",
        nodes=[dict(id="b", label="网页红警", sub="B 站", kind="party", x=0.26, y=0.30, emoji=e("1f4fa")),
                dict(id="d", label="dogemoon", sub="Discord", kind="party", x=0.50, y=0.20, emoji=e("1f4ac")),
                dict(id="x", label="huangkaoya", sub="X / GitHub", kind="party", x=0.74, y=0.30, emoji=e("1f310")),
                dict(id="t", label="王二火大", sub="抖音 · 公众号", kind="party", x=0.26, y=0.62, emoji=e("1f3ae")),
                dict(id="g", label="ra2web", sub="GitHub 组织", kind="doc", x=0.74, y=0.62, emoji=e("1f4da")),
                dict(id="q", label="？", sub="同一个运营方？", kind="conflict", x=0.50, y=0.84, emoji=e("2753"), r=52)],
        edges=[dict(a="b", b="q", style="dashed", conflict=True),
               dict(a="d", b="q", style="dashed", conflict=True),
               dict(a="x", b="q", style="dashed", conflict=True),
               dict(a="t", b="q", style="dashed", conflict=True),
               dict(a="g", b="q", style="dashed")],
        heading="五个名字，一条线？", sub="谁在说话，谁在注册，谁在否认", seed=32, sfx=["whoosh-soft"]))

A(pic("S03", ["img01.png"], "原作者声明一／2026-10-29 · 图1",
      "2026 年 10 月 29 日，Chrono Divide 的原作者发了一份声明。他写得很克制：这个项目只有三个人代表，"
      "官方网站只有 chronodivide.com 和它的子域名。", motion="up"))

A(pic("S04", ["img48.png"], "vera20k 作者声明／2026-11-08 · 图48",
      "十天后的 11 月 8 日，vera20k 的作者也发了声明：要求停止分发基于 VERA20K 的版本，禁止以任何方式使用 VERA20K 这个名字。",
      motion="down"))

# ---------------------------------------------------------------- 1 三个项目，三个实体

A(media("S05", "title",
        "先把三个项目分清楚。因为后面所有的争议，都建立在同一个问题上：这三个名字，到底属于谁。",
        kicker="第一章", title="三个项目，三个实体", sub="Chrono Divide · vera20k · RA2WEB",
        seed=33, num=1, total=6, sfx=["whoosh-soft"]))

A(pic("S06", ["img07.png"], "官方渠道／图7",
      "Chrono Divide 是网页版红警2的客户端和引擎，专有、闭源。有人问 chronodivide.cn 是不是官方站，"
      "原作者只回了一句：只有 chronodivide.com 和它的子域名。"))

A(pic("S06b", ["img05.png"], "镜像最初怎么部署的／图5",
      "这里补一句背景：镜像最初部署时，并没有先征得原作者同意，是破坏性更新之后才来联系。"
      "后来写下的条件是：不盈利、保留署名标识。"))

A(pic("S07", ["img23.png"], "镜像怎么来的／2026-10-31 · 图23",
      "他还说，中文镜像每次都是从他自己的域名自动同步客户端；镜像不是想开就能开的。", motion="left"))

A(pic("S07b", ["img17.png"], "部署教程与「可以分发」／2024-03-02 · 图17",
      "2024 年 3 月，B 站上出现了《如何部署自己的网页红井？》的教程；配套的群聊说法是："
      "历史静态文件的部署，原作者明确许可，可以分发。"))

A(pic("S08", ["img02.png"], "声明二：撤销许可／2026-11-04 · 图2",
      "2026 年 11 月 4 日的第二份声明里，他写明：许可条件没有被遵守，从 11 月 3 日起，撤销镜像许可。", motion="up"))

A(media("S09", "flow",
        "把 Chrono Divide 这条线拉直，只有三步：一个作者、一份有条件许可、一次公开撤销。没有第四步。",
        heading="Chrono Divide：三步，没有第四步",
        steps=[dict(label="一个作者", sub="use-strict · 三人维护", kind="start"),
               dict(label="有条件许可", sub="非商业 · 保留标识 · 注明原项目", kind="step"),
               dict(label="公开撤销", sub="2026-11-03 起", kind="bad")],
        note="以上全部来自原作者公开发言", seed=34))

A(pic("S10", ["img39.png"], "ra20k 的运营／图39",
      "vera20k 不一样。它是社区用 Rust 重写红警2的开源项目，GPLv3 加补充条款。作者 Halvor 说，"
      "ra20k.com 这个网页启动器由社区成员运营，并且得到他和贡献者的许可。"))

A(pic("S11", ["img34.png"], "CD 没有尤里／图34",
      "这里有个容易混淆的点：Chrono Divide 只支持原版红警2，没有《尤里的复仇》的内容。"
      "所以任何「尤里的复仇网页版」，都不可能是它。"))

A(pic("S12", ["img15.png"], "RA2WEB 的自我介绍／图15",
      "第三个是 RA2WEB，中文名「红色井界」。它自己的介绍页写着：游戏核心基于 Chronodivide 引擎；"
      "2023 年 8 月完成软著登记；2024 年 3 月，RA2WEB 商标在英国注册。", motion="down"))

A(pic("S12b", ["img04.png"], "「贡献」包括什么／2024-03-01 · 图4",
      "运营方列出的「贡献」是：修 AI bug、汉化、摇杆、网红色启动器。"
      "原作者在声明里只认可其中一项：中文翻译字符串——并特意说明，这不等于开发贡献。"))

A(pic("S13", ["img10.png"], "同一时期的另一种说法／图10",
      "而同一时期，另一个页面写的是：全面自研、完全知识产权的闭源项目、二十余万用户。", motion="left"))

A(media("S14", "contradiction",
        "同一个项目，两个页面，两种自我描述。这不是我们说的，是他们自己写的。",
        heading="同一个 RA2WEB，两种自我介绍",
        left=dict(img="图15", who="RA2WEB 介绍页", quote="游戏核心基于 Chronodivide 引擎", date="图15"),
        right=dict(img="图10", who="「关于红色井界™」", quote="全面自研，完全知识产权的闭源项目", date="图10"),
        verdict="那么，它到底是「基于 Chronodivide 的镜像」，还是「全面自研」？",
        seed=35, sfx=["glitch-burst"]))

A(pic("S15", ["img35.png"], "「尤里的复仇 Web」站／图35",
      "再往外一层，还有一个叫「尤里的复仇 Web」的站。页内搜 vera20k，结果是 0 个；页面上挂着「下载王二火大移动客户端」。"))

A(media("S16", "network",
        "到这里，三个实体已经清楚了：一个原作者，一个开源社区，一个中文运营方。接下来的问题只有一个——"
        "这个「中文运营方」，到底是谁。",
        nodes=[dict(id="cd", label="Chrono Divide", sub="原作者 · 专有闭源", kind="party", x=0.22, y=0.34, emoji=e("1f3ae")),
                dict(id="v", label="vera20k", sub="社区 · Rust · GPLv3", kind="doc", x=0.22, y=0.70, emoji=e("1f9f1")),
                dict(id="w", label="网页红警 / RA2WEB", sub="中文运营方", kind="conflict", x=0.62, y=0.52, emoji=e("1f310"), r=46),
                dict(id="q", label="？", sub="它是谁", kind="neutral", x=0.86, y=0.52, emoji=e("2753"), r=44)],
        edges=[dict(a="cd", b="w", style="solid", label="镜像授权"),
               dict(a="v", b="w", style="dashed", label="曾用代码"),
               dict(a="w", b="q", style="dashed", conflict=True)],
        heading="三个实体，一个问题", sub="谁在运营、谁在授权、谁在改代码", seed=36))

# ---------------------------------------------------------------- 2 一个实体，五个名字

A(media("S17", "title",
        "现在，把他们公开出现过的身份，一个一个列出来。请注意看每个平台的注册信息、每个视频里的链接、每个站点的页脚。",
        kicker="第二章", title="一个实体，五个名字", sub="账号 · 站点 · 商标 · 公司",
        seed=37, num=2, total=6, sfx=["riser-up"]))

A(media("S18", "network",
        "B 站的「网页红警」，Discord 的 dogemoon，X 上的 huangkaoya，抖音和微信公众号的「王二火大」，"
        "GitHub 上的 ra2web 组织——这些名字，指向的是同一个产品的同一条时间线。",
        nodes=[dict(id="b", label="网页红警", sub="B 站", kind="party", x=0.24, y=0.26, emoji=e("1f4fa")),
                dict(id="d", label="dogemoon", sub="Discord", kind="party", x=0.50, y=0.18, emoji=e("1f4ac")),
                dict(id="x", label="huangkaoya", sub="X", kind="party", x=0.76, y=0.26, emoji=e("1f310")),
                dict(id="t", label="王二火大", sub="抖音", kind="party", x=0.24, y=0.62, emoji=e("1f3ae")),
                dict(id="m", label="王二火大", sub="微信公众号", kind="party", x=0.50, y=0.62, emoji=e("1f4e2")),
                dict(id="g", label="ra2web / huangkaoya", sub="GitHub", kind="doc", x=0.76, y=0.62, emoji=e("1f4da")),
                dict(id="u", label="同一运营方", sub="跨平台账号", kind="conflict", x=0.50, y=0.88, r=48)],
        edges=[dict(a="b", b="u", style="dashed"), dict(a="d", b="u", style="dashed"),
               dict(a="x", b="u", style="dashed"), dict(a="t", b="u", style="dashed"),
               dict(a="m", b="u", style="dashed"), dict(a="g", b="u", style="dashed")],
        heading="账号层：六个入口", sub="同一个产品，同一批链接，同一段时间", seed=38, sfx=["whoosh-soft"]))

A(pic("S19", ["img46.png"], "B 站：张三水小／2026-11-15 · 图46",
      "B 站这条线最直白：2026 年 11 月 15 日，同一个账号发布「张三水小：尤里的复仇」，"
      "并称表现强于 vera20k、OpenRA 和 Chrono Divide。"))

A(pic("S20", ["img19.png"], "抖音：王二火大／图19",
      "抖音的「王二火大」主页，自称「全球第一个开源对标红警2游戏引擎的人」。"))

A(pic("S21", ["img20.png", "img21.png"], "X：huangkaoya／图20、图21",
      "X 上的 huangkaoya 说，他把自己手头的闭源项目「抽取」成开源仓库 ts-redalert2，用于 AI 训练；"
      "10 月 5 日又说，开源之前，大模型写不出红警2。", motion="left"))

A(pic("S22", ["img36.png"], "Discord：dogemoon 的说明／图36",
      "Discord 的 dogemoon 在解释 vera20k 争议时说：youlidefuchou 早就和包括 krizitian 在内的人讨论过，"
      "并如实披露基于 vera20k。"))

A(media("S23", "web",
        "而 youlidefuchou 这个站，页脚自己写着：历史版本曾基于 vera20k，历史分支在 github.com/huangkaoya/vera20k。",
        url="youlidefuchou.com/  （页脚原文）",
        title="历史版本与源码说明",
        lines=["*此网站历史发布的版本曾基于 vera20k 项目（GPLv3）。",
               "历史分支 github.com/huangkaoya/vera20k/tree/feature/vera-native-web",
               "提交 291b3461d5a7",
               "当前版本：基于 redalert2-recomp（MIT）"],
        tag="公开网页摘录", foot="© youlidefuchou.com", seed=39, sfx=["tick"]))

A(media("S24", "flow",
        "dogemoon 口中的「youlidefuchou」，就是那个站；那个站的历史分支，在 huangkaoya 名下。"
        "两句话，把三个 ID 连成了一条线。",
        heading="三个 ID，一条链",
        steps=[dict(label="dogemoon", sub="Discord 发言", kind="start"),
               dict(label="youlidefuchou", sub="「早就披露基于 vera20k」", kind="step"),
               dict(label="huangkaoya/vera20k", sub="该站自述的历史分支", kind="bad")],
        note="以上三句，均出自他们自己的公开页面与发言", seed=40, sfx=["whoosh-hard"]))

A(pic("S25", ["img37.png"], "PR #3087：改名／图37",
      "同样的 ID 也出现在 vera20k 的 PR 里：第 3087 号 PR 把 VERA20k.app 改名为「王二火大.app」，连 ipa 都跟着改名。"))

A(pic("S25b", ["img28.png"], "「会从自己的构建里移除」／2026-10-28 · 图28",
      "同一份声明里，dogemoon 还说明为什么要移除那个 logo：之前用它，是表示对创始人的尊重。"))

A(media("S26", "web",
        "而「王二火大」官网的友情链接里，赫然写着「Chronodivide」，指向 chronodivide.cn。",
        url="wangerhuoda.com/  （页脚 · 友情链接）",
        title="友情链接",
        lines=["*Chronodivide → https://chronodivide.cn",
               "正式服 game.ra2web.com",
               "测试服 gonghui.k0s.cn",
               "共和国之辉 · 尤里的复仇官网"],
        tag="公开网页摘录", foot="© 2026 王二火大", seed=41, sfx=["tick-fast"]))

A(pic("S27", ["img08.png", "img11.png"], "chronodivide.cn 的注册人／图8、图11",
      "而 chronodivide.cn 的注册人，是瑞得哈希（北京）科技有限责任公司，注册日 2025 年 10 月 26 日。"))

A(pic("S28", ["img12.png"], "瑞得哈希的企业登记／图12",
      "这家公司 2026 年 2 月 5 日成立，注册资本 1.25 万元，地址标注「集群注册」。", motion="left"))

A(pic("S29", ["img40.png"], "ra2ok.cn：同一个注册人／2026-11-06 · 图40",
      "2026 年 11 月 6 日，同一个注册人又注册了 ra2ok.cn——和 vera20k 的 ra20k.com，只差一个字母的顺序。"))

A(media("S30", "network",
        "账号、站点、商标、公司，四层。到这里，说「这些是同一个运营方」，已经不算猜了；"
        "但「是不是同一个人」，我们只能打一个问号，放在这里。",
        nodes=[dict(id="acc", label="六个账号", sub="B站·Discord·X·抖音·公众号·GitHub", kind="party", x=0.30, y=0.20, r=40),
                dict(id="site", label="六个站点", sub="ra2web · chronodivide.cn · ra2ok.cn …", kind="doc", x=0.30, y=0.50, r=40),
                dict(id="tm", label="CHRONO DIVIDE 商标", sub="第 91624924 号 · 2026-05-08 申请", kind="event", x=0.30, y=0.80, r=40),
                dict(id="co", label="瑞得哈希（北京）", sub="1.25 万 · 集群注册", kind="conflict", x=0.72, y=0.65, r=44),
                dict(id="q", label="同一个人？", sub="我们还不能回答", kind="neutral", x=0.72, y=0.26, r=44, emoji=e("2753"))],
        edges=[dict(a="acc", b="site", style="solid", label="同一批链接"),
               dict(a="site", b="tm", style="solid", label="同一主体"),
               dict(a="tm", b="co", style="solid", label="申请人"),
               dict(a="co", b="q", style="dashed", conflict=True),
               dict(a="acc", b="q", style="dashed")],
        heading="四层：账号 · 站点 · 商标 · 公司", sub="哪一层都可以查，只有「人」这一层要打问号", seed=42))

# ---------------------------------------------------------------- 3 平台关联网

A(media("S31", "title",
        "如果说账号还能辩称是巧合，那网站就很难了。因为网站会留下同一个模板、同一批链接、同一个备用入口。",
        kicker="第三章", title="同一套模板，同一批链接", sub="站点之间的指纹",
        seed=43, num=3, total=6, sfx=["whoosh-soft"]))

A(media("S32", "web",
        "ra2web.com、wangerhuoda.com、youlidefuchou.com、gongheguozhihui.com，四个站，页脚是同一组友情链接："
        "网页红警、王二火大、尤里的复仇官网、Chronodivide。",
        url="四个站点的页脚（对照）",
        title="同一组友情链接",
        lines=["ra2web.com          → 共和国之辉 · 王二火大 · 尤里的复仇官网",
               "wangerhuoda.com     → 正式服 · 测试服 · Chronodivide · 共和国之辉 · 尤里的复仇",
               "youlidefuchou.com   → 王二火大 · 共和国之辉 · Chronodivide",
               "gongheguozhihui.com → 网页红警 · 王二火大 · 尤里的复仇官网 · Chronodivide"],
        tag="公开网页摘录 · 2026-11-21", foot="四点互链", seed=44, sfx=["tick"]))

A(media("S33", "web",
        "连「必定能打开版」这个备用入口，四个站都指向同一个 B 站链接。",
        url="bilibili.com/toy/m7OYj6aBWZJxSY4I",
        title="同一个「必定能打开版」",
        lines=["*ra2web.com 首页 → bilibili.com/toy/m7OYj6aBWZJxSY4I",
               "*wangerhuoda.com 顶部 → 同一个链接",
               "*gongheguozhihui.com 首屏 → 同一个链接",
               "服务器不稳时，大家一起走同一条备用通道"],
        tag="公开网页摘录", foot="四个站点 · 同一个兜底入口", seed=45, sfx=["pop"]))

A(media("S34", "web",
        "更关键的是 ra2web.com 首页自己写的话：在 2026 年 11 月 3 日之前，它曾经是某个海外项目的中文镜像站点；"
        "在给这个项目带来巨大流量之后，合作被中止。",
        url="www.ra2web.com/  （「关于红色井界」段）",
        title="他们自己的原话",
        lines=["*在2026年11月3日之前，曾经是某个海外项目的中文镜像站点，",
               "*在给此项目带来巨大流量后，目前合作被中止。",
               "它是首个完全基于网页技术开发的、对标《红色警戒2》的游戏引擎，",
               "具有完全知识产权的闭源项目……深受全球20余万用户喜爱。"],
        tag="公开网页摘录", seed=46, sfx=["impact-hit"]))

A(media("S35", "web",
        "而 chronodivide.cn 上写着：具有独立自主知识产权；RA2WEB 是 ChronoDivide 的中文版；"
        "如需基于 Chronodivide 二次开发，请联系原作者购买授权。",
        url="www.chronodivide.cn/",
        title="ChronoDivide 全平台即时战略类游戏引擎",
        lines=["*TypeScript 完全重写的游戏引擎，独立自主知识产权",
               "*RA2WEB 是 ChronoDivide 的中文版",
               "如您需基于 Chronodivide 进行二次开发，请务必通过 discord 联系原作者购买授权",
               "© 2025 ChronoDivide. All rights reserved."],
        tag="公开网页摘录", seed=47, sfx=["tick"]))

A(media("S36", "contradiction",
        "同一段话里，前半句是「镜像站点」，后半句是「首个完全基于网页技术开发、具有完全知识产权的闭源项目」。"
        "两个说法之间，没有过渡。",
        heading="同一段话里的两句话",
        left=dict(img="图15", who="介绍页：引擎来源", quote="游戏核心基于 Chronodivide 引擎", date="图15"),
        right=dict(img="图9", who="关于页：知识产权", quote="RA2WEB 是 ChronoDivide 的中文版", date="图9"),
        verdict="如果只是「中文版」，那「完全知识产权」指的是哪一部分？",
        seed=48, sfx=["glitch-burst"]))

A(pic("S37", ["img09.png"], "关于页的红框／图9",
      "这个说法不是孤例。关于页里，还专门用红框标出了同一句话。", motion="up"))

A(media("S38", "flow",
        "六个域名，一个页脚，一套模板，一个注册人。这不是六个项目，这是一套门面。",
        heading="域名族谱",
        steps=[dict(label="ra2web.com", sub="主站 · 2026 年改口", kind="start"),
               dict(label="chronodivide.cn", sub="2025-10-26 · 瑞得哈希", kind="step"),
               dict(label="ra2ok.cn", sub="2026-11-06 · 同一注册人", kind="bad"),
               dict(label="wangerhuoda.com", sub="桌面/移动客户端", kind="step"),
               dict(label="youlidefuchou.com", sub="张三水小 · 曾用 vera20k", kind="step"),
               dict(label="gongheguozhihui.com", sub="共和国之辉 · 上游源", kind="end")],
        note="以上域名均可在公开注册信息或站点页脚核对", seed=49))

A(media("S39", "web",
        "同一个首页还写着：捐赠 200 元以上的，可以自由决定挂名内容；金牌赞助商的位置，给了一家游戏账号交易平台。",
        url="www.ra2web.com/  （赞助与合作）",
        title="赞助与合作",
        lines=["*捐赠 200 元以上的，可以自由决定挂名内容。",
               "金牌赞助商：盼之游戏交易（pzds.com）· 游戏账号交易代售",
               "目前不存在任何商业化行为，站点运营费用全部由运营方承担。",
               "服务器 500 元每月 · 6 台合计"],
        tag="公开网页摘录", seed=50, sfx=["heartbeat"]))

A(pic("S39b", ["img41.png", "img42.png"], "MOD 悬赏：200 到 2000 元／图41、图42",
      "还有一条「MOD 悬赏」：200 元起，最高 2000 元。评论区里，网页红警回复说「先给一部分，200 作为辛苦费」。"
      "这条视频后来被删除。", motion="left"))

A(media("S40", "network",
        "把这些连起来看：账号是入口，域名是店面，公司是收款主体，商标是护城河。"
        "一个完整的商业结构，被包装成了一个「热爱红警的社区项目」。",
        nodes=[dict(id="acc", label="账号矩阵", sub="B站 · 抖音 · Discord · X", kind="party", x=0.18, y=0.30, emoji=e("1f4e2")),
                dict(id="dom", label="域名店面", sub="6 个站点互链", kind="doc", x=0.50, y=0.24, emoji=e("1f310")),
                dict(id="pay", label="收款与赞助", sub="加密货币 · 赞助商 · 道具", kind="event", x=0.82, y=0.34, emoji=e("1f4b0")),
                dict(id="co", label="瑞得哈希", sub="商标 · 域名注册者", kind="conflict", x=0.50, y=0.62, emoji=e("1f3e2")),
                dict(id="tm", label="CHRONO DIVIDE", sub="商标 91624924", kind="conflict", x=0.82, y=0.70, emoji=e("1f3f7")),
                dict(id="q", label="？", sub="这是社区，还是生意？", kind="neutral", x=0.18, y=0.70, emoji=e("2753"), r=46)],
        edges=[dict(a="acc", b="dom", style="solid"), dict(a="dom", b="pay", style="solid"),
               dict(a="dom", b="co", style="solid"), dict(a="co", b="tm", style="solid"),
               dict(a="pay", b="tm", style="dashed"), dict(a="acc", b="q", style="dashed", conflict=True)],
        heading="平台关联网", sub="入口 · 店面 · 收款 · 商标", seed=51, sfx=["whoosh-hard"]))

# ---------------------------------------------------------------- 4 前后矛盾九问

A(media("S41", "title",
        "下面九处，全部来自他们自己的账号、自己的网站、自己的提交记录。我们只做一件事：把两句话放在一起。",
        kicker="第四章", title="九处前后矛盾", sub="都是他们自己说的",
        seed=52, num=4, total=6, sfx=["riser-long"]))

A(media("S42", "contradiction",
        "第一处。2023 年 12 月 12 日的 B 站动态说：不是私服，就是 chronodivide 正规授权；chronodivide 是网页红警的国际版项目名。"
        "十天后，私信里被问「游戏主体核心不是你的吧」，回答是：不是我的，我也没说过是我的。",
        heading="① 国际版？还是「不是我的」？",
        left=dict(img="图13", who="B 站动态", quote="“不是私服，就是 chronodivide 正规授权”", date="2023-12-12"),
        right=dict(img="图14", who="私信", quote="“不是我的”“我也没说过是我的”", date="2023-12-22"),
        verdict="十天之内，同一个账号，两种说法。哪一句是真的？",
        seed=53, sfx=["glitch-burst"]))

A(media("S43", "contradiction",
        "第二处。2023 年 10 月 1 日的评论说：我们是大中华区代理。原作者的回答是：官方只有 chronodivide.com 及其子域名。",
        heading="② 「大中华区代理」？",
        left=dict(img="图6", who="B 站评论", quote="“我们是大中华区代理”", date="2023-10-01"),
        right=dict(img="图7", who="原作者", quote="“Only chronodivide.com and subdomains”", date="Discord"),
        verdict="如果代理关系存在，为什么原作者连域名都不认？",
        seed=54, sfx=["glitch-burst"]))

A(pic("S44", ["img16.png"], "原作者的回应／图16",
      "同一句「国际版项目名」，原作者在 Discord 里回的是一个竖中指的表情。我们不为这个动作辩护，"
      "但它至少说明：他否认这个说法。", motion="up"))

A(media("S45", "contradiction",
        "第三处。部署教程和群聊里说：历史静态文件的部署，原作者明确许可，可以分发。"
        "原作者看到这句话，只回了三个词：obviously not true。",
        heading="③ 「明确许可，可以分发」？",
        left=dict(img="图18", who="部署教程", quote="“chronodivide 并不是开源项目…不提供源代码”", date="图18"),
        right=dict(img="图22", who="原作者", quote="“obviously not true”", date="Discord"),
        verdict="如果许可存在，书面记录在哪里？",
        seed=55, sfx=["glitch-burst"]))

A(media("S46", "contradiction",
        "第四处。他们说自己「全面自研、完全知识产权」；而自己的仓库 README 写着：基于《红色井界》RA2WEB 的分析而开发，许可证 GPL-3.0。",
        heading="④ 「全面自研」？",
        left=dict(img="图10", who="关于红色井界™", quote="“全面自研”“完全知识产权”", date="图10"),
        right=dict(img="图24", who="ts-redalert2 README", quote="“基于《红色井界》RA2WEB 的分析而开发”", date="图24"),
        verdict="「全面自研」和「基于分析而开发」，这两句能同时成立吗？",
        seed=56, sfx=["impact-hit"]))

A(pic("S47", ["img25.png"], "提交记录：改为完全自研／图25",
      "仓库里还有一个提交，标题就叫：把 ra2web 重新定位为完全自研，并移除 Chronodivide 的直通。"
      "同一次提交里，向 Chrono Divide 捐赠的入口被撤下。", motion="left"))

A(pic("S48", ["img26.png"], "README 改动：删掉侵权声明／图26",
      "另一处改动，把《时空分裂》换成《红色井界》，并删掉了「均视为对原作者和 RA2WEB 的侵权」这句话。", motion="right"))

A(pic("S49", ["img27.png"], "主菜单上的 CHRONO DIVIDE／图27",
      "可是王二火大的主菜单上，标题下面仍然挂着 CHRONO DIVIDE 的标识。"))

A(media("S50", "contradiction",
        "第五处。被问到商标，dogemoon 说「并不是抢注，是代为国内维权」。"
        "商标公告第 91624924 号的申请人，是瑞得哈希；原作者的原话是：I did not authorize it。",
        heading="⑤ 「代为维权」？",
        left=dict(img="图31", who="dogemoon", quote="“并不是抢注……代为国内维权”", date="2026-10-28"),
        right=dict(img="图32", who="原作者", quote="“I did not authorize it.”", date="2026-10-29"),
        verdict="如果只是「代为」，授权书在哪里？",
        seed=57, sfx=["glitch-burst"]))

A(pic("S50b", ["img30.png"], "「舆论审判」与「大家都去注册商标」／2026-10-28 · 图30",
      "同一天，他还写道：这件事在中国已经变成了舆论审判；如果我维权成功，希望大家都去把自己的商标注册了。"
      "这句话该怎么理解，请你判断。"))

A(pic("S51", ["img01.png"], "声明一：未授权商标／2026-10-29 · 图1",
      "声明一里也写了：从未授权 RA2WEB、dogemoon、Redhash 或任何相关方，在任何地区申请或注册 CHRONO DIVIDE 商标。"))

A(media("S52", "contradiction",
        "第六处。B 站评论说，已经获得 vera20k 创始人的「正式确认 ok」。"
        "vera20k 作者的声明原文是：这个 OK 只表示我看到了对方报告的修改，不代表认可此前的行为。",
        heading="⑥ 「正式确认 ok」？",
        left=dict(img="图47", who="B 站评论", quote="“已获 vera20k 创始人正式确认 ok”", date="图47"),
        right=dict(img="图48", who="vera20k 作者", quote="“这个 OK 只表示看到了修改”", date="2026-11-08"),
        verdict="一句「OK」，是谁在替谁解释？",
        seed=58, sfx=["glitch-burst"]))

A(pic("S53", ["img36.png"], "网页红警方的说明／图36",
      "网页红警方这边也有说明：修改部分的源码因个人原因没有及时上传，「这是我的问题」；"
      "他们已经提交了认为没有问题的 3090 号 PR。"))

A(pic("S54", ["img49.png"], "私信：投毒？／2026-10-27 · 图49",
      "同一段私信里还有一句：「你真觉得我是在投毒啊？」", motion="down"))

A(media("S55", "contradiction",
        "第七处。私信说「cd 通过我的渠道已经拿了至少 5000 赞助」「他因为我的网站收入了几乎上万元」。"
        "原作者说，几年前确实收到过一笔 DOGE 捐赠，但按他的换算，远没有这个数额。",
        heading="⑦ 「至少 5000」？",
        left=dict(img="图43", who="私信", quote="“至少 5000 赞助”“几乎上万元”", date="图43、图44"),
        right=dict(img="图45", who="原作者", quote="“nowhere near that amount”", date="2026-10-28"),
        verdict="同一笔钱，两个数字。差的是汇率，还是别的？",
        seed=59, sfx=["glitch-burst"]))

A(pic("S56", ["img03.png"], "决胜商店／图3",
      "第八处。一个写着「目前不存在任何商业化行为」的项目，客户端里有一个「决胜商店」："
      "排位翻倍卡、重新定级卡、大厅喇叭，全部以「决胜点」计价。截图没有显示，决胜点怎么获得。", motion="up"))

A(media("S57", "web",
        "而首页的另一处写着：站点运营费用全部由运营方承担，服务器 500 元每月、6 台。",
        url="www.ra2web.com/  （当前网站费用）",
        title="当前网站费用",
        lines=["腾讯云 CDN · 已获得赞助免费套餐",
               "服务器 · 500 元每月 · 6 台合计",
               "*目前不存在任何商业化行为，站点运营费用全部由运营方承担。"],
        tag="公开网页摘录", seed=60))

A(pic("S58", ["img29.png"], "「跟我运营的网站无关」／图29",
      "第九处。评论里说 ts-redalert2「跟目前我运营的网站无关，只是一个单纯的开源项目」；"
      "同一条评论又说，项目里有多个 GPLv3 代码，按 GPLv3 的要求「cd 应该开源，否则是他违规」。", motion="left"))

A(pic("S59", ["img50.png"], "自述／图50",
      "还有一句自述：「我或许就是使命召唤中的普莱斯，我有自己热爱的东西需要捍卫。」"
      "这句话我们不评论，原样放在这里。"))

A(media("S60", "wall",
        "九处矛盾，全部来自他们自己的材料。你可以不同意我们的解读，但你无法否认这些页面的存在。",
        heading="九处矛盾 · 证据墙", sub="每一张都能在原始出处找到",
        cols=5,
        items=[dict(img="图13", label="① 国际版"), dict(img="图14", label="① 不是我的"),
               dict(img="图6", label="② 大中华区代理"), dict(img="图7", label="② 只认 .com"),
               dict(img="图18", label="③ 可以分发"), dict(img="图22", label="③ not true"),
               dict(img="图10", label="④ 全面自研"), dict(img="图24", label="④ 基于分析"),
               dict(img="图31", label="⑤ 代为维权"), dict(img="图32", label="⑤ 未授权")],
        note="图13/14 · 6/7 · 18/22 · 10/24 · 31/32", seed=61, sfx=["whoosh-mega"]))

# ---------------------------------------------------------------- 5 提问环节

A(media("S61", "question",
        "那么，问题来了。",
        kicker="第五章", title="那么，问题来了。",
        questions=["如果只是镜像，为什么页面上写着「独立自主知识产权」？",
                   "如果只是「代为维权」，为什么商标申请人是自己的公司？",
                   "如果「全面自研」，为什么仓库写着「基于分析而开发」？"],
        foot="先不急着回答，把问题记下来", seed=62, emoji=e("1f914"), sfx=["question-ding"]))

A(media("S62", "question",
        "这些问题，一个比一个难回答。因为每回答一个，就会碰到下一处的记录。",
        kicker="继续", title="还能怎么解释？",
        questions=["如果「非商业化」，决胜商店的道具钱从哪里来？",
                   "如果「合作被中止」，为什么还在用它的名字做域名？",
                   "如果「只是开源项目」，为什么 PR 要改别人的应用名？"],
        seed=63, emoji=e("1f914"), sfx=["question-ding"]))

A(media("S63", "stamp",
        "而这一连串问题，有一个共同点：答案不在我们的猜测里，而在他们自己的记录里。",
        emoji_path=e("1f914"), text="问题，比答案更清楚", sub="九处矛盾 · 十问待答",
        color="#FFD38A", seed=64, sfx=["stamp"]))

# ---------------------------------------------------------------- 6 十问

A(media("S64", "title",
        "下面十个问题，我们只对着「网页红警这个实体」问，不针对任何个人。每一个问题后面，都挂着一条证据。",
        kicker="第六章", title="十问", sub="对着实体问，不针对个人",
        seed=65, num=5, total=6, sfx=["riser-long"]))

A(media("S65", "bigq",
        "第一问。你们说「不是私服，就是正规授权」，为什么同一个账号，在被问到「游戏主体核心是不是你的」时，回答「不是我的」？",
        num="Q01", text="你们说「不是私服，就是正规授权」——那为什么同一个账号，在被问「核心是不是你的」时，回答「不是我的」？",
        sub="同一账号 · 相隔十天 · 两种说法", ev="图13 / 图14", tag="证据", seed=66, sfx=["question-ding"]))

A(media("S66", "bigq",
        "第二问。你们说「我们是大中华区代理」，为什么原作者公开表示，官方只有 chronodivide.com 和它的子域名？",
        num="Q02", text="你们说「我们是大中华区代理」——那为什么原作者公开表示，官方只有 chronodivide.com 和它的子域名？",
        sub="代理关系如果有，凭据在哪", ev="图6 / 图7", tag="证据", seed=67, sfx=["question-ding"]))

A(media("S67", "bigq",
        "第三问。你们说「原作者明确许可，可以分发」，为什么原作者看到这句话，回的是 obviously not true？",
        num="Q03", text="你们说「原作者明确许可，可以分发」——那为什么原作者看到这句话，回的是 obviously not true？",
        sub="没有书面许可的公开记录", ev="图18 / 图22", tag="证据", seed=68, sfx=["question-ding"]))

A(media("S68", "bigq",
        "第四问。你们说「全面自研、完全知识产权」，为什么你们自己的仓库写着「基于《红色井界》RA2WEB 的分析而开发」？",
        num="Q04", text="你们说「全面自研、完全知识产权」——那为什么你们自己的仓库写着「基于《红色井界》RA2WEB 的分析而开发」？",
        sub="同一次提交里，捐赠入口被撤下", ev="图10 / 图24 / 图25", tag="证据", seed=69, sfx=["question-ding"]))

A(media("S69", "bigq",
        "第五问。你们说「曾经是中文镜像」，为什么同一段话的后半句，又写着「首个完全基于网页技术开发、具有完全知识产权的闭源项目」？",
        num="Q05", text="你们说「曾经是中文镜像站点」——那为什么同一段话的后半句，又写着「首个完全基于网页技术开发、具有完全知识产权的闭源项目」？",
        sub="两句话之间没有过渡", ev="ra2web.com 首页 / 图9", tag="公开网页", seed=70, sfx=["question-ding"]))

A(media("S70", "bigq",
        "第六问。你们说「代为国内维权」，为什么 CHRONO DIVIDE 商标的申请人，是 2026 年 2 月 5 日才成立、注册资本 1.25 万元的瑞得哈希？",
        num="Q06", text="你们说「代为国内维权」——那为什么这个商标的申请人，是成立不到一年、注册资本 1.25 万元的瑞得哈希？",
        sub="原作者：I did not authorize it", ev="图31 / 图32 / 图12", tag="证据", seed=71, sfx=["question-ding"]))

A(media("S71", "bigq",
        "第七问。你们说「已获 vera20k 创始人正式确认 ok」，为什么作者原文说，这个 OK 只表示看到了对方报告的修改？",
        num="Q07", text="你们说「已获 vera20k 创始人正式确认 ok」——那为什么作者原文说，这个 OK 只表示看到了对方报告的修改？",
        sub="作者随后禁止以任何方式使用 VERA20K", ev="图47 / 图48", tag="证据", seed=72, sfx=["question-ding"]))

A(media("S72", "bigq",
        "第八问。你们说「目前不存在任何商业化行为」，为什么客户端里有以「决胜点」计价的商店，金牌赞助商是一家游戏账号交易平台？",
        num="Q08", text="你们说「不存在任何商业化行为」——那为什么客户端里有以「决胜点」计价的商店，金牌赞助商是一家账号交易平台？",
        sub="截图没有显示决胜点如何获得", ev="图3 / ra2web.com", tag="证据", seed=73, sfx=["question-ding"]))

A(media("S73", "bigq",
        "第九问。你们的镜像从原作者域名自动同步客户端；许可撤销之后，同步的又是什么？",
        num="Q09", text="你们的镜像，每次从原作者的域名自动同步客户端——那许可撤销之后，同步的又是什么？",
        sub="原作者：镜像不是想开就能开的", ev="图23 / 图2", tag="证据", seed=74, sfx=["question-ding"]))

A(media("S74", "bigq",
        "第十问。你们说「王二火大是个无厘头的名字」，为什么 PR #3087 要把 VERA20k.app 改名成「王二火大.app」，连 ipa 都跟着改？",
        num="Q10", text="你们说「王二火大是个无厘头的名字」——那为什么 PR #3087 要把 VERA20k.app 改名成「王二火大.app」，连 ipa 都跟着改？",
        sub="PR 未合并即被关闭", ev="图49 / 图37 / 图48", tag="证据", seed=75, sfx=["question-ding"]))

A(media("S75", "wall",
        "十问，十条证据。我们不需要任何人点头，也不需要任何人回答。只要这些页面还在，问题就一直在。",
        heading="十问 · 十条证据", sub="编号与截图一一对应", cols=5,
        items=[dict(img="图13", label="Q01"), dict(img="图6", label="Q02"), dict(img="图22", label="Q03"),
               dict(img="图24", label="Q04"), dict(img="图9", label="Q05"), dict(img="图32", label="Q06"),
               dict(img="图48", label="Q07"), dict(img="图3", label="Q08"), dict(img="图23", label="Q09"),
               dict(img="图37", label="Q10")],
        note="全部为公开截图或公开网页", seed=76, sfx=["whoosh-mega"]))

# ---------------------------------------------------------------- 7 猜测

A(media("S76", "title",
        "接下来这一段，是猜测。我们把它单独放在这里，因为它是整支片子里唯一没有直接证据的部分。"
        "每一条都带问号，你可以不同意。",
        kicker="第七章", title="那么，图什么？", sub="以下全部是带问号的猜测",
        seed=77, num=6, total=6, sfx=["riser-up"]))

A(media("S77", "guess",
        "第一个猜测：借名。用一个已经在玩家群里传开的名字，承接搜索、承接信任、承接「正规授权」这四个字。",
        index="01", guess="借名：让「Chronodivide」这四个字，替自己的产品说话？",
        basis="chronodivide.cn 自称独立知识产权；王二火大官网把 Chronodivide 指向它；图13 说「国际版项目名」",
        seed=78))

A(media("S78", "guess",
        "第二个猜测：转身。先把镜像做大，再宣布「已具备独立研发能力」，把上游从「作者」变成「合作方」。",
        index="02", guess="转身：把「镜像」改写成「对等合作」，让上游从授权方变成合作伙伴？",
        basis="ra2web.com 发展历程：2025-10 推出「完全基于自研代码重新编译」的测试服；「双方目前为对等合作关系」",
        seed=79))

A(media("S79", "guess",
        "第三个猜测：占位。抢在原作进入中国市场之前，把域名、商标、公司都摆好，形成事实上的品牌控制。",
        index="03", guess="占位：先把域名、商标、公司摆好，让后来者绕不开？",
        basis="chronodivide.cn 2025-10 注册；商标 2026-05 申请；ra2ok.cn 2026-11 注册；注册人同一家",
        seed=80))

A(media("S80", "guess",
        "第四个猜测：合法化。用「已获确认」「遵循 GPLv3」这类说法，降低社区的阻力，把争议变成流程问题。",
        index="04", guess="合法化：用「已获确认」「遵循 GPL」降低社区阻力，把侵权争议变成流程问题？",
        basis="图47「正式确认 ok」；图36「至少遵循了 GPLv3」「已提交 3090 号 PR」",
        seed=81))

A(media("S81", "guess",
        "第五个猜测：变现。流量先留住，再有赞助、有道具、有账号交易平台的广告位。",
        index="05", guess="变现：先用「热爱」留住流量，再把流量换成赞助、道具和广告位？",
        basis="决胜商店（图3）；捐赠 200 元以上可挂名；金牌赞助商为游戏账号交易平台；五个加密货币地址",
        seed=82))

A(media("S82", "question",
        "这五个猜测，我们一个都不能证明。它们只是把公开记录串起来之后，最自然的几种可能。"
        "如果当事人愿意回答，我们很乐意把答案放进下一支片子。",
        kicker="声明", title="这只是猜测",
        questions=["我们不能证明动机，只能列出可能",
                   "所有判断，请回到原始截图与公开页面核对",
                   "如有回应，欢迎提供公开链接"],
        foot="猜测不是证据 · 结论留给观众", seed=83, emoji=e("1f9d0")))

# ---------------------------------------------------------------- 8 收束

A(media("S83", "chain",
        "最后，把时间线收在一起。从 2023 年的第一句「大中华区代理」，到 2026 年 11 月的两份声明。",
        heading="一条时间线", sub="2023 – 2026 · 全部有截图或公开记录",
        items=[dict(date="2023-10-01", label="「大中华区代理」", sub="图6"),
               dict(date="2023-12-12", label="「正规授权」", sub="图13"),
               dict(date="2023-12-22", label="「不是我的」", sub="图14"),
               dict(date="2024-03-02", label="「可以分发」", sub="图17"),
               dict(date="2025-10-26", label="chronodivide.cn", sub="图11"),
               dict(date="2026-05-08", label="商标申请", sub="图32"),
               dict(date="2026-10-29", label="声明一", sub="图1", hot=True),
               dict(date="2026-11-03", label="撤销许可", sub="图2", hot=True),
               dict(date="2026-11-08", label="vera20k 声明", sub="图48", hot=True)],
        seed=84, sfx=["typewriter"]))

A(media("S84", "flow",
        "如果只记一件事，记这个方法：看到授权，先找书面许可；看到自研，先看仓库；看到维权，先看商标申请人。",
        heading="三步核验法",
        steps=[dict(label="看到「授权」", sub="先找书面许可", kind="start"),
               dict(label="看到「自研」", sub="先看仓库与提交记录", kind="step"),
               dict(label="看到「维权」", sub="先看商标申请人", kind="step"),
               dict(label="看到「合作」", sub="先看对方认不认", kind="good")],
        note="这三步，不需要任何立场", seed=85))

A(media("S85", "web",
        "所以，最后的建议很短：玩游戏，认准官方渠道；用开源项目，看清许可证；看到「正规授权」四个字，先问一句——授权书在哪。",
        url="chronodivide.com  ·  game.chronodivide.com",
        title="如果你只是想玩游戏",
        lines=["*官方渠道只有 chronodivide.com 及其子域名（原作者原话）",
               "vera20k：YuriPlanet/vera20k（GPLv3 + 补充条款）",
               "任何「中文版」「国际版」「代理版」，先核对再下载"],
        tag="本片建议", seed=86, sfx=["pop"]))

A(media("S86", "quote",
        "这支片子里，没有一句是我们替谁下的结论。我们只是把他们的两句话，放在了一起。",
        text="我们不下结论。我们只把两句话，放在一起。",
        source="全部证据：图1–图50 · 公开网页 2026-11-21 抓取", who="— 本片立场", seed=87))

A(media("S87", "end",
        "二〇二六年十一月，网页红警的全平台实体关联网、九处前后矛盾、十问，以及五个带问号的猜测，都在这里了。"
        "证据清单在简介里，欢迎逐条核对。",
        title="一个实体，五个名字", lines=["48 张原始截图 · 6 个公开网页，逐条可核", "九处矛盾 · 十问 · 五个猜测（带问号）",
                                       "官方渠道：chronodivide.com"], foot="2026-11 · 全部材料公开可查", seed=88))

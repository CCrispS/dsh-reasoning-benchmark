# 场景目录

所有场景都是 `Scene` 子类，实现 `frame(t) -> PIL.Image`，由 `anim.render_scene()` 逐帧写成 mp4。参数直接对应 `story_v3.py` 里的 `scene=dict(...)`。

## 基础场景（`tools/scenes.py`）

| 类型 | 签名 | 用途 | 要点 |
| --- | --- | --- | --- |
| `title` | `(dur, kicker, title, sub, foot, seed, warm, num, total)` | 开场 / 章节卡 | 标题逐字浮起 + 下划线左扫；`num` 给右侧 420px 半透明大号章节数字（alpha 0.06），`total` 画底部进度点 |
| `network` | `(dur, nodes, edges, heading, sub, seed, top, warm)` | 关系网 | 节点 `{id,label,sub,kind,x,y,emoji,r}`，`x/y` 为 0–1 比例；边 `{a,b,style,label,conflict,arrow}`，`style="dashed"`，`conflict=True` 变红色虚线 + 沿线脉冲 + 双环 |
| `versus` | `(dur, left, right, center, center_emoji, heading, seed)` | 左右对照板 | `left/right = {title, who, items:[{t,mark,note}], color}`；`mark` 为 `✓`/`✕`，自动用矢量图标绘制 |
| `chain` | `(dur, items, heading, sub, seed, focus)` | 横向时间链 | `items=[{date,label,sub,hot,color}]`；日期与标签上下交替；**首尾节点标签自动左/右对齐**，避免被裁 |
| `stamp` | `(dur, emoji_path, emoji, text, sub, color, seed)` | 冲击卡 / 转场 | 大字 + emoji 砸下，适合章节之间的重音 |
| `quote` | `(dur, text, source, who, emoji_path, seed)` | 大字引言 | 左上 emoji + 引文 + 来源胶囊 + 补充行 |
| `end` | `(dur, title, lines, foot, seed)` | 片尾 | |

节点配色（`kind`）：`party=#FFD38A`（人/账号）、`doc=#58A6FF`（文档/记录）、`event=#3DDC97`（事件）、`conflict=#E5432D`（冲突）、`neutral=#8A96AB`。

## 证据场景（`tools/scenes3.py`）——主力

| 类型 | 签名 | 用途 | 要点 |
| --- | --- | --- | --- |
| `contradiction` | `(dur, left, right, heading, verdict, seed, warm)` | 两说直接冲突 | `left/right = {img:"图24", who:"标题", quote:"一句原话"}`；卡片高度按截图宽高比自适应（`clamp(cw/asp, 200, 430)`），中缝 VS 呼吸光，底部 `verdict` 是带问号的结论 |
| `wall` | `(dur, items, heading, sub, cols, seed, note)` | 一批证据压过来 | `items=[{img, label}]`，逐张飞入；10 张用 5 列 2 行；底部 `note` 写图号清单 |
| `flow` | `(dur, steps, heading, note, seed, vertical)` | 环节流程 | `steps=[{label, sub, kind}]`，`kind ∈ start/step/bad/good/end` 决定描边色；横排 3–6 步，>4 步自动收窄 |
| `web` | `(dur, url, title, lines, tag, seed, foot)` | 网页原话 | 浏览器窗口样式（红黄绿三灯 + 地址栏）；`lines` 行首写 `*` 即高亮为金色；**角标必须写明抓取日期** |
| `question` | `(dur, kicker, title, questions, foot, emoji, seed)` | 提问环节 | 巨型 🤔 + 呼吸环，问题逐条浮现；3–5 条最好，超过 5 条要拆镜 |
| `bigq` | `(dur, num, text, sub, ev, tag, seed, accent)` | 连发质问 | 左侧 250px 半透明编号水印 + 竖线 + 大号问句 + 左下证据角标 `ev` |
| `guess` | `(dur, index, guess, basis, seed)` | 只能猜不能定性 | 猜测标题 + 巨型问号水印 + 「依据：」一行；**没有依据就不要用这个场景** |

## 加一个新场景

四步，都在 `tools/scenes3.py` 里完成：

```python
class MyScene(Scene):
    def __init__(self, dur, heading="", seed=21, **kw):
        super().__init__(dur, seed, False)   # (dur, seed, grid)
        self.heading = heading

    def frame(self, t):
        img = self.bg.copy()                 # 背景已缓存：径向渐变 + 网格 + 颗粒
        p = ease_out(seg(t, 0.0, 0.45))      # 0→1 的入场进度
        put(img, text_img(self.heading, 46, TEXT, "bold"), 90, 120, "lt", p)
        img = glow_blob(img, ACC, 960, 620, 260, 0.10 * p)   # 呼吸光
        return vignette(img)                 # 暗角

TYPES["mine"] = MyScene
```

可用原语（`anim.py`）：

| 函数 | 作用 |
| --- | --- |
| `font(size, weight)` | 缓存字体（bold/regular/light） |
| `text_img(s, size, color, weight, stroke, spacing)` | 文字转图层，支持描边与字距 |
| `wrap_text / para / fit_line` | 断行、段落、自动缩字号 |
| `put(base, layer, x, y, anchor, alpha, scale)` | 九宫锚点贴图（`lt/mm/rb`…） |
| `new_layer / blur / glow` | 图层、模糊、发光 |
| `rrect / pill / dashed_line / arrow` | 圆角框、胶囊、虚线、箭头 |
| `backdrop(seed, grid, warm)` | 缓存背景 |
| `noise_tile / grain / vignette` | 颗粒与暗角 |
| `particles / draw_particles` | 粒子 |
| `seg(t, a, b)` | 把时间轴切成 0→1 区段（动画时序的基本单位） |
| `ease_out / ease_in_out / ease_out_back / ease_out_quint` | 缓动 |
| `emoji_img(v, size)` | 传路径→读 png；传字符→从 emoji 目录查 |
| `mark_icon(kind, size, color)` | 矢量画 ✓ / ✕ / ·（字体里没有这些字形） |

## 动效的三条原则

1. **一层一件事**：背景 → 呼吸光 → 主体 → 局部强调 → 颗粒/暗角。每层都从 `self.bg.copy()` 起，不要叠在上一帧上（会累积糊）。
2. **时序就是叙事**：`seg(t, a, b)` 的窗口按"谁先说话谁先出"排；两个元素相差 0.2–0.4 秒，观众才读得出先后。
3. **每帧都要有东西在动**，但只让一个东西动得明显：关系网的脉冲边、对照板的 VS 呼吸、质问卡的问号水印轻微缩放。全都在动 = 全都没动。

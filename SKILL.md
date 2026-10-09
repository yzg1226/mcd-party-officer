---
name: mcd-party-officer
agent_created: true
description: 麦当劳门店派对/包场/拼团的选址、成团调度与筹备助手。当用户想办生日派对、亲子派对、主题派对、品鉴会、读书会、麦麦体验营，或说「麦当劳派对」「派对拼团」「包场」「生日会怎么办」「哪家店能办派对」「还差几个人成团」「包场还是拼团划算」「帮我写拼团招募文案」「做一张派对邀请函」「孩子派对吃什么不超标」时使用。基于麦当劳官方 MCP（mcp.mcd.cn）的 party 系列工具：扫描全城场次、估算成团概率、对比包场与拼团成本、按官方营销活动日历挑最佳日期、审查儿童餐营养、生成招募卡与邀请函。
---

# 派对拼团官（McDonald's Party Officer）

麦当劳门店派对在 MCP 里是一条**完整但几乎无人使用**的业务线：城市 → 门店 → 可约日期 → 场次（含成团人数与余位）→ 下单，五个工具环环相扣。

本 Skill 不是"帮你订个派对"，而是**一整套派对决策系统**。官方规则写着两条关键约束：

- **拼团若未在截止前凑够人数会自动取消并退款**
- **需提前 3 天预订**

于是就产生了四个真实问题，也正是本 Skill 的四大能力：

| 问题 | 能力 | 用户会怎么问 |
|---|---|---|
| 哪家店、哪天、哪场我最可能凑满人？ | **成团概率雷达** | "6 个人能办成吗" |
| 包场还是拼团？哪个划算？ | **双模式成本对比** | "包场和拼团差多少钱" |
| 未来哪天办最值？ | **派对黄历** | "最近哪天办合适" |
| 孩子吃这些会不会钠/热量超标？ | **儿童营养安心指数** | "这个搭配健康吗" |

再加上三个**能直接拿去用**的产出物：**拼团招募卡**（发群）、**派对邀请函**（可分享 HTML）、**筹备时间线**（T-7→T 待办 + 预订截止倒计时）。

## When to use

- 选址与成团：「想给孩子办麦当劳生日会」「附近哪家店能办派对」「还差几个人成团」
- 决策：「包场还是拼团」「多少钱」「有没有余位」「最近哪天有活动」
- 健康：「开心乐园餐这套搭配适合小孩吗」「怎么换更健康」
- 传播：「帮我写个拼团招募文案」「做张派对邀请函发群里」
- 其它派对型商品：主题派对、麦麦体验营、品鉴会、读书会、积分兑换活动

## 八大能力总览

| # | 能力 | 函数 | 输入 → 输出 |
|---|---|---|---|
| 1 | 成团调度扫描 | `party_officer.plan` | 城市+商品+人数 → Top N / 最易成团 / 余位告急 |
| 2 | **成团概率雷达** | `party_plus.formation_radar` | 场次+人数 → 成团概率 % + 差几人 + 拉人话术 |
| 3 | **包场 vs 拼团** | `party_plus.compare_modes` | 场次+人数 → 两模式总价、确定性、推荐结论 |
| 4 | **派对黄历** | `party_plus.party_almanac` | 候选日期 → 逐日评分（活动/周末/余位/提前量） |
| 5 | **营养安心指数** | `party_plus.kids_nutrition_audit` | 餐单 → 逐项营养 + 评分 A/B/C + 替换建议 |
| 6 | **筹备时间线** | `party_plus.party_timeline` | 活动日 → T-7→T 待办 + 预订截止倒计时 |
| 7 | 招募卡 / 邀请函 | `render_recruit_card` / `render_invite_html` | 场次 → 可发群文本 / 可分享 HTML |
| 8 | 四宫格比选 | `party_plus.scout_grid` | 候选 → 最优综合/最省/最近/空位最多 |

## 派对业务关键规则（来自官方商品说明，务必向用户复述）

| 规则 | 内容 |
|---|---|
| 成团下限 | 包场 5 人起订；**拼团需超过 5 人**才可举办 |
| 成团上限 | 每场最高 12 人（含） |
| 加价 | 包场每增加 1 人 +¥50（以实际场次 price 字段为准） |
| 时长 | 约 90 分钟 |
| 预订提前量 | **需提前 3 天预订** |
| 拼团风险 | **未成团则预约自动取消并自动退款** |
| 退订 | 需在活动日前 3 天申请，当天缺席不退款 |
| 适用人群 | 多数生日派对商品面向 4–12 岁儿童（不同商品不同） |

> 价格、人数门槛、适用人群**因商品而异**，一律以 `mall-product-detail` 返回的 `note` 与 `skuList[].price` 为准。

## 执行流程

### 第 0 步：确定派对商品（spuId）
```
mall-points-products({"catRuleIds": "1>6>20"})   # 生日类派对
mall-points-products({"catRuleIds": "1>6>21"})   # 主题类派对
mall-points-products({"catRuleIds": "1>6>22"})   # 麦麦体验营
mall-points-products({"catRuleIds": "1>6>25"})   # 品鉴会
mall-points-products({"catRuleIds": "1>6>34"})   # 读书会
mall-points-products({"catRuleIds": "1>6>40"})   # 积分兑换活动
```
拿到 `spuId` 后，用 `mall-product-detail({"spuId": ...})` 读取 `skuList[].skuId`（下单必需）与 `note`。

### 第 1–4 步：扫描场次（核心）
```
query-party-city({"spuId": 1779})                       → 城市列表（code / 经纬度）
query-party-store({"code": "330100",                    → 可承办门店（含 distance / 营业状态）
                   "spuId": 1779,
                   "latitude": ..., "longitude": ...})
query-party-store-date({"spuId": 1779,                  → 可预约日期
                        "storeCode": "3330206"})
query-party-store-session({"spuId": 1779,               → 场次（时间/成团人数/价格/余位）
                           "storeCode": "3330206",
                           "dateStr": "2026-10-14"})
```

### 第 5 步：成团调度排序
对每个候选场次打分（`scripts/party_officer.py::score`），五维：成团可行性（硬约束）、余位紧张度、时段匹配、价格、距离。
输出三个视图：**推荐 Top N**、**最易成团**、**余位告急**。

### 第 6 步：下单（必须二次确认）
```
party-order-create({"partyType": 1,        # 1=包场，2=拼团
                    "spuId": 1779, "skuId": 2027,
                    "storeCode": "3330206", "code": "330100",
                    "dateStr": "2026-10-14",
                    "id": 36825489,        # 场次 id
                    "leftNum": 12, "count": 6})
```
**未经用户明确确认，禁止调用下单类工具。**

## 创意增强模块（差异化所在）

> 以下模块全部为**纯算法 + 官方数据**，不依赖模型猜测，结果可复现、可解释。

### ① 成团概率雷达 `formation_radar(date, sess, headcount)`
输出 `prob`(5~95%) / `level` / `gap`(还差几人) / `reasons`(逐条依据) / `pitch`(可直接发群的拉人话术)。

评分依据（透明可查）：是否达成团线（基础 68，每差 1 人 −11）／余位是否够用（+8 / +2 / −22）／筹备窗口（3–7 天 +10，≤2 天 −16）／周末 +7 ／晚市 +4。

### ② 包场 vs 拼团 `compare_modes(sess, headcount)`
给出两种模式的**总价、确定性、推荐结论**。要点：包场按 `max(人数, 起订数)` 计费换取"确定举办"；拼团按实际人数计费但承担未成团退款风险。同价时优先包场。

### ③ 派对黄历 `party_almanac(cli, dates, sessions_by_date, headcount)`
把 `campaign-calendar`（**markdown 文本，需 `raw_text=True` 解析**）的官方活动日与场次余位结合，逐日评分：
有官方活动 +18 ／周末 +12 ／余位充足 +10 ／满足提前 3 天 +8 ／不满足 −30。
输出 `宜 / 可 / 忌` 与"当月有活动的日期"清单。

### ④ 儿童营养安心指数 `kids_nutrition_audit(cli, combo)`
数据源 `list-nutrition-foods`（**158 个餐品的表格文本，藏在 JSON 的 `data` 字段里**，需二次解析）。
对一份餐单算合计热量/脂肪/钠/碳水，按**超出参考上限的比例**扣分，给 A/B/C 评级，并自动给出替换建议（如「中薯条→小薯条 = 钠 −45mg、热量 −79kcal」）。
> 参考区间为儿童单餐：热量 400–700 kcal、钠 ≤800 mg、脂肪 ≤26 g。**这是本模块唯一的硬编码标准，需向用户说明是参考值而非官方结论。**

### ⑤ 筹备时间线 `party_timeline(date)`
输出 T-7 → T 日待办与**预订截止倒计时**（截止日 = 活动日 − 3 天），并在 ≤3 天时给出强提醒。

### ⑥ 招募卡 / 邀请函
- `render_recruit_card(...)` → 带余位进度条的群消息文本
- `render_invite_html(...)` → 麦当劳红黄配色的单文件邀请函（浅色、可直接分享）

### ⑦ 四宫格比选 `scout_grid(ranked)`
一屏给出：**最优综合 / 最省人均 / 最近门店 / 空位最多**。

## 输出规范

给用户的最终答复建议为四段：

1. **商品与规则**：派对名称、人均价、成团区间、提前预订天数、适用人群
2. **推荐场次表**：`门店 | 日期 | 时段 | 人均 | 余位 | 成团概率 | 推荐理由`
3. **决策建议**：包场还是拼团 + 最佳日期 + 筹备截止提醒
4. **可复制产出**：招募卡文本（或邀请函文件路径）+ 是否代下单的确认问句

金额一律显示为「元」（接口单位为**分**，需 `/100`）。

## 代码入口

```bash
export MCD_MCP_TOKEN=<your_token>          # https://open.mcd.cn/mcp 免费领取
python scripts/demo.py                       # 基础演示（成团调度）
python scripts/demo_plus.py                  # 创意增强演示（八大能力全量）
```

```python
from scripts.party_officer import plan
from scripts.party_plus import formation_radar, compare_modes, party_almanac, \
     kids_nutrition_audit, party_timeline, render_recruit_card, render_invite_html, scout_grid

res = plan("杭州市", 1779, headcount=6, budget=60, prefer_time="dinner")
top = res["best"][0]
radar = formation_radar(top["date"], top["sess"], 6)     # 成团概率
modes = compare_modes(top["sess"], 6)                    # 包场 vs 拼团
audit = kids_nutrition_audit(cli, ["吉士汉堡包", "中薯条", "可乐中杯"])  # 营养
```

- `scripts/mcd_client.py` —— MCP 通用客户端（35 工具，仅标准库）
- `scripts/party_officer.py` —— 扫描 + 五维成团调度评分
- `scripts/party_plus.py` —— 七个创意增强模块
- `references/party_flow.md` —— 链路详解与字段字典
- `references/tools.md` —— 全量工具速查

## 边界与注意事项

- **只读优先**：除 `party-order-create` 外全部为只读调用，可放心批量扫描。
- **两种响应格式**：多数工具返回 JSON（用 `extract_json` 解析）；`campaign-calendar` 与 `list-nutrition-foods` 返回**文本/表格**，需 `raw_text=True` 或取 `data` 字段后二次解析。
- **团餐接口不稳**：`query-meals` / `query-promotions` 依赖门店营业状态，非营业时段会返回「门店可能已关闭或不在营业时间」，不要作为核心链路依赖。
- **城市匹配**：`query-party-city` 返回全国城市，按名称宽松匹配（"杭州" 可命中 "杭州市"）。
- **门店筛选**：只保留 `businessStatus == 1` 且 `onlineBusinessStatus == true` 的门店。
- **限流**：单 Token 600 请求/分钟；扫描请求数 = 门店数 × 日期数，建议 `max_stores ≤ 8`、`max_dates ≤ 3`。
- **Token 安全**：只从环境变量读取，不要写入代码或提交到仓库。

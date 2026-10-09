# MCP 接入说明 · MCP_INTEGRATION

本项目基于麦当劳中国官方 MCP 服务构建，以下是实际接入信息、使用的工具、调用流程与业务价值。

## 一、MCP Server 接入信息

| 项目 | 值 |
|---|---|
| 服务提供方 | 麦当劳中国（官方 MCP 服务） |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 消息格式 | JSON-RPC 2.0 |
| 协议版本 | `2025-06-18` |
| 鉴权方式 | 请求头 `Authorization: Bearer <MCP_TOKEN>` |
| Token 获取 | <https://open.mcd.cn/mcp>（手机号登录 → 控制台 → 激活） |
| 限流 | 每个 Token 每分钟 600 次请求，超限返回 `429` |

**已脱敏的接入配置见 [`mcp-config.example.json`](mcp-config.example.json)，仅使用环境变量占位符，不含任何真实凭证。**

## 二、实际使用的 MCP Tool

本项目实际调用 **10 个**官方 Tool，按业务分组：

### 1. 派对主线（核心依赖）

| Tool | 用途 | 关键返回字段 |
|---|---|---|
| `mall-points-products` | 查询商城派对类商品（生日派对 / 主题派对 / 麦麦体验营 / 品鉴会 / 读书会） | `spuId` |
| `mall-product-detail` | 读取商品详情与业务规则 | `skuList[].skuId`、`note`（成团人数、加价、适用年龄） |
| `query-party-city` | 查询可承办派对的**城市** | `code`、`name`、`latitude`、`longitude` |
| `query-party-store` | 查询该城市可承办派对的**门店** | `code`、`shortName`、`distance`、`businessStatus` |
| `query-party-store-date` | 查询门店**可预约日期** | `date` |
| `query-party-store-session` | 查询某日**场次** | `id`、`timeStart`、`partyMin`、`partyMax`、`price`、`leftNum` |
| `party-order-create` | 创建派对订单（包场 `partyType=1` / 拼团 `partyType=2`） | 订单信息 |

> **写操作门控**：`party-order-create` 是本项目唯一的下单接口，**必须经用户明确二次确认**后才会调用，默认只输出建议不代下单。

### 2. 决策增强

| Tool | 用途 |
|---|---|
| `campaign-calendar` | 读取官方营销活动日历 → 用于「派对黄历」择日（该工具返回 **markdown 文本**，非 JSON） |
| `list-nutrition-foods` | 读取 158 个餐品的营养数据（能量/蛋白/脂肪/碳水/钠/钙）→ 用于「儿童营养安心指数」 |
| `now-time-info` | 取官方服务器时间 → 用于预订截止倒计时与场次倒计时（避免本地时区偏差） |

## 三、调用流程

### 主链路：从"想办派对"到"锁定场次"

```
① mall-points-products(catRuleIds=1>6>20 等)
        │  选定派对商品，拿到 spuId
        ▼
② mall-product-detail(spuId)
        │  读取 skuId（下单必需）与 note（成团人数 / 加价 / 适用年龄等业务规则）
        ▼
③ query-party-city(spuId)
        │  城市列表 → 按名称宽松匹配（"杭州" 命中 "杭州市"）
        ▼
④ query-party-store(code=城市码, spuId, latitude, longitude)
        │  门店列表 → 过滤停业 / 未上线 → 按 distance 升序
        ▼
⑤ query-party-store-date(spuId, storeCode)
        │  可预约日期（滚动窗口）
        ▼
⑥ query-party-store-session(spuId, storeCode, dateStr)
        │  场次明细：班次时间 / 成团人数区间 / 人均价 / 剩余余位
        ▼
⑦ 本地算法层（不消耗接口配额）
        ├─ 五维成团调度评分     → 推荐 Top N / 最易成团 / 余位告急
        ├─ 成团概率雷达         → 成团概率 % + 差几人 + 拉人话术
        ├─ 包场 vs 拼团对比     → 总价 / 确定性 / 推荐结论
        ├─ 派对黄历             → 结合 campaign-calendar 择日
        ├─ 儿童营养安心指数     → 结合 list-nutrition-foods 评分
        ├─ 筹备时间线           → 结合 now-time-info 计算预订截止倒计时
        └─ 招募卡 / 邀请函      → 可发群文本 / 可分享 HTML
        ▼
⑧ party-order-create（需用户二次确认）
```

### 并行支线

```
campaign-calendar ─┐
                   ├─→ 派对黄历（宜 / 可 / 忌）
场次余位数据 ───────┘

list-nutrition-foods ─→ 儿童营养安心指数（评分 + 替换建议）

now-time-info ────────→ 预订截止倒计时（活动日 − 3 天）
```

## 四、业务价值

| 维度 | 价值 |
|---|---|
| **解决真实痛点** | 派对的核心风险是「拼团未成团会自动取消并退款」。本项目把这个风险量化为**成团概率**，让用户在下单前就能判断这场靠不靠谱 |
| **降低决策成本** | 原来要一家家打电话问门店，现在一次扫描全城可约场次并排序 |
| **减少退款与空场** | 通过余位紧张度、筹备窗口、成团人数约束的多维评估，降低选错场次的概率 |
| **提升转化** | 招募卡与邀请函直接解决"拉人"环节，把决策转成行动 |
| **健康侧补充** | 儿童餐单的钠/热量/脂肪多约束评估与自动替换建议 |
| **接口用量友好** | 扫描期只读；所有算法在本地计算，不额外消耗接口配额 |

## 五、工程注意事项（实测沉淀）

| 事项 | 说明 |
|---|---|
| **金额单位** | 场次 `price` 单位为**分**（¥50 → 5000），展示时 `/100` |
| **响应格式不统一** | 多数工具返回 JSON（首部带字段说明 markdown）；`campaign-calendar` 返回**纯 markdown**；`list-nutrition-foods` 的表格**藏在 JSON 的 `data` 字符串字段里** |
| **门店营业状态** | 点餐类工具（`query-meals` / `query-promotions`）在非营业时段返回 `code=600057`，不宜作为核心链路依赖 |
| **只读工具可批量** | 除 `party-order-create` 外均为只读；扫描请求数 = 门店数 × 日期数，建议单次 `门店 ≤ 8`、`日期 ≤ 3` |
| **城市名匹配** | 接口返回全称（杭州市），用户常传简称（杭州），需宽松匹配 |
| **门店过滤** | 仅保留 `businessStatus == 1` 且 `onlineBusinessStatus == true` |

## 六、合规声明

- 本项目的 MCP Token 仅从环境变量读取，**不写入代码、不提交仓库**
- 项目仅使用官方 MCP 公开能力，未对接口进行反向工程或绕过
- 项目输出为决策参考，不构成医疗、营养或专业建议

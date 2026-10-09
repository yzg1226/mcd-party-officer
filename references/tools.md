# 麦当劳 MCP 工具速查

共 **35** 个工具（2026-10-09 实测）。金额字段单位为**分**，显示时 `/100`。

## 派对 / 活动预订（本 Skill 主角）

- `query-party-city` — Description: 活动派对商品配置场次城市列表, 必须先确定spuId(从 mall-points-products 获取）或查询商品详情（从 mall-product-detail 获取) When： - 用户询问"主题派对在哪些…  **必填**: `spuId`
- `query-party-store` — Description: 查询指定城市下支持主题派对的门店列表。  **必填**: `code`
- `query-party-store-date` — Description: 查询指定门店支持生日类派对/主题类派对/麦麦体验营/品鉴会/读书会/积分兑换活动的可预约日期列表。  **必填**: `spuId`, `storeCode`
- `query-party-store-session` — Description: 查询指定门店、指定日期下的生日类派对/主题类派对/麦麦体验营/品鉴会/读书会/积分兑换活动场次列表。  **必填**: `spuId`, `storeCode`, `dateStr`
- `party-order-create` — Description: 创建生日类派对/主题类派对/麦麦体验营/品鉴会/读书会/积分兑换活动, 仅支持shopId=5（从 mall-product-detail 获取）的调用， 支持包场(partyType=1)、拼团(partyTyp…  **必填**: `partyType`
- `campaign-calendar` — 查询麦当劳中国当月的营销活动日历，返回进行中、往期和未来日期的活动。

## 积分商城 / 派对商品

- `mall-points-products` — 查询可兑换餐品券列表 - 当用户询问"有哪些积分兑换商品"、"积分可以兑换什么"、"查看积分商城"时使用 支持类目规则筛选：商品券(1>4)、实物商品(2)、周边产品(2>8)、实物礼品卡(2>9)、生日类派对(1>6>20)、主题类派对(…
- `mall-product-detail` — 查询积分兑换商品详情 - 当用户询问"这个商品详情是什么"、"查看商品详细信息"、用户点击商品查看详情时使用 返回商品的所有SKU规格信息，用户需要选择具体SKU后才能下单兑换 前提条件： - 已知商品SPU ID，需要从查询可兑换餐品券列…  **必填**: `spuId`
- `mall-create-order` — 创建积分兑换订单，仅支持shopId=2（从 mall-product-detail 获取） - 当用户询问"用积分兑换这个商品"、"兑换这个券"、用户确认兑换商品时使用,切记：如果单个商品一个订单下单；如果用户需要兑换多个商品‘必须’分别…  **必填**: `skuId`, `spuCategory`
- `mall-order-list` — Description: 查询麦麦商城订单列表 When： - 用户询问"查看我的麦当劳商城订单列表"
- `mall-order-detail` — Description: 查询麦麦商城订单详情 When： - 用户询问"麦麦商城的订单详情" Next: - 引导用户："您可以打开麦当劳APP查看凭证等其他信息"  **必填**: `orderId`
- `query-my-account` — 查询用户积分账户详情 - 当用户询问"我有多少积分"、"查下我的积分"、"积分余额"、"查询过期积分"时使用

## 积分抽奖

- `query-lottery-info` — Description: 查看当前积分抽奖活动信息，包括活动基本信息、抽奖消耗规则、单次所需积分、剩余可抽次数、当前可用积分与公开奖品列表，不执行抽奖。
- `draw-lottery` — Description: 使用后台配置的抽奖消耗规则参加一次当前积分抽奖并返回结果，服务端原子完成次数或积分扣减与抽奖。
- `query-my-prizes` — Description: 查询当前登录会员通过积分抽奖获得的本期及历史奖品（可用/已使用/已过期/已领取/已失效）。

## 点餐 · 门店 · 菜单

- `query-nearby-stores` — Description: 到店场景下，查询用户可点餐门店，需要用户明确是到店自取还是车道取餐 - beType=1(到店自提): 返回的门店无 beCode，后续工具调用不传 beCode - beType=5(得来速): 返回的门店有 b…  **必填**: `beType`, `searchType`
- `delivery-query-stores` — Description: 外送场景下，用户选择完地址后，需要根据地址ID，查询用户当前地址可配送的门店 When: - 外送场景下，用户选择完配送地址后 - 用户问"这个地址能送到哪些店" 注意：到店场景请使用 query-nearby-s…  **必填**: `beType`, `addressId`
- `delivery-query-addresses` — Description: 外送场景下，查询用户配送地址列表 When： - 用户想点麦乐送 - 用户想吃麦当劳，并配送到家 - 我想点团餐 Next： - 1:引导用户创建新的配送地址 - 2:当用户选择企业团餐时，需要引导用户提供预算金额…
- `delivery-create-address` — Description: 创建用户配送地址 When： - 用户想添加新的配送地址 Input: - city: 城市名称，必填，必须从用户输入中获取实际城市名称，如"南京市" - contactName: 联系人姓名，必填，必须从用户输入…  **必填**: `address`, `addressDetail`, `city`, `contactName`, `phone`
- `query-meals` — Description: 餐品列表, 支持到店自提(orderType=1)和外送(orderType=2)两种场景 企业团餐场景下，可按照这个规则给用户进行搭配 - **20元以下**: 小食 - **20-30元**：汉堡+小食 或 汉…  **必填**: `storeCode`, `orderType`, `beType`
- `query-meal-detail` — Description: 餐品详情, 支持到店自提(orderType=1)和外送(orderType=2)两种场景 When: - 用户想要了解餐品有哪些组成 - 用户想要更换套餐的组成或者更换特制商品 Input: - storeCod…  **必填**: `storeCode`, `orderType`, `beType`, `code`
- `calculate-price` — Description: 计算商品的价格（含优惠），支持到店自提(orderType=1)和外送(orderType=2)两种场景 When： - 用户问"这些商品多少钱" - 用户问"总价是多少" Input: - reservation…  **必填**: `storeCode`, `orderType`, `beType`
- `create-order` — Description: 创建麦当劳订单，支持到店(orderType=1)和外送(orderType=2)两种场景下单, 必须先确定订单类型，必填 (1：到店，2外送) When： - 用户说"我要下单" - 用户说"创建订单" Inpu…  **必填**: `storeCode`, `orderType`, `beType`

## 企业团餐（beType=6）

- `query-promotions` — Description: 查询当前门店企业团餐场景下可用的促销规则（满减/满折），仅返回当前时间有效且适用在售餐品的规则原始数据 When： - 企业团餐场景(beType=6)下，用户搭配方案前需要了解当前门店有哪些可用的促销活动/满减满…  **必填**: `storeCode`, `orderType`, `beType`
- `query-meal-assistance` — Description: 仅支持企业团餐场景(beType=6)在calculate-price前需要获取当前门店可用的助餐服务 When： - 企业团餐场景(beType=6)下，用户选完商品后、计算价格前 - 用户问"有什么助餐服务"、…  **必填**: `storeCode`

## 优惠券

- `available-coupons` — 查询用户当前可领取的麦麦省的优惠券列表。
- `auto-bind-coupons` — 自动领取麦麦省所有当前可用的麦当劳优惠券。
- `query-my-coupons` — 获取用户卡包中的优惠券资产信息，用于“我有什么券 / 券详情查看”等展示与管理场景。
- `query-store-coupons` — Description: 查询【指定门店+订单类型】下可使用的优惠券，支持到店(orderType=1,含到店自取和得来速)和外送(orderType=2,含麦乐送和团餐) When： - 当用户已获取到门店时，用户询问"我有什么优惠券可以…  **必填**: `orderType`, `beType`, `storeCode`

## 订单与售后

- `order-list` — Description: 查询麦当劳历史订单，非商城订单，商城订单需要使用mall-order-list When： - 用户询问"帮我查询一下历史订单" - 用户询问"我买了什么麦当劳餐品"
- `query-order` — Description: 查询订单详细信息 When： - 用户询问"查下订单详情"、"订单状态"、"我的订单" - 用户提供了麦当劳订单编号想查询配送进度 - 用户说我已支付或者支付失败时，查询一下最新的订单状态  **必填**: `orderId`
- `cancel-order` — Description: 取消订单，非商城订单 When： - 用户说"取消订单"、"我要取消" - 用户说"帮我取消一下订单" Input: - cancelReasonCode: 取消原因code，必填，可选值：1=改主意了, 2=重复…  **必填**: `orderId`, `cancelReasonCode`
- `query-survey-coupon` — Description: 按订单号查询当前 MCP 用户本人订单的 CSAT 满意度答卷，并返回该订单关联奖券的标题、核销时间、核销状态和点餐方式。  **必填**: `orderId`

## 其他

- `list-nutrition-foods` — 获取麦当劳常见餐品的营养成分数据，包括能量、蛋白质、脂肪、碳水化合物、钠、钙等信息，当用户咨询麦当劳餐品的热量、营养，帮助用户搭配指定热量套餐时有用
- `now-time-info` — 获取当前时间信息 - 返回当前服务器的完整时间信息，包括： - 时间戳（毫秒级） - 格式化的日期时间 - 年月日信息 - 时区和UTC时间 在你不知道当前时间，并且用户需要指定日期查询活动日历的时候有用

## ⚠️ 响应格式陷阱（实测）

| 工具 | 返回形态 | 解析方式 |
|---|---|---|
| 多数工具 | JSON（首部带字段说明 markdown，后跟 JSON） | `extract_json()`：从 `{"success"` / `{"code"}` / `{"data"` 处 `raw_decode` |
| `campaign-calendar` | **纯 markdown 文本**（无 JSON） | 必须 `raw_text=True`，再正则提取 `#### YYYY年M月D日` 与 `**活动标题**：` |
| `list-nutrition-foods` | JSON，**但表格内容在 `data` 字符串里**（形如 `[158]{productName,energyKcal,...}:\n  名称,null,...`） | 取 `data` 后按行 `split(",")` 解析 |
| `query-meals` / `query-promotions` | JSON，但**依赖门店营业状态** | 非营业时段返回 `code=600057 门店可能已关闭或不在营业时间` |


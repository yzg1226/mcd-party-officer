# 派对业务链路详解

> 全部字段与示例均来自 2026-10-09 真实接口实测（杭州市）。

## 一、五步链路

```
① mall-points-products / mall-product-detail
   └─ 选商品：拿到 spuId、skuId、price、note（业务规则）
                │
② query-party-city(spuId)
   └─ 全国可办城市：code / name / latitude / longitude
                │
③ query-party-store(code=城市code, spuId, latitude, longitude)
   └─ 该城市可承办门店：code / shortName / distance / businessStatus
                │
④ query-party-store-date(spuId, storeCode)
   └─ 可预约日期：["2026-10-14", "2026-10-15", ...]
                │
⑤ query-party-store-session(spuId, storeCode, dateStr)
   └─ 场次：id / timeStart / timeEnd / partyMin / partyMax / price / leftNum
                │
⑥ party-order-create(partyType, spuId, skuId, storeCode, code, dateStr, id, count, leftNum)
   └─ partyType: 1=包场, 2=拼团     ⚠️ 写操作，需用户明确确认
```

## 二、字段字典

### query-party-city
| 字段 | 含义 |
|---|---|
| `code` | 城市编码（如杭州 330100），后续 `query-party-store` 作为 `code` 传入 |
| `name` | 城市名称 |
| `latitude` / `longitude` | 城市中心经纬度，用于计算门店距离 |

### query-party-store
| 字段 | 含义 |
|---|---|
| `code` | **门店编码**，后续所有门店级调用都用它 |
| `shortName` | 门店简称（展示用） |
| `distance` | 距离（**米**），已按此升序 |
| `businessStatus` | 1 = 营业中 |
| `onlineBusinessStatus` | 是否线上可订 |

### query-party-store-session（核心）
| 字段 | 含义 |
|---|---|
| `id` | **场次 id**，下单必传 |
| `timeStart` / `timeEnd` | 场次时段（实测为 12:00–13:30 与 18:30–20:00 两档） |
| `partyMin` | **最小成团人数**（实测 5） |
| `partyMax` | **最大成团人数**（实测 12） |
| `price` | 人均价（**分**，实测 5000 → ¥50） |
| `leftNum` | **剩余余位**（实测 12 = 全场空位） |

## 三、实测样例（杭州 · spuId 1779 麦当劳奇妙生日派对）

```json
{
  "id": 36825489,
  "timeStart": "12:00", "timeEnd": "13:30",
  "partyMin": 5, "partyMax": 12,
  "price": 5000, "leftNum": 12
}
```

杭州共 **60 家**门店可承办该派对；单店单日通常 2 个场次。

## 四、业务规则（来自 mall-product-detail 的 note）

- 包场：**5 人起订**，每增加 1 人 +¥50，单场最高 12 人
- 拼团：**需超过 5 人**才可举办；**未成团则预约自动取消并自动退款**
- 时长约 90 分钟；**需提前 3 天预订**
- 退订需在活动日前 3 天申请，缺席不退款
- 生日派对多面向 **4–12 岁儿童**，每位含 1 份开心乐园餐 + 3 个派对礼品

> 不同 spuId 的规则不同（如主题派对、品鉴会、读书会），**一律读取该商品的 note**，不要套用固定值。

## 五、常见坑

1. **`beCode` 陷阱**：团餐（beType=6）与麦乐送（beType=2）的 `beCode` 不同（实测同一门店分别为 `333013781` / `333013702`），跨业务类型不可混用。派对链路**不使用** `beCode`。
2. **城市名匹配**：接口返回 `杭州市`，用户常说 `杭州`，需宽松匹配。
3. **停业门店**：必须过滤 `businessStatus != 1` 的门店。
4. **请求量控制**：扫描请求数 = 门店数 × 日期数，单 Token 限 600/分钟。
5. **不要自行推算价格**：一律用场次 `price` 字段，加价规则以商品 note 为准。

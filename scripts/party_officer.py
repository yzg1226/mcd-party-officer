"""
派对拼团官 · 核心引擎

链路（全部为麦当劳 MCP 真实工具）：
    query-party-city          → 城市（拿 code / 经纬度）
    query-party-store         → 可承办派对的门店（含距离 / 营业状态）
    query-party-store-date    → 门店可预约日期
    query-party-store-session → 场次（时间 / 成团人数 / 价格 / 余位）
    party-order-create        → 下单（包场 partyType=1 / 拼团 partyType=2）

本模块只做「扫描 + 成团调度评分」，不自动下单。
"""

from mcd_client import McDClient

LUNCH_CUTOFF = "15:00"   # 早于该时刻算午市，否则算晚市


# --------------------------------------------------------------------------
# 1. 数据获取
# --------------------------------------------------------------------------
def find_city(cli, spu_id, city_name):
    """按城市名匹配 query-party-city 返回的城市（宽松匹配）。"""
    data = (cli.call("query-party-city", {"spuId": spu_id}) or {}).get("data") or []
    key = city_name.rstrip("市")
    for c in data:
        if c.get("name") == city_name:
            return c
    for c in data:
        if key and key in (c.get("name") or ""):
            return c
    return None


def list_stores(cli, spu_id, city, limit=8):
    """该城市可承办该派对的门店，按距离升序；过滤停业 / 未上线门店。"""
    payload = {
        "code": str(city["code"]),
        "spuId": spu_id,
        "latitude": city.get("latitude"),
        "longitude": city.get("longitude"),
    }
    stores = (cli.call("query-party-store", payload) or {}).get("data") or []
    alive = [s for s in stores
             if s.get("businessStatus") == 1 and s.get("onlineBusinessStatus")]
    alive.sort(key=lambda s: s.get("distance") or 9e9)
    return alive[:limit]


def list_dates(cli, spu_id, store_code, limit=3):
    """门店可预约日期（取最近的 limit 个）。"""
    payload = {"spuId": spu_id, "storeCode": store_code}
    data = (cli.call("query-party-store-date", payload) or {}).get("data") or []
    return [d["date"] for d in data][:limit]


def list_sessions(cli, spu_id, store_code, date_str):
    """某门店某天的场次列表。"""
    payload = {"spuId": spu_id, "storeCode": store_code, "dateStr": date_str}
    return (cli.call("query-party-store-session", payload) or {}).get("data") or []


# --------------------------------------------------------------------------
# 2. 扫描 + 评分（成团调度器）
# --------------------------------------------------------------------------
def scan(cli, spu_id, city, headcount=6, budget=None, prefer_time=None,
         max_stores=6, max_dates=3, verbose=False):
    """
    扫描一座城市全部可约场次。

    返回候选列表：[{store, date, sess}, ...]
    """
    stores = list_stores(cli, spu_id, city, max_stores)
    if verbose:
        print("[扫描] 城市 %s：可承办门店 %d 家" % (city.get("name"), len(stores)))

    candidates = []
    for s in stores:
        dates = list_dates(cli, spu_id, s["code"], max_dates)
        for d in dates:
            for sess in list_sessions(cli, spu_id, s["code"], d):
                candidates.append({"store": s, "date": d, "sess": sess})
        if verbose:
            print("  - %s（%s，%s）-> %d 个日期" %
                  (s.get("shortName"), s.get("distanceText"), s["code"], len(dates)))
    return candidates


def score(cand, headcount, budget=None, prefer_time=None):
    """
    为单个场次打分（越高越好）；不满足硬约束返回 (None, 原因)。

    五个维度：
      1. 成团可行性（人数是否落在 partyMin~partyMax）
      2. 余位紧张度（leftNum 与需求人数的关系）
      3. 时间匹配（午市 / 晚市偏好）
      4. 价格（人均 vs 预算）
      5. 距离
    """
    sess = cand["sess"]
    store = cand["store"]
    pmin = sess.get("partyMin") or 0
    pmax = sess.get("partyMax") or 999
    left = sess.get("leftNum") or 0
    price = (sess.get("price") or 0) / 100.0          # 分 -> 元/人
    start = sess.get("timeStart") or ""
    dist = (store.get("distance") or 0) / 1000.0

    reasons = []
    s = 100.0

    # 1) 成团可行性 —— 硬约束
    if headcount > pmax:
        return None, ["超出该场次最大成团人数 %d" % pmax]
    if headcount < pmin:
        gap = pmin - headcount
        s -= 25 + gap * 6
        reasons.append("还差 %d 人成团（%d 人起拼）" % (gap, pmin))
    else:
        s += 6
        reasons.append("%d 人正好落在 %d~%d 成团区间" % (headcount, pmin, pmax))

    # 2) 余位紧张度
    if left < headcount:
        s -= 30
        reasons.append("余位仅 %d，不足以容纳 %d 人" % (left, headcount))
    elif left - headcount <= 2:
        s -= 8
        reasons.append("仅剩 %d 位，建议尽快锁定" % left)
    else:
        s += 4
        reasons.append("余位充足（剩 %d）" % left)

    # 3) 时间匹配
    is_lunch = start < LUNCH_CUTOFF
    if prefer_time == "lunch":
        s += 12 if is_lunch else -12
        reasons.append("符合午市偏好" if is_lunch else "非午市场次")
    elif prefer_time == "dinner":
        s += 12 if not is_lunch else -12
        reasons.append("符合晚市偏好" if not is_lunch else "非晚市场次")
    elif not is_lunch:
        s += 3   # 无偏好时略偏向晚市（生日会通常晚上）

    # 4) 价格
    if budget:
        if price <= budget:
            s += 8
            reasons.append("人均 ¥%.0f，在预算 ¥%.0f 内" % (price, budget))
        else:
            s -= (price - budget) * 1.0
            reasons.append("人均 ¥%.0f，超预算 ¥%.0f" % (price, price - budget))

    # 5) 距离
    if dist:
        s -= dist * 1.2
        reasons.append("距你 %.1f km" % dist)

    return s, reasons


def rank(candidates, headcount, budget=None, prefer_time=None, topk=5):
    """对所有候选场次评分并排序，返回 Top K。"""
    scored = []
    for c in candidates:
        sc, reasons = score(c, headcount, budget, prefer_time)
        if sc is None:
            continue
        item = dict(c)
        item["score"] = round(sc, 1)
        item["reasons"] = reasons
        scored.append(item)
    scored.sort(key=lambda x: -x["score"])
    return scored[:topk]


# --------------------------------------------------------------------------
# 3. 两个特色视图
# --------------------------------------------------------------------------
def easiest_to_form(ranked):
    """最容易成团：需要补的人数最少（partyMin - headcount 最小）。"""
    need = lambda r: max(0, (r["sess"].get("partyMin") or 0))
    return sorted(ranked, key=need)


def most_urgent(ranked):
    """余位告急：leftNum 最小（最可能被别人抢走）。"""
    return sorted(ranked, key=lambda r: (r["sess"].get("leftNum") or 0))


# --------------------------------------------------------------------------
# 4. 一站式入口
# --------------------------------------------------------------------------
def plan(city_name, spu_id, headcount=6, budget=None, prefer_time=None,
         max_stores=6, max_dates=3, topk=5, cli=None, verbose=False):
    """
    输入一个派对诉求，返回成团调度方案。

    返回：{"city":..., "spuId":..., "headcount":..., "candidates":N,
           "best":[...], "easiest":[...], "urgent":[...]}
    """
    cli = cli or McDClient()
    city = find_city(cli, spu_id, city_name)
    if not city:
        raise ValueError("未找到城市：%s" % city_name)

    cands = scan(cli, spu_id, city, headcount, budget, prefer_time,
                 max_stores=max_stores, max_dates=max_dates, verbose=verbose)
    ranked = rank(cands, headcount, budget, prefer_time, topk=topk)

    return {
        "city": city,
        "spuId": spu_id,
        "headcount": headcount,
        "candidates": len(cands),
        "best": ranked,
        "easiest": easiest_to_form(ranked)[:3],
        "urgent": most_urgent(ranked)[:3],
    }

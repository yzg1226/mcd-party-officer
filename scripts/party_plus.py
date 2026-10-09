"""
派对拼团官 · 创意增强模块（Party Plus）
=========================================

在「成团调度」之外，再叠加七个差异化的决策 / 健康 / 传播模块。
这些模块共同构成别的点餐类 Skill 没有的东西：

  1. formation_radar        成团概率雷达 —— 把「未成团自动退款」的风险变成可读数字
  2. compare_modes          包场 vs 拼团 成本与确定性对比 —— 找出人数临界点
  3. party_almanac          派对黄历 —— 结合官方营销活动日历，算未来哪天办最值
  4. kids_nutrition_audit   儿童营养安心指数 —— 多约束评分 + 自动替换建议
  5. party_timeline         派对筹备时间线 —— T-7 → T 日待办 + 预订截止倒计时
  6. render_recruit_card    拼团招募卡（文本）—— 一键发群
  7. render_invite_html     派对邀请函（可分享 HTML）
  8. scout_grid             全城四宫格比选（最省 / 最近 / 最易成团 / 最空）

除营养评分标准外，所有业务阈值（成团人数、价格、余位）均来自接口实时数据。
"""

from datetime import date as _date

LUNCH_CUTOFF = "15:00"
WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


# ==========================================================================
# 0. 小工具
# ==========================================================================
def _parse_date(s):
    y, m, d = [int(x) for x in s.split("-")]
    return _date(y, m, d)


def _fmt_date(s):
    d = _parse_date(s)
    return "%s %s" % (s, WEEKDAY_CN[d.weekday()])


def today_from(cli=None):
    """取"官方服务器当天"；失败回退本机日期。"""
    if cli is not None:
        try:
            o = cli.call("now-time-info", {})
            ds = (o or {}).get("data") or o or {}
            for k in ("date", "dateStr", "currentDate"):
                if isinstance(ds, dict) and ds.get(k):
                    return _parse_date(str(ds[k])[:10])
        except Exception:
            pass
    return _date.today()


# ==========================================================================
# 1. 成团概率雷达
# ==========================================================================
def formation_radar(date_str, sess, headcount, today=None):
    """
    估算这一场次的成团概率（5%~95%）。

    权重设计（可解释、可复现，非模型猜测）：
      · 是否已达成团线          基础分 68 / 每差 1 人 -11
      · 余位是否够用            充足 +8 / 勉强 +2 / 不足 -22
      · 筹备窗口（距活动日天数） 3~7 天 +10（拉人黄金期）/ ≤2 天 -16
      · 周末                      +7（客流旺，散客更易拼上）
      · 晚市 / 下午场              +4 / +1
    """
    today = today or _date.today()
    d = _parse_date(date_str)
    days = (d - today).days

    pmin = sess.get("partyMin") or 5
    pmax = sess.get("partyMax") or 12
    left = sess.get("leftNum") or 0
    start = sess.get("timeStart") or ""

    if headcount > pmax:
        return {"prob": 0, "level": "不可行", "gap": 0, "days_ahead": days,
                "reasons": ["需求 %d 人超出该场次上限 %d 人" % (headcount, pmax)]}

    reasons = []
    gap = max(0, pmin - headcount)

    if gap == 0:
        p = 68
        reasons.append("已达 %d 人成团线" % pmin)
    else:
        p = 46 - gap * 11
        reasons.append("还差 %d 人才到 %d 人成团线" % (gap, pmin))

    if left >= headcount + 3:
        p += 8
        reasons.append("余位充足（剩 %d）" % left)
    elif left >= headcount:
        p += 2
    else:
        p -= 22
        reasons.append("余位仅 %d，容纳不下 %d 人" % (left, headcount))

    if days < 0:
        p -= 40
        reasons.append("该日期已过")
    elif days <= 2:
        p -= 16
        reasons.append("距活动仅 %d 天，拉人窗口很紧" % days)
    elif days <= 7:
        p += 10
        reasons.append("筹备期 %d 天，正是拉人黄金窗口" % days)
    elif days <= 14:
        p += 5
        reasons.append("筹备期 %d 天，时间充裕" % days)
    else:
        p -= 3

    if d.weekday() >= 5:
        p += 7
        reasons.append("周末场次，客流旺更易拼成")
    if start >= "17:00":
        p += 4
        reasons.append("晚市场次热度高")

    p = max(5, min(95, int(round(p))))
    level = ("高，可放心订" if p >= 80 else
             "较高" if p >= 60 else
             "一般，建议补人" if p >= 40 else "偏低，建议改期或换店")

    return {
        "prob": p,
        "level": level,
        "gap": gap,
        "target": pmin,
        "days_ahead": days,
        "left": left,
        "reasons": reasons,
        # 拉人话术：直接可复制进群
        "pitch": ("%s 的麦当劳派对已有 %d 人，还差 %d 人就成团，人均 ¥%.0f，来吗？"
                  % (_fmt_date(date_str), headcount, gap, (sess.get("price") or 0) / 100.0))
                 if gap > 0 else
                 ("%s 的麦当劳派对 %d 人已达成团线，人均 ¥%.0f，可直接锁定 🎉"
                  % (_fmt_date(date_str), headcount, (sess.get("price") or 0) / 100.0)),
    }


# ==========================================================================
# 2. 包场 vs 拼团
# ==========================================================================
def compare_modes(sess, headcount, note=None):
    """
    同一场次下，包场（partyType=1）与拼团（partyType=2）的成本与确定性对比。

    规则（来自商品 note，实测）：包场 5 人起订、单场最高 12 人；
    拼团需超过起订人数才可举办，未成团自动取消并退款。
    """
    per = (sess.get("price") or 0) / 100.0
    pmin = sess.get("partyMin") or 5
    pmax = sess.get("partyMax") or 12
    left = sess.get("leftNum") or 0

    # 包场：不足起订人数时按起订人数计费（场地保底）
    book_cnt = max(headcount, pmin)
    book_total = per * book_cnt
    # 拼团：按实际人数计费，但必须超过起订线
    group_ok = headcount > pmin and headcount <= left
    group_total = per * headcount if group_ok else None

    best, why = "包场", []
    if not group_ok:
        why.append("拼团需超过 %d 人才能发起，当前 %d 人不满足 → 只能走包场" % (pmin, headcount))
    elif headcount < pmin:
        why.append("人数低于起订线，包场按 %d 人保底计费" % pmin)
    else:
        why.append("两种模式均可发起")

    if group_ok:
        delta = book_total - group_total
        if delta > 0:
            best = "拼团"
            why.append("拼团比包场省 ¥%.0f（按实际 %d 人计费，无场地保底）" % (delta, headcount))
        else:
            why.append("两种模式总价相同，差别在「确定性」而非价格 → 同价优先选包场")
        why.append("拼团未成团会自动取消并退款，需承担凑不齐的风险")

    return {
        "headcount": headcount,
        "per": per,
        "book": {"mode": "包场", "type": 1, "count": book_cnt,
                 "total": book_total, "certainty": "100%（确定举办）"},
        "group": {"mode": "拼团", "type": 2, "count": headcount,
                  "total": group_total, "certainty": "取决于成团（未成团自动退款）"},
        "recommend": best,
        "reasons": why,
        "max": pmax,
    }


# ==========================================================================
# 3. 派对黄历（营销活动日历 × 场次余位）
# ==========================================================================
def parse_calendar(raw_text):
    """把 campaign-calendar 的 markdown 文本解析为 {日期: [活动标题, ...]}。"""
    import re
    out = {}
    cur = None
    for line in (raw_text or "").splitlines():
        m = re.match(r"^####\s*(\d{4})年(\d{1,2})月(\d{1,2})日", line.strip())
        if m:
            cur = "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            out.setdefault(cur, [])
            continue
        m2 = re.search(r"\*\*活动标题\*\*：\s*(.+)", line)
        if m2 and cur:
            out[cur].append(m2.group(1).strip())
    return out


def party_almanac(cli, dates, sessions_by_date, today=None, headcount=6):
    """
    派对黄历：对候选日期逐日评分，给出「未来哪天办最值」。

    评分维度：
      · 当日有官方营销活动   +18（有新品/联名，气氛与话题）
      · 周末                 +12（亲子家庭更易凑人）
      · 余位充足             +10
      · 满足提前 3 天预订     +8（不满足直接标注"来不及"）
      · 距今天数适中（3~14）  +5

    返回按分数降序的日期建议列表。
    """
    today = today or today_from(cli)
    calendar = {}
    try:
        calendar = parse_calendar(cli.call("campaign-calendar", {}, raw_text=True))
    except Exception:
        calendar = {}

    rows = []
    for ds in dates:
        d = _parse_date(ds)
        days = (d - today).days
        s = 50.0
        tags = []

        acts = calendar.get(ds) or []
        if acts:
            s += 18
            tags.append("官方活动：" + "、".join(a[:16] for a in acts[:2]))
        if d.weekday() >= 5:
            s += 12
            tags.append("周末")
        if days < 3:
            s -= 30
            tags.append("⚠ 距今天仅 %d 天，不满足「提前 3 天预订」" % days)
        else:
            s += 8
            if 3 <= days <= 14:
                s += 5

        sessions = sessions_by_date.get(ds) or []
        left_max = max([(x.get("leftNum") or 0) for x in sessions] or [0])
        if left_max >= headcount + 3:
            s += 10
            tags.append("余位充足")
        elif left_max < headcount:
            s -= 20
            tags.append("余位不足")

        rows.append({
            "date": ds, "weekday": WEEKDAY_CN[d.weekday()],
            "days_ahead": days, "activities": acts,
            "sessions": len(sessions), "left": left_max,
            "score": round(s, 1), "tags": tags,
            "verdict": "宜" if s >= 70 else ("可" if s >= 55 else "忌"),
        })

    rows.sort(key=lambda r: -r["score"])
    return {"today": today.isoformat(), "rows": rows,
            "with_activity": sorted([k for k, v in calendar.items() if v])}


# ==========================================================================
# 4. 儿童营养安心指数
# ==========================================================================
# 换购建议库：高负担 → 低负担（用官方菜单里真实存在的名字）
SWAPS = [
    ("大薯条", "小薯条"),
    ("中薯条", "小薯条"),
    ("可乐中杯", "无糖可口可乐中杯"),
    ("可乐小杯", "无糖可口可乐小杯"),
    ("可乐大杯", "无糖可口可乐大杯"),
    ("雪碧中杯", "锡兰红茶"),
    ("双层吉士汉堡", "吉士汉堡包"),
    ("麦辣鸡腿汉堡", "麦香鸡"),
    ("板烧鸡腿堡", "麦香鱼"),
    ("巨无霸", "吉士汉堡包"),
]

# 单餐营养参考区间（4–12 岁儿童，一餐）
NUTRI_REF = {"energyKcal": (400, 700), "sodium": (0, 800), "fat": (0, 26)}


def load_nutrition(cli):
    """
    解析 list-nutrition-foods 的表格文本 → {品名: {energyKcal, protein, fat, carbohydrate, sodium, calcium}}。
    返回文本形如：
        [160]{productName,nutritionDescription,energyKj,energyKcal,...}:
          猪柳麦满分,null,1288,308,16,16,24,781,213
    """
    txt = cli.call("list-nutrition-foods", {})
    if isinstance(txt, dict):
        txt = txt.get("data") or ""
    txt = txt if isinstance(txt, str) else str(txt)
    import re
    header, rows = None, {}
    for line in txt.splitlines():
        h = re.search(r"^\[\d+\]\{([^}]+)\}:", line.strip())
        if h:
            header = [c.strip() for c in h.group(1).split(",")]
            continue
        if header and "," in line and not line.strip().startswith(("###", "|")):
            parts = [p.strip() for p in line.strip().split(",")]
            if len(parts) == len(header):
                rec = dict(zip(header, parts))
                name = rec.get("productName")
                if name:
                    def num(k):
                        try:
                            return float(rec.get(k))
                        except Exception:
                            return 0.0
                    rows[name] = {
                        "energyKcal": num("energyKcal"),
                        "protein": num("protein"), "fat": num("fat"),
                        "carbohydrate": num("carbohydrate"),
                        "sodium": num("sodium"), "calcium": num("calcium"),
                    }
    return rows


def _match(table, name):
    """在营养表里宽松匹配一个餐品名。"""
    if name in table:
        return name
    for k in table:
        if name and (name in k or k in name):
            return k
    return None


def kids_nutrition_audit(cli, combo, table=None):
    """
    对一份派对餐单做「儿童营养安心指数」审计。

    combo: [品名, ...]，如 ["吉士汉堡包", "小薯条", "可乐小杯"]
    输出：逐项明细 + 合计 + 评级（A/B/C）+ 自动替换建议（含可省下的钠与热量）
    """
    table = table or load_nutrition(cli)
    items, total = [], {k: 0.0 for k in
                        ("energyKcal", "protein", "fat", "carbohydrate", "sodium", "calcium")}
    missing = []
    for name in combo:
        key = _match(table, name)
        if not key:
            missing.append(name)
            continue
        n = table[key]
        items.append({"name": name if key == name else "%s（按 %s 计）" % (name, key),
                      "raw": key, **n})
        for k in total:
            total[k] += n[k]

    # 评分：热量 / 钠 / 脂肪 三项按「超出参考上限的比例」扣分
    score, notes = 100.0, []
    lo_e, hi_e = NUTRI_REF["energyKcal"]
    if total["energyKcal"] > hi_e:
        over = (total["energyKcal"] - hi_e) / float(hi_e)
        score -= min(30, over * 100 * 1.5)
        notes.append("总热量 %.0f kcal 超出单餐参考上限 %d（+%.0f%%）"
                     % (total["energyKcal"], hi_e, over * 100))
    if total["sodium"] > NUTRI_REF["sodium"][1]:
        over = (total["sodium"] - 800) / 800.0
        score -= min(35, over * 100 * 3)
        notes.append("总钠 %.0f mg 偏高（儿童单餐建议 ≤800mg，+%.0f%%）"
                     % (total["sodium"], over * 100))
    if total["fat"] > NUTRI_REF["fat"][1]:
        over = (total["fat"] - 26) / 26.0
        score -= min(20, over * 100 * 2)
        notes.append("总脂肪 %.0fg 偏高（+%.0f%%）" % (total["fat"], over * 100))
    score = int(max(40, min(100, round(score))))
    grade = "A（放心吃）" if score >= 85 else ("B（尚可，建议微调）" if score >= 70 else "C（建议替换）")

    def _d(v, unit):
        return ("-%d%s" % (abs(v), unit)) if v > 0 else ("+%d%s" % (abs(v), unit))

    # 自动替换建议：挑 Δ钠（权重更高）与 Δ热量最大的 3 条
    swaps = []
    for a, b in SWAPS:
        ka, kb = _match(table, a), _match(table, b)
        if not ka or not kb or a not in combo:
            continue
        na, nb = table[ka], table[kb]
        d_sod = na["sodium"] - nb["sodium"]
        d_e = na["energyKcal"] - nb["energyKcal"]
        if d_sod > 0 or d_e > 0:
            swaps.append({"from": a, "to": b, "d_sodium": d_sod, "d_energy": d_e,
                          "text": "把「%s」换成「%s」→ 钠 %s、热量 %s"
                                  % (a, b, _d(d_sod, "mg"), _d(d_e, "kcal"))})
    swaps.sort(key=lambda x: -(x["d_sodium"] * 2 + x["d_energy"]))

    return {"items": items, "total": total, "score": score, "grade": grade,
            "notes": notes or ["各项均在儿童单餐参考区间内"],
            "swaps": swaps[:3], "missing": missing}


# ==========================================================================
# 5. 派对筹备时间线
# ==========================================================================
def party_timeline(date_str, today=None, headcount=6, is_group=True):
    """
    生成 T-7 → T 日筹备待办与预订截止倒计时（官方要求提前 3 天预订）。
    """
    today = today or _date.today()
    d = _parse_date(date_str)
    days = (d - today).days
    deadline = d.fromordinal(d.toordinal() - 3)

    def rel(n):
        return _date.fromordinal(d.toordinal() - n).isoformat()

    plan = [
        {"when": rel(7), "tag": "T-7", "todo": "确定到场人数与预算，初选门店/时段"},
        {"when": rel(5), "tag": "T-5", "todo": "发起拼团招募（如走拼团），把候选人拉进群"},
        {"when": rel(3), "tag": "T-3", "todo": "⚠️ 预订截止日：必须完成下单锁定场次"},
        {"when": rel(1), "tag": "T-1", "todo": "最终确认人数；如需餐食可提前点餐/预约"},
        {"when": rel(0), "tag": "T", "todo": "提前 15 分钟到店，核对派对礼品与座位"},
    ]
    for p in plan:
        pd = _parse_date(p["when"])
        p["days_ahead"] = (pd - today).days
        p["status"] = ("已过期" if p["days_ahead"] < 0
                       else ("今天" if p["days_ahead"] == 0
                             else "还剩 %d 天" % p["days_ahead"]))
    return {"date": date_str, "weekday": WEEKDAY_CN[d.weekday()],
            "days_ahead": days,
            "deadline": deadline.isoformat(),
            "deadline_days": (deadline - today).days,
            "alert": (("仅剩 %d 天就到预订截止日，请尽快锁定" % (deadline - today).days)
                      if (deadline - today).days <= 3 else "筹备期正常"),
            "plan": plan,
            "checklist": ["确认到场人数（成团线以上）",
                          "选定门店与场次并下单",
                          "告知家长时间/地点/接送",
                          "如有过敏史提前告知门店",
                          "准备蛋糕/伴手礼（如需）"]}


# ==========================================================================
# 6. 拼团招募卡（文本）
# ==========================================================================
def render_recruit_card(store_name, date_str, sess, headcount, radar=None,
                        contact="（点这里报名）"):
    """生成可直接粘贴进微信群的拼团招募卡（含余位进度条）。"""
    per = (sess.get("price") or 0) / 100.0
    pmin = sess.get("partyMin") or 5
    left = sess.get("leftNum") or 0
    filled = min(left, headcount)
    bar_len = 12
    done = int(round(bar_len * min(1.0, headcount / float(max(pmin, 1)))))
    bar = "█" * done + "░" * (bar_len - done)

    remain = max(0, pmin - headcount)
    tail = ("还差 %d 人成团！\n" % remain) if remain else "已成团，可锁定 ✅\n"
    prob_line = ""
    if radar:
        prob_line = "成团概率 %d%%（%s）\n" % (radar["prob"], radar["level"])

    return (
        "🎉 麦当劳派对拼团招募 🎉\n"
        "———————————————\n"
        "📍 门店：%s\n"
        "🕒 时间：%s %s–%s\n"
        "💰 人均：¥%.0f（%d 人成团，上限 %d 人）\n"
        "🎈 内容：开心乐园餐 + 派对礼品 + 90 分钟主题游戏\n"
        "———————————————\n"
        "报名进度 [%s] %d/%d\n"
        "%s%s"
        "———————————————\n"
        "👉 %s\n"
        "（余 %d 位，满 %d 人成团即锁定）"
        % (store_name, _fmt_date(date_str), sess.get("timeStart"), sess.get("timeEnd"),
           per, pmin, sess.get("partyMax") or 12,
           bar, filled, pmin, prob_line, tail, contact, left, pmin)
    )


# ==========================================================================
# 7. 邀请函 HTML（可保存 / 分享）
# ==========================================================================
def render_invite_html(title, store_name, date_str, sess, headcount, city,
                       radar=None, contact=""):
    """生成麦当劳红黄配色的派对邀请函（浅色、单文件、可直接分享）。"""
    per = (sess.get("price") or 0) / 100.0
    d = _parse_date(date_str)
    prob = ("%d%%" % radar["prob"]) if radar else "—"
    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s · 派对邀请函</title>
<style>
 *{box-sizing:border-box;margin:0;padding:0}
 body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
      background:#faf7f2;color:#2b2b2b;display:flex;justify-content:center;padding:32px 16px}
 .card{width:100%%;max-width:520px;background:#fff;border-radius:24px;overflow:hidden;
       box-shadow:0 18px 48px rgba(180,30,20,.12)}
 .top{background:linear-gradient(135deg,#DA291C,#F24E1E);color:#fff;padding:28px 28px 22px}
 .brand{font-size:13px;letter-spacing:3px;opacity:.9}
 h1{font-size:30px;margin:8px 0 6px;letter-spacing:1px}
 .sub{font-size:14px;opacity:.92}
 .body{padding:22px 28px}
 .row{display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px dashed #eee;font-size:15px}
 .row span:first-child{color:#8a8a8a}
 .row span:last-child{font-weight:700}
 .badge{display:inline-block;background:#FFF3D1;color:#8a6100;border-radius:999px;
        padding:4px 12px;font-size:13px;font-weight:700;margin:6px 6px 0 0}
 .bar{height:12px;background:#f0eee9;border-radius:999px;overflow:hidden;margin:14px 0 8px}
 .bar>i{display:block;height:100%%;background:linear-gradient(90deg,#FFC72C,#DA291C);border-radius:999px}
 .foot{padding:18px 28px 26px;font-size:13px;color:#8a8a8a;line-height:1.7}
 .cta{display:block;text-align:center;background:#FFC72C;color:#3a2a00;font-weight:800;
      padding:14px;border-radius:14px;margin-top:16px;font-size:16px}
</style></head><body>
<div class="card">
 <div class="top">
   <div class="brand">McDONALD'S PARTY</div>
   <h1>%s</h1>
   <div class="sub">%s · %s</div>
 </div>
 <div class="body">
   <div class="row"><span>门店</span><span>%s</span></div>
   <div class="row"><span>时段</span><span>%s – %s</span></div>
   <div class="row"><span>人均</span><span>¥%.0f</span></div>
   <div class="row"><span>成团</span><span>%d 人起（上限 %d 人）</span></div>
   <div class="row"><span>已报名</span><span>%d 人</span></div>
   <div class="bar"><i style="width:%d%%"></i></div>
   <div>
     <span class="badge">成团概率 %s</span>
     <span class="badge">时长 90 分钟</span>
     <span class="badge">开心乐园餐</span>
   </div>
 </div>
 <div class="foot">
   %s
   <div class="cta">%s</div>
 </div>
</div></body></html>""" % (
        title, title, city, _fmt_date(date_str),
        store_name, sess.get("timeStart"), sess.get("timeEnd"), per,
        sess.get("partyMin") or 5, sess.get("partyMax") or 12, headcount,
        int(100 * min(1.0, headcount / float(max(sess.get("partyMin") or 5, 1)))),
        prob,
        "名额有限，先到先得；如需调整请在活动日前 3 天申请退订。",
        contact or "长按识别 / 点击报名参加",
    )
    return html


# ==========================================================================
# 8. 全城四宫格比选
# ==========================================================================
def scout_grid(ranked):
    """把候选场次切成四个最有决策价值的视角。"""
    if not ranked:
        return {}
    cheapest = min(ranked, key=lambda r: (r["sess"].get("price") or 0))
    nearest = min(ranked, key=lambda r: (r["store"].get("distance") or 9e9))
    emptiest = max(ranked, key=lambda r: (r["sess"].get("leftNum") or 0))
    top = ranked[0]
    return {"最优综合": top, "最省人均": cheapest, "最近门店": nearest,
            "空位最多": emptiest,
            "备注": "「最优综合」来自五维调度评分；其余为单目标极值"}


def grid_line(label, r):
    if not r:
        return "  · %s：—" % label
    s, st = r["sess"], r["store"]
    return "  · %-14s %s %s %s ｜ 人均 ¥%.0f ｜ 余位 %s ｜ %s" % (
        label, (st.get("shortName") or "")[:18], r["date"], s.get("timeStart"),
        (s.get("price") or 0) / 100.0, s.get("leftNum"),
        (st.get("distanceText") or ""))

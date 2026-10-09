"""
派对拼团官 · 创意增强演示

展示七个差异化模块（成团雷达 / 双模式对比 / 派对黄历 / 营养审计 /
筹备时间线 / 招募卡 / 邀请函 HTML / 四宫格比选）。

用法：
    export MCD_MCP_TOKEN=xxxx
    python scripts/demo_plus.py
"""

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcd_client import McDClient                        # noqa: E402
from party_officer import find_city, scan, rank         # noqa: E402
from party_plus import (                                # noqa: E402
    formation_radar, compare_modes, party_almanac, kids_nutrition_audit,
    party_timeline, render_recruit_card, render_invite_html, scout_grid,
    grid_line, load_nutrition, today_from,
)

SPU = 1779
CITY = "杭州市"
HEAD = 6
BUDGET = 60


def hr(t):
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def main():
    cli = McDClient()
    today = today_from(cli)
    print("官方服务器日期：%s" % today)

    city = find_city(cli, SPU, CITY)
    cands = scan(cli, SPU, city, HEAD, BUDGET, "dinner", max_stores=5, max_dates=3)
    ranked = rank(cands, HEAD, BUDGET, "dinner", topk=5)
    print("城市：%s ｜ 扫描场次：%d ｜ 有效候选：%d" % (city.get("name"), len(cands), len(ranked)))

    top = ranked[0]
    sess, store = top["sess"], top["store"]

    # ---- 1. 成团概率雷达 ----
    hr("① 成团概率雷达")
    radar = formation_radar(top["date"], sess, HEAD, today)
    print("场次：%s %s %s" % (store.get("shortName"), top["date"], sess.get("timeStart")))
    print("成团概率：%d%%（%s）｜ 还差 %d 人 ｜ 距活动 %d 天"
          % (radar["prob"], radar["level"], radar["gap"], radar["days_ahead"]))
    for r in radar["reasons"]:
        print("   · " + r)
    print("拉人话术 → " + radar["pitch"])

    # ---- 2. 包场 vs 拼团 ----
    hr("② 包场 vs 拼团：成本与确定性")
    cmp_ = compare_modes(sess, HEAD)
    print("%-6s %-6s %-10s %s" % ("模式", "人数", "总价", "确定性"))
    print("-" * 74)
    for m in (cmp_["book"], cmp_["group"]):
        total = "¥%.0f" % m["total"] if m["total"] is not None else "不可发起"
        print("%-6s %-6d %-10s %s" % (m["mode"], m["count"], total, m["certainty"]))
    print("结论：推荐【%s】" % cmp_["recommend"])
    for r in cmp_["reasons"]:
        print("   · " + r)

    # ---- 3. 派对黄历 ----
    hr("③ 派对黄历：未来哪天办最值")
    dates = sorted({c["date"] for c in cands})
    by_date = {}
    for c in cands:
        by_date.setdefault(c["date"], []).append(c["sess"])
    alma = party_almanac(cli, dates, by_date, today, HEAD)
    print("%-12s %-4s %-4s %-6s %-4s %s" % ("日期", "星期", "天", "余位", "评判", "标签"))
    print("-" * 74)
    for r in alma["rows"]:
        print("%-12s %-4s %-4d %-6d %-4s %s"
              % (r["date"], r["weekday"], r["days_ahead"], r["left"], r["verdict"],
                 "；".join(r["tags"])[:44]))
    if alma["with_activity"]:
        print("当月有官方活动的日期：%s" % "、".join(alma["with_activity"]))

    # ---- 4. 儿童营养安心指数 ----
    hr("④ 儿童营养安心指数（开心乐园餐典型组合）")
    table = load_nutrition(cli)
    print("营养库：%d 个餐品" % len(table))
    combo = ["吉士汉堡包", "中薯条", "可乐中杯"]
    audit = kids_nutrition_audit(cli, combo, table=table)
    print("餐单：%s" % " + ".join(combo))
    print("%-16s %-8s %-8s %-8s %s" % ("餐品", "热量kcal", "脂肪g", "钠mg", "碳水g"))
    print("-" * 74)
    for it in audit["items"]:
        print("%-16s %-8.0f %-8.0f %-8.0f %.0f"
              % (it["name"][:15], it["energyKcal"], it["fat"], it["sodium"], it["carbohydrate"]))
    t = audit["total"]
    print("合计：%.0f kcal ｜ 脂肪 %.0fg ｜ 钠 %.0fmg ｜ 碳水 %.0fg"
          % (t["energyKcal"], t["fat"], t["sodium"], t["carbohydrate"]))
    print("安心指数：%d 分 → %s" % (audit["score"], audit["grade"]))
    for n in audit["notes"]:
        print("   · " + n)
    for s in audit["swaps"]:
        print("   ✔ " + s["text"])

    # ---- 5. 筹备时间线 ----
    hr("⑤ 派对筹备时间线")
    tl = party_timeline(top["date"], today, HEAD)
    print("活动日：%s（%s）｜ 预订截止：%s（%s）"
          % (tl["date"], tl["weekday"], tl["deadline"],
             ("还剩 %d 天" % tl["deadline_days"]) if tl["deadline_days"] >= 0 else "已过"))
    for p in tl["plan"]:
        print("  %-5s %-11s %-12s %s" % (p["tag"], p["when"], p["status"], p["todo"]))
    print("提示：" + tl["alert"])

    # ---- 6-7. 招募卡 + 邀请函 ----
    hr("⑥ 拼团招募卡（可直接发群）")
    card = render_recruit_card(store.get("shortName") or "", top["date"], sess, HEAD, radar)
    print(card)

    out_html = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "sample_invite.html"))
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(render_invite_html("麦当劳奇妙生日派对", store.get("shortName") or "",
                                   top["date"], sess, HEAD, city.get("name"),
                                   radar, contact="扫码报名（示例）"))
    print("\n⑦ 邀请函 HTML 已生成：%s" % out_html)

    # ---- 8. 四宫格 ----
    hr("⑧ 全城四宫格比选")
    for k, v in scout_grid(ranked).items():
        if k == "备注":
            print("  （%s）" % v)
        else:
            print(grid_line(k, v))


if __name__ == "__main__":
    main()

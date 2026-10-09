"""
派对拼团官 · 演示脚本

用法：
    export MCD_MCP_TOKEN=xxxx
    python scripts/demo.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcd_client import McDClient           # noqa: E402
from party_officer import plan             # noqa: E402

SPU = 1779          # 麦当劳奇妙生日派对（¥50/人，5~12 人成团）
CITY = "杭州市"


def print_report(title, res):
    print("\n" + "=" * 74)
    print(title)
    print("=" * 74)
    print("城市：%s   ｜   派对商品 spuId：%s   ｜   需求人数：%d   ｜   扫描场次：%d"
          % (res["city"]["name"], res["spuId"], res["headcount"], res["candidates"]))

    print("\n【推荐场次 Top %d】" % len(res["best"]))
    print("-" * 74)
    print("%-4s %-26s %-11s %-6s %-9s %s" % ("#", "门店", "日期", "时段", "人均", "评分"))
    print("-" * 74)
    for i, r in enumerate(res["best"], 1):
        s, st = r["sess"], r["store"]
        print("%-4d %-26s %-11s %-6s ¥%-8.0f %.1f"
              % (i, (st.get("shortName") or "")[:24], r["date"],
                 s.get("timeStart"), (s.get("price") or 0) / 100.0, r["score"]))
        print("     └ " + "；".join(r["reasons"]))

    print("\n【最易成团】")
    for r in res["easiest"]:
        need = (r["sess"].get("partyMin") or 0) - res["headcount"]
        tag = "已满足成团线" if need <= 0 else "还差 %d 人" % need
        print("  · %s %s %s  →  %s"
              % (r["store"].get("shortName"), r["date"], r["sess"].get("timeStart"), tag))

    print("\n【余位告急（优先锁定）】")
    for r in res["urgent"]:
        print("  · %s %s %s  →  仅剩 %s 位"
              % (r["store"].get("shortName"), r["date"],
                 r["sess"].get("timeStart"), r["sess"].get("leftNum")))


def main():
    cli = McDClient()

    # 场景一：6 人，预算 60 元/人，偏爱晚市
    r1 = plan(CITY, SPU, headcount=6, budget=60, prefer_time="dinner",
              max_stores=4, max_dates=2, topk=5, cli=cli, verbose=True)
    print_report("场景一：杭州 · 生日会 6 人 · 预算 ¥60/人 · 晚市", r1)

    # 场景二：3 人（不足 5 人成团线）—— 展示"拼团"提示
    r2 = plan(CITY, SPU, headcount=3, budget=60, prefer_time="dinner",
              max_stores=4, max_dates=2, topk=3, cli=cli)
    print_report("场景二：杭州 · 生日会 3 人（不足起步人数）", r2)


if __name__ == "__main__":
    main()

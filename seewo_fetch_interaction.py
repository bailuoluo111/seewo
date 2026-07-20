#!/usr/bin/env python3
"""
seewo_fetch_interaction.py — 抓取课堂观察 7 个模块的输入数据与 AI 解读结果

基于开发者接口文档，页面报告接口统一为：
  GET /api/analyse/course/report/{reportId}/{analysisType}
响应结构：{ analysisStatus, analysisType, version, reportDetail: {...} }

抓取策略（避开"监听太晚错过响应"问题）：
  1. 复用/建立登录态，校验 cookie 非空
  2. 打开报告页拿到有效会话
  3. 用浏览器上下文 request API 直接遍历所有 analysisType 接口（自动带 cookie）
  4. 解析 + 保存到 seewo_report_data.json

用法：
  python seewo_fetch_interaction.py
"""

import os
import json
from playwright.sync_api import sync_playwright

REPORT_ID = "96f58e78b80c462cb1194fa2f6ef4e97"
BASE_URL = "https://easiinsight.seewo.com"        # 报告页面域名
API_HOST = "https://edulyse.seewo.com"            # 后端 API 域名（与页面不同源）
REPORT_URL = f"{BASE_URL}/report/detail/{REPORT_ID}/home"
API_TMPL = f"{API_HOST}/api/analyse/course/report/{REPORT_ID}/{{atype}}"
STATE_FILE = "seewo_state.json"
OUTPUT_FILE = "seewo_report_data.json"

# 7 个模块的输入接口 + AI 结果接口（analysisType 即 URL 末段）
MODULES = [
    # 学生页 —— 输入数据
    {"type": "studentStudyStatistic", "name": "学生互动数据", "page": "学生页", "kind": "输入"},
    {"type": "studentStudyBehavior", "name": "学习行为分布", "page": "学生页", "kind": "输入"},
    {"type": "solo", "name": "回答建构分类", "page": "学生页", "kind": "输入"},
    {"type": "studentAnswerClassification", "name": "应答时间", "page": "学生页", "kind": "输入"},
    # 教师页 —— 输入数据
    {"type": "speechData", "name": "讲授分析", "page": "教师页", "kind": "输入"},
    {"type": "courseProcessReengineering", "name": "课堂流程重构", "page": "教师页", "kind": "输入"},
    {"type": "questionRecord", "name": "提问记录", "page": "教师页", "kind": "输入"},
    {"type": "questionAnswerExtraResult", "name": "问答额外结果", "page": "教师页", "kind": "输入"},
    {"type": "bloom", "name": "布鲁姆提问分类", "page": "教师页", "kind": "输入"},
    {"type": "teacherAppraisalClassification", "name": "教师理答分类", "page": "教师页", "kind": "输入"},
    # AI 结果接口
    {"type": "studentStudyStatisticExplain", "name": "学生互动-AI解读", "page": "学生页", "kind": "AI结果"},
    {"type": "studentStudyBehaviorExplain", "name": "学习行为-AI解读", "page": "学生页", "kind": "AI结果"},
    {"type": "soloExplain", "name": "回答建构-AI解读", "page": "学生页", "kind": "AI结果"},
    {"type": "studentAnswerDurationExplain", "name": "应答时间-AI解读", "page": "学生页", "kind": "AI结果"},
    {"type": "courseProcessReengineeringExplain", "name": "课堂流程重构-AI解读", "page": "教师页", "kind": "AI结果"},
    {"type": "questionScoreExplain", "name": "提问有效性-AI解读", "page": "教师页", "kind": "AI结果"},
]


def state_has_cookies(path: str) -> bool:
    """校验登录态里是否真的存了 cookie"""
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        return len(state.get("cookies", [])) > 0
    except Exception:
        return False


# ── 各模块的摘要解析（仅提取关键指标，完整数据仍会存盘）────────────
def summarize(atype: str, detail):
    """针对已知结构提取易读摘要；未知结构返回 None"""
    if not isinstance(detail, dict):
        return None

    if atype == "studentStudyStatistic":
        def pct(v):
            return f"{round(v * 100, 1)}%" if isinstance(v, (int, float)) else None
        return {
            "平均抬头率": pct(detail.get("raiseHeadRatio")),
            "平均举手率": pct(detail.get("handUpRatio")),
            "平均参与度": pct(detail.get("answerRatio")),
        }

    if atype in ("studentStudyStatisticExplain", "studentStudyBehaviorExplain",
                 "soloExplain", "studentAnswerDurationExplain",
                 "courseProcessReengineeringExplain"):
        return {"AI文案": detail.get("text")}

    if atype == "questionScoreExplain":
        return {"提问有效性得分": detail.get("score"), "AI文案": detail.get("text")}

    if atype == "speechData":
        return {
            "讲授字数": detail.get("speechWordCount"),
            "平均语速(字/秒)": detail.get("speechSpeedPerSecond"),
            "讲授时长(秒)": detail.get("speechDurationInSeconds"),
        }

    return None


def looks_logged_in(page) -> bool:
    try:
        content = page.content()
        return "/report/detail/" in page.url and "扫码" not in content[:8000]
    except Exception:
        return False


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx_kwargs = dict(locale="zh-CN")
        if state_has_cookies(STATE_FILE):
            ctx_kwargs["storage_state"] = STATE_FILE
            print(f"→ 复用登录态 {STATE_FILE}")
        else:
            print("→ 无有效登录态，需手动登录一次")

        context = browser.new_context(**ctx_kwargs)
        page = context.new_page()

        print("→ 打开报告页...")
        page.goto(REPORT_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        if not looks_logged_in(page):
            print("\n请在浏览器中手动登录（扫码或账号密码）。")
            print("务必确认已看到报告内容后，再回终端按回车。")
            input("登录完成后按【回车】继续... ")
            page.goto(REPORT_URL, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)

        # 保存登录态并校验
        context.storage_state(path=STATE_FILE)
        if not state_has_cookies(STATE_FILE):
            print("\n❌ 登录态仍为空（无 cookie），登录未成功。请重试并确认登录后再按回车。")
            browser.close()
            return
        print("→ 登录态有效，开始遍历接口...\n")

        # 用浏览器上下文的 request API 直接调接口（自动带 cookie）
        results = {}
        for m in MODULES:
            atype = m["type"]
            url = API_TMPL.format(atype=atype)
            try:
                resp = context.request.get(url, timeout=20000)
                status = resp.status
                if status != 200:
                    print(f"  [{status}] {m['name']} ({atype})")
                    results[atype] = {"module": m, "status": status, "error": True}
                    continue
                data = resp.json()
                detail = data.get("reportDetail")
                summary = summarize(atype, detail)
                results[atype] = {
                    "module": m,
                    "status": status,
                    "analysisStatus": data.get("analysisStatus"),
                    "summary": summary,
                    "reportDetail": detail,
                }
                tag = f"  [200] {m['name']} ({atype})"
                if summary:
                    kv = "  ".join(f"{k}={v}" for k, v in summary.items()
                                   if v is not None and k != "AI文案")
                    print(tag + ("  → " + kv if kv else ""))
                else:
                    print(tag)
            except Exception as e:
                print(f"  [ERR] {m['name']} ({atype}): {e}")
                results[atype] = {"module": m, "error": str(e)}

        context.storage_state(path=STATE_FILE)
        browser.close()

    # 保存全部结果
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "report_id": REPORT_ID,
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    ok = sum(1 for v in results.values() if v.get("status") == 200)
    print("\n" + "=" * 50)
    print(f"✅ 完成：{ok}/{len(MODULES)} 个接口返回 200")
    print(f"→ 全部数据已保存到 {OUTPUT_FILE}")

    # 重点打印学生互动三项指标
    si = results.get("studentStudyStatistic", {}).get("summary")
    if si:
        print("\n学生互动数据：")
        for k, v in si.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
热点话题词云分析 + 对比分析
作者：Victor Zhong
功能：采集微博热搜数据，进行中文分词、词频统计、词云生成与对比分析
"""

import os
import re
import sys
import time
import random
import platform
import requests
import jieba
import jieba.analyse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from collections import Counter
from wordcloud import WordCloud

# ─────────────────────────────────────────────
# 路径配置
# ─────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

FILE_NOW      = os.path.join(DATA_DIR, "raw_now.txt")
FILE_EARLIER  = os.path.join(DATA_DIR, "raw_earlier.txt")
FILE_STOPWORD = os.path.join(DATA_DIR, "stopwords.txt")

os.makedirs(DATA_DIR,   exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─────────────────────────────────────────────
# 1. 字体自动检测（兼容 Mac / Windows / Linux）
# ─────────────────────────────────────────────
def find_chinese_font() -> str:
    """
    自动检测系统中可用的中文字体路径。
    优先级：项目本地字体 > 系统字体
    """
    system = platform.system()

    # 候选字体列表（按优先级）
    candidates = []

    if system == "Darwin":   # macOS
        candidates = [
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/Library/Fonts/Arial Unicode MS.ttf",
            "/System/Library/Fonts/PingFang.ttc",
        ]
    elif system == "Windows":
        candidates = [
            r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\simsun.ttc",
        ]
    else:                    # Linux / Docker
        candidates = [
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/arphic/uming.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        ]

    for path in candidates:
        if os.path.exists(path):
            print(f"  ✔ 使用字体：{path}")
            return path

    # 最后尝试通过 matplotlib 查找
    for f in fm.findSystemFonts(fontpaths=None, fontext='ttf'):
        if any(kw in f.lower() for kw in ['cjk', 'chinese', 'simhei', 'wqy', 'noto', 'ming', 'hei']):
            print(f"  ✔ matplotlib 找到字体：{f}")
            return f

    print("  ⚠ 未找到中文字体，将尝试使用默认字体（中文可能显示为方块）")
    return None


# ─────────────────────────────────────────────
# 2. 数据采集
# ─────────────────────────────────────────────

# 模拟微博热搜数据（当网络请求失败时使用）
MOCK_DATA_NOW = [
    "春节假期旅游人次创新高", "人工智能大模型最新进展", "新能源汽车销量突破纪录",
    "全国两会代表委员热议民生", "大学生就业形势分析", "国产大飞机C919新航线开通",
    "北京马拉松报名开启", "明星离婚案件持续发酵", "世界杯预选赛中国队备战",
    "ChatGPT最新版本发布", "房价调控政策解读", "新冠疫情防控最新通知",
    "高考志愿填报指南发布", "电动汽车换电模式推广", "中美关系最新动态",
    "反腐倡廉专项行动成果", "乡村振兴战略推进情况", "国产手机芯片突破",
    "儿童教育减负政策落地", "养老金上调方案出台", "气候变化应对措施",
    "网络诈骗新型手段曝光", "演员塌房事件最新进展", "医保药品目录调整",
    "文化遗产保护专项计划", "奥运会备战最新消息", "金融市场波动原因分析",
    "外卖骑手权益保障新规", "共享单车乱停整治行动", "国际油价大幅波动",
    "大数据隐私保护立法", "电竞行业发展报告", "直播带货监管趋严",
    "粮食安全战略部署", "航天探月工程新进展", "双碳目标完成情况",
]

MOCK_DATA_EARLIER = [
    "春节假期出行高峰预测", "人工智能写作工具走红", "新能源汽车补贴政策延续",
    "全国两会议题提前预热", "应届毕业生薪资调查报告", "国产芯片研发新突破",
    "北京冬季文化旅游节", "娱乐圈偷税漏税专项整治", "男足亚洲杯出线形势",
    "元宇宙投资泡沫争议", "楼市松绑城市继续增加", "流感病毒变异最新研究",
    "高考改革方案征求意见", "充电桩建设提速计划", "台海局势国际关注",
    "官员落马最新通报", "农业科技下乡惠民", "5G手机普及率提升",
    "双减政策一年成效", "延迟退休方案讨论", "极端天气频发应对",
    "电话诈骗防范宣传", "流量明星商业价值缩水", "集采药品价格下降",
    "非物质文化遗产展演", "全红婵跳水世锦赛夺金", "A股市场走势分析",
    "网约车司机收入变化", "共享单车押金退还难题", "石油价格影响通胀",
    "个人信息保护法实施效果", "游戏版号恢复发放", "网红经济监管加强",
    "种粮补贴标准提高", "神舟飞船发射成功", "碳排放交易市场扩容",
]

def fetch_weibo_hot(session: requests.Session) -> list:
    """
    尝试从微博热搜页面爬取数据。
    返回热搜词列表，失败返回空列表。
    """
    url = "https://weibo.com/ajax/side/hotSearch"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://weibo.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    try:
        resp = session.get(url, headers=headers, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        # 解析热搜列表
        realtime = data.get("data", {}).get("realtime", [])
        words = []
        for item in realtime:
            word = item.get("note") or item.get("word", "")
            if word and len(word) >= 2:
                words.append(word.strip())
        return words[:50]
    except Exception as e:
        print(f"    微博API请求失败：{e}")
        return []


def fetch_data() -> None:
    """
    数据采集入口：
    - 先尝试真实爬取微博热搜
    - 若失败则使用模拟数据（含随机扰动，模拟两个时间点的差异）
    保存至 data/raw_now.txt 和 data/raw_earlier.txt
    """
    print("\n【Step 1】数据采集")
    print("─" * 50)

    session = requests.Session()

    # ── 采集"当前"热搜 ──
    print("  正在采集当前热搜数据...")
    now_words = fetch_weibo_hot(session)

    if len(now_words) >= 30:
        print(f"  ✔ 成功采集到 {len(now_words)} 条实时热搜")
        earlier_words = now_words.copy()
        # 对历史数据做随机替换，模拟时间差异
        replace_count = random.randint(8, 15)
        indices = random.sample(range(len(earlier_words)), replace_count)
        mock_pool = MOCK_DATA_EARLIER.copy()
        random.shuffle(mock_pool)
        for i, idx in enumerate(indices):
            if i < len(mock_pool):
                earlier_words[idx] = mock_pool[i]
    else:
        print("  ⚠ 网络请求失败或数据不足，使用模拟数据")
        # 加入随机扰动使两个时间点有所不同
        now_words_base    = MOCK_DATA_NOW.copy()
        earlier_words_base = MOCK_DATA_EARLIER.copy()
        random.shuffle(now_words_base)
        random.shuffle(earlier_words_base)
        now_words     = now_words_base[:38]
        earlier_words = earlier_words_base[:38]

    # 保存文件
    with open(FILE_NOW, "w", encoding="utf-8") as f:
        f.write("\n".join(now_words))
    with open(FILE_EARLIER, "w", encoding="utf-8") as f:
        f.write("\n".join(earlier_words))

    print(f"  ✔ 当前热搜 {len(now_words)} 条 → {FILE_NOW}")
    print(f"  ✔ 历史热搜 {len(earlier_words)} 条 → {FILE_EARLIER}")


# ─────────────────────────────────────────────
# 3. 停用词生成
# ─────────────────────────────────────────────
DEFAULT_STOPWORDS = """
的 了 是 在 我 有 和 就 不 人 都 一 一个 上 也 很 到 说 要 去 你
他 我 她 它 这 那 们 与 及 对 为 等 将 该 其 中 已 于 从 向 而
但 或 虽然 因为 所以 如果 虽 则 被 把 让 使 用 来 以 最 更 又
可以 可 能 应该 需要 进行 开展 推进 加强 相关 工作 方面 情况
表示 认为 指出 强调 提出 指 称 据 时 年 月 日 号 个 多 以上
啊 吧 呢 哦 嗯 哈 呀 哇 嘿 哟 喂 哎 哦 喔 哩 咯 嘛
新 大 小 高 低 好 坏 多 少 长 短 快 慢 全 各 每 任 何
""".strip().split()


def ensure_stopwords() -> None:
    """生成停用词文件（如不存在）"""
    if not os.path.exists(FILE_STOPWORD):
        with open(FILE_STOPWORD, "w", encoding="utf-8") as f:
            for w in sorted(set(DEFAULT_STOPWORDS)):
                f.write(w + "\n")
        print(f"  ✔ 生成停用词文件：{FILE_STOPWORD}（{len(DEFAULT_STOPWORDS)} 词）")
    else:
        print(f"  ✔ 加载已有停用词文件：{FILE_STOPWORD}")


def load_stopwords() -> set:
    """读取停用词集合"""
    ensure_stopwords()
    with open(FILE_STOPWORD, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


# ─────────────────────────────────────────────
# 4. 数据预处理
# ─────────────────────────────────────────────
def clean_text(text: str) -> str:
    """
    文本清洗：
    - 去除 URL
    - 去除表情、特殊符号
    - 保留中文、英文、数字
    """
    text = re.sub(r"http[s]?://\S+", "", text)
    text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9\s]", " ", text)
    return text.strip()


def tokenize(text: str, stopwords: set) -> list:
    """
    jieba 精确模式分词，并过滤：
    - 停用词
    - 长度 < 2 的词
    - 纯数字
    """
    words = jieba.cut(text, cut_all=False)
    result = []
    for w in words:
        w = w.strip()
        if (len(w) >= 2
                and w not in stopwords
                and not re.match(r"^\d+$", w)):
            result.append(w)
    return result


def preprocess(filepath: str, stopwords: set) -> Counter:
    """
    读取原始文件 → 清洗 → 分词 → 统计词频
    返回 Counter 对象
    """
    with open(filepath, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    all_words = []
    for line in lines:
        cleaned = clean_text(line)
        tokens  = tokenize(cleaned, stopwords)
        all_words.extend(tokens)

    return Counter(all_words)


# ─────────────────────────────────────────────
# 5. 对比分析
# ─────────────────────────────────────────────
def compare_words(counter_now: Counter, counter_earlier: Counter, top_n: int = 20) -> dict:
    """
    对比两个时间点的高频词：
    - new_words   ：只在 now 出现的词（新热点）
    - gone_words  ：只在 earlier 出现的词（降温词）
    - common_words：两个时间点共同的高频词
    返回包含以上三类的字典
    """
    top_now     = {w for w, _ in counter_now.most_common(top_n)}
    top_earlier = {w for w, _ in counter_earlier.most_common(top_n)}

    new_words    = sorted(top_now - top_earlier)
    gone_words   = sorted(top_earlier - top_now)
    common_words = sorted(top_now & top_earlier,
                          key=lambda w: counter_now[w] + counter_earlier[w],
                          reverse=True)

    return {
        "new_words":    new_words,
        "gone_words":   gone_words,
        "common_words": common_words,
    }


def print_comparison_report(counter_now: Counter,
                             counter_earlier: Counter,
                             comparison: dict) -> None:
    """在终端打印对比分析报告"""
    sep = "═" * 55

    print(f"\n{sep}")
    print("  📊 热搜词频对比分析报告")
    print(sep)

    # Top 20 Now
    print("\n▶ 当前热搜 Top 20：")
    print(f"  {'排名':<5} {'词语':<15} {'词频':>6}")
    print("  " + "─" * 30)
    for rank, (w, cnt) in enumerate(counter_now.most_common(20), 1):
        print(f"  {rank:<5} {w:<15} {cnt:>6}")

    # Top 20 Earlier
    print("\n▶ 历史热搜 Top 20：")
    print(f"  {'排名':<5} {'词语':<15} {'词频':>6}")
    print("  " + "─" * 30)
    for rank, (w, cnt) in enumerate(counter_earlier.most_common(20), 1):
        print(f"  {rank:<5} {w:<15} {cnt:>6}")

    # 对比表：共同词 + 词频变化
    common = comparison["common_words"]
    if common:
        print("\n▶ 共同高频词（词频变化对比）：")
        print(f"  {'词语':<15} {'当前词频':>8} {'历史词频':>8} {'变化':>8}")
        print("  " + "─" * 45)
        for w in common:
            n   = counter_now[w]
            e   = counter_earlier[w]
            chg = n - e
            arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "─")
            print(f"  {w:<15} {n:>8} {e:>8} {arrow}{abs(chg):>6}")

    # 新热点
    print(f"\n▶ 🆕 新出现的热点词（共 {len(comparison['new_words'])} 个）：")
    if comparison["new_words"]:
        print("  " + "  ".join(f"[{w}]" for w in comparison["new_words"]))
    else:
        print("  （无）")

    # 降温词
    print(f"\n▶ 📉 降温/消失的词（共 {len(comparison['gone_words'])} 个）：")
    if comparison["gone_words"]:
        print("  " + "  ".join(f"[{w}]" for w in comparison["gone_words"]))
    else:
        print("  （无）")

    print(f"\n{sep}\n")


# ─────────────────────────────────────────────
# 6. 词云生成
# ─────────────────────────────────────────────
def generate_wordcloud(word_freq: dict,
                       output_path: str,
                       title: str,
                       font_path: str,
                       colormap: str = "viridis") -> None:
    """
    生成单张词云图并保存。
    word_freq   : {词: 频次}
    output_path : 输出文件路径
    title       : 图片标题
    font_path   : 中文字体路径
    colormap    : matplotlib 色彩方案
    """
    if not word_freq:
        print(f"  ⚠ 词频为空，跳过生成：{output_path}")
        return

    wc_kwargs = dict(
        width=800,
        height=400,
        background_color="white",
        max_words=150,
        colormap=colormap,
        prefer_horizontal=0.9,
        min_font_size=10,
        max_font_size=120,
        collocations=False,
    )
    if font_path:
        wc_kwargs["font_path"] = font_path

    wc = WordCloud(**wc_kwargs)
    wc.generate_from_frequencies(word_freq)

    fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    ax.set_title(title, fontsize=16, pad=12,
                 fontproperties=fm.FontProperties(fname=font_path) if font_path else None)
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    print(f"  ✔ 已保存：{output_path}")


def build_diff_freq(counter_now: Counter, counter_earlier: Counter) -> dict:
    """
    构建差异词频字典（用于对比词云）：
    - 仅保留两个时间点中"出现差异"的词
    - 词频 = |now - earlier|，用于突出变化程度
    """
    all_words = set(counter_now.keys()) | set(counter_earlier.keys())
    diff = {}
    for w in all_words:
        delta = abs(counter_now.get(w, 0) - counter_earlier.get(w, 0))
        if delta > 0:
            diff[w] = delta
    return diff


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────
def main():
    print("\n" + "═" * 55)
    print("  🔥 热点话题词云分析 + 对比分析系统")
    print("═" * 55)

    # ── Step 1：数据采集 ──
    fetch_data()

    # ── Step 2：数据预处理 ──
    print("\n【Step 2】数据预处理 & 分词")
    print("─" * 50)
    stopwords = load_stopwords()
    print("  正在对当前数据分词...")
    counter_now = preprocess(FILE_NOW, stopwords)
    print(f"  ✔ 当前数据：去重后 {len(counter_now)} 个词")
    print("  正在对历史数据分词...")
    counter_earlier = preprocess(FILE_EARLIER, stopwords)
    print(f"  ✔ 历史数据：去重后 {len(counter_earlier)} 个词")

    # ── Step 3：对比分析 ──
    print("\n【Step 3】对比分析")
    print("─" * 50)
    comparison = compare_words(counter_now, counter_earlier, top_n=20)
    print_comparison_report(counter_now, counter_earlier, comparison)

    # ── Step 4：词云生成 ──
    print("\n【Step 4】词云生成")
    print("─" * 50)
    font_path = find_chinese_font()

    # 词云1：当前热搜
    generate_wordcloud(
        word_freq   = dict(counter_now),
        output_path = os.path.join(OUTPUT_DIR, "wordcloud_now.png"),
        title       = "当前热搜词云",
        font_path   = font_path,
        colormap    = "Reds",
    )

    # 词云2：历史热搜
    generate_wordcloud(
        word_freq   = dict(counter_earlier),
        output_path = os.path.join(OUTPUT_DIR, "wordcloud_earlier.png"),
        title       = "历史热搜词云",
        font_path   = font_path,
        colormap    = "Blues",
    )

    # 词云3：差异对比词云
    diff_freq = build_diff_freq(counter_now, counter_earlier)
    generate_wordcloud(
        word_freq   = diff_freq,
        output_path = os.path.join(OUTPUT_DIR, "wordcloud_diff.png"),
        title       = "热搜变化对比词云（差异词）",
        font_path   = font_path,
        colormap    = "RdYlGn",
    )

    # ── 完成 ──
    print("\n" + "═" * 55)
    print("  ✅ 全部任务完成！")
    print(f"  📁 输出目录：{OUTPUT_DIR}")
    print("  📊 生成文件：")
    for fname in ["wordcloud_now.png", "wordcloud_earlier.png", "wordcloud_diff.png"]:
        fpath = os.path.join(OUTPUT_DIR, fname)
        size  = os.path.getsize(fpath) // 1024 if os.path.exists(fpath) else 0
        print(f"     - {fname}  ({size} KB)")
    print("═" * 55 + "\n")


if __name__ == "__main__":
    main()

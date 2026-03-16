from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
SHOT_DIR = ROOT / "runtime" / "docs" / "screenshots"
OUT_PDF = ROOT / "runtime" / "docs" / "DolphinDB_回测工作台_用户教程.pdf"


def scaled_image(path: Path, max_width: float, max_height: float) -> Image:
  with PILImage.open(path) as im:
    width, height = im.size
  ratio = min(max_width / width, max_height / height)
  return Image(str(path), width=width * ratio, height=height * ratio)


def build_pdf() -> Path:
  OUT_PDF.parent.mkdir(parents=True, exist_ok=True)

  pdfmetrics.registerFont(TTFont("SimHei", r"C:\Windows\Fonts\simhei.ttf"))
  pdfmetrics.registerFont(TTFont("YaHei", r"C:\Windows\Fonts\msyh.ttc"))

  doc = SimpleDocTemplate(
    str(OUT_PDF),
    pagesize=A4,
    leftMargin=16 * mm,
    rightMargin=16 * mm,
    topMargin=14 * mm,
    bottomMargin=14 * mm,
    title="DolphinDB 量化选股择时策略工作台 - 使用教程",
  )

  styles = getSampleStyleSheet()
  title_style = ParagraphStyle(
    "TitleCN",
    parent=styles["Title"],
    fontName="YaHei",
    fontSize=22,
    leading=30,
    alignment=TA_CENTER,
    textColor=colors.HexColor("#0A2A55"),
  )
  h1 = ParagraphStyle(
    "H1CN",
    parent=styles["Heading1"],
    fontName="YaHei",
    fontSize=16,
    leading=22,
    spaceAfter=8,
    textColor=colors.HexColor("#0A2A55"),
  )
  h2 = ParagraphStyle(
    "H2CN",
    parent=styles["Heading2"],
    fontName="YaHei",
    fontSize=13,
    leading=18,
    spaceBefore=8,
    spaceAfter=6,
    textColor=colors.HexColor("#173B68"),
  )
  body = ParagraphStyle(
    "BodyCN",
    parent=styles["BodyText"],
    fontName="SimHei",
    fontSize=10.5,
    leading=16,
    spaceAfter=4,
  )
  caption = ParagraphStyle(
    "CaptionCN",
    parent=styles["BodyText"],
    fontName="SimHei",
    fontSize=9,
    leading=13,
    textColor=colors.HexColor("#4A5873"),
    alignment=TA_CENTER,
  )

  story = []

  # Cover
  story.append(Paragraph("DolphinDB 量化选股择时策略工作台", title_style))
  story.append(Paragraph("使用教程（V1）", title_style))
  story.append(Spacer(1, 18))
  story.append(
    Paragraph(
      f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>"
      "适用对象：策略研究员、量化开发、交易支持<br/>"
      "说明：本教程基于当前部署版本界面，包含完整操作流程和页面截图。",
      body,
    )
  )
  story.append(Spacer(1, 14))
  cover_img = scaled_image(SHOT_DIR / "01_factor_page_full.png", doc.width, 140 * mm)
  story.append(cover_img)
  story.append(Spacer(1, 4))
  story.append(Paragraph("图 1. 平台首页（因子页）", caption))

  story.append(PageBreak())

  # 功能介绍
  story.append(Paragraph("1. 功能介绍", h1))
  story.append(
    Paragraph(
      "本平台将 DolphinDB 回测能力与前端工作台整合，覆盖“选股因子构建 -> 回测参数配置 -> "
      "任务并行运行 -> 结果分析与代码回显 -> 系统配置管理”的完整闭环。",
      body,
    )
  )
  feature_table = Table(
    [
      ["模块", "核心用途", "主要输出"],
      ["因子页", "通过标签或语义输入构建策略条件", "选股范围、基本面/技术面条件、语义判定结果"],
      ["回测页", "配置回测模板和风控参数并提交任务", "回测任务请求"],
      ["任务页", "查看任务状态、收益曲线、交易明细和运行代码", "任务结果与分析明细"],
      ["配置页", "管理 DolphinDB 与 LLM 接入参数", "连接配置与模型参数"],
    ],
    colWidths=[38 * mm, 78 * mm, 48 * mm],
  )
  feature_table.setStyle(
    TableStyle(
      [
        ("FONTNAME", (0, 0), (-1, -1), "SimHei"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E9F0FA")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0A2A55")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#A8BDD9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
      ]
    )
  )
  story.append(feature_table)
  story.append(Spacer(1, 10))
  story.append(Paragraph("页面顺序固定为：因子页 -> 回测页 -> 任务页 -> 配置页。", body))

  story.append(Paragraph("2. 使用前准备", h1))
  story.append(Paragraph("开始前请确认以下检查项：", body))
  story.append(Paragraph("1）前后端服务已启动，浏览器可访问 http://localhost:5173/factors。", body))
  story.append(Paragraph("2）配置页中的 DolphinDB 连接可用，状态栏显示 DDB 在线。", body))
  story.append(Paragraph("3）如需语义能力，请在配置页填写 LLM Provider/Model/API Key。", body))

  story.append(PageBreak())

  # Step 1
  story.append(Paragraph("3. 操作流程", h1))
  story.append(Paragraph("步骤 1：在因子页创建策略条件", h2))
  story.append(Paragraph("入口：导航栏“因子页”。", body))
  story.append(Paragraph("操作：", body))
  story.append(Paragraph("1）可在“语义策略输入”中用自然语言描述策略并点击“开始语义分析”。", body))
  story.append(Paragraph("2）在“选股范围与检索”选择市场范围，并搜索因子。", body))
  story.append(Paragraph("3）在“基本面因子”“技术面因子”中选择指标，并按需启用个性化条件。", body))
  story.append(Paragraph("4）不启用个性化时，系统沿用默认回测脚本条件。", body))
  img1 = scaled_image(SHOT_DIR / "01_factor_page_full.png", doc.width, 108 * mm)
  story.append(img1)
  story.append(Paragraph("图 2. 因子页主视图", caption))
  story.append(Spacer(1, 4))
  img2 = scaled_image(SHOT_DIR / "02_factor_conditions.png", doc.width, 108 * mm)
  story.append(img2)
  story.append(Paragraph("图 3. 因子个性化条件示例", caption))

  story.append(PageBreak())

  # Step 2
  story.append(Paragraph("步骤 2：在回测页提交任务", h2))
  story.append(Paragraph("入口：导航栏“回测页”。", body))
  story.append(Paragraph("操作：", body))
  story.append(Paragraph("1）选择策略模板（组合策略或择时模板）。", body))
  story.append(Paragraph("2）设置开始/结束日期，可直接使用快捷时间按钮。", body))
  story.append(Paragraph("3）配置基准、买入优先级和风控参数（资金、持仓、单日买入等）。", body))
  story.append(Paragraph("4）点击“提交回测任务”，系统会自动跳转到任务页并定位 run_id。", body))
  img3 = scaled_image(SHOT_DIR / "03_backtest_page_full.png", doc.width, 135 * mm)
  story.append(img3)
  story.append(Paragraph("图 4. 回测页参数配置", caption))

  # Step 3
  story.append(Paragraph("步骤 3：在任务页查看并分析回测结果", h2))
  story.append(Paragraph("入口：导航栏“任务页”。", body))
  story.append(Paragraph("操作：", body))
  story.append(Paragraph("1）左侧列表按时间显示任务状态（运行中/已完成/失败）。", body))
  story.append(Paragraph("2）点击任务后，右侧展示 KPI、净值曲线（起点归一化为 1）与交易明细。", body))
  story.append(Paragraph("3）页面同时展示“提交到 DolphinDB 的代码”，便于追踪脚本执行。", body))
  img4 = scaled_image(SHOT_DIR / "04_tasks_page_list.png", doc.width, 105 * mm)
  story.append(img4)
  story.append(Paragraph("图 5. 任务页任务列表", caption))
  story.append(Spacer(1, 4))
  img5 = scaled_image(SHOT_DIR / "05_task_result_overview.png", doc.width, 105 * mm)
  story.append(img5)
  story.append(Paragraph("图 6. 任务结果总览（KPI + 净值）", caption))

  story.append(PageBreak())

  img6 = scaled_image(SHOT_DIR / "06_task_result_code.png", doc.width, 115 * mm)
  story.append(img6)
  story.append(Paragraph("图 7. 任务结果中的代码回显区域", caption))

  # Step 4
  story.append(Spacer(1, 10))
  story.append(Paragraph("步骤 4：在配置页管理连接参数", h2))
  story.append(Paragraph("入口：导航栏“配置页”。", body))
  story.append(Paragraph("操作：", body))
  story.append(Paragraph("1）设置 DolphinDB Host/Port/账号和候选数据节点端口。", body))
  story.append(Paragraph("2）设置 LLM Provider、Base URL、Model、API Key 等参数。", body))
  story.append(Paragraph("3）点击保存后，顶部状态栏会反映最新连接状态。", body))
  img7 = scaled_image(SHOT_DIR / "07_settings_page_full.png", doc.width, 118 * mm)
  story.append(img7)
  story.append(Paragraph("图 8. 配置页（DDB + LLM）", caption))

  # End
  story.append(Spacer(1, 10))
  story.append(Paragraph("4. 常见建议", h1))
  story.append(Paragraph("1）先在因子页完成条件构建，再进入回测页提交任务，可减少重复调整。", body))
  story.append(Paragraph("2）任务页支持并行任务观察，建议优先关注失败任务错误信息。", body))
  story.append(Paragraph("3）语义输入用于快速起稿，最终以任务页代码回显为执行依据。", body))

  doc.build(story)
  return OUT_PDF


if __name__ == "__main__":
  output = build_pdf()
  print(output)

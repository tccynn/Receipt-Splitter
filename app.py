import streamlit as st
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

def to_dec(v):
    try:
        return Decimal(str(v)) if v else Decimal("0")
    except Exception:
        return Decimal("0")

def fmt2(d):
    return str(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def fmt3(d):
    return str(d.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))

def rows_to_df(rows, members):
    return pd.DataFrame([
        {"单价":  r.get("price"),
         "数量":  int(r.get("qty") or 1),
         "折扣":  r.get("discount"),
         **{f"权重_{m}": int(r.get("weights", {}).get(m) or 0) for m in members}}
        for r in rows
    ])

def df_to_rows(df, members):
    return [
        {"price":    r.get("单价"),
         "qty":      int(r.get("数量") or 1),
         "discount": r.get("折扣"),
         "weights":  {m: int(r.get(f"权重_{m}") or 0) for m in members}}
        for _, r in df.iterrows()
    ]

# 初始化
st.set_page_config(page_title="小票分摊计算器", layout="wide")
if "members" not in st.session_state:
    st.session_state.members = ["成员 1", "成员 2"]
if "rows" not in st.session_state:
    st.session_state.rows = []
if "input_version" not in st.session_state:
    st.session_state.input_version = 0

CURRENCY_SYMBOLS = {
    "人民币 (¥)": "¥",
    "英镑 (£)": "£",
    "美元 ($)": "$",
    "欧元 (€)": "€",
    "港币 (HK$)": "HK$",
    "日元 (JP¥)": "JP¥",
    "韩元 (₩)": "₩",
    "澳元 (A$)": "A$",
    "加元 (C$)": "C$",
    "新加坡元 (S$)": "S$",
}
if "currency" not in st.session_state:
    st.session_state.currency = "人民币 (¥)"


# 侧边栏：成员管理
with st.sidebar:
    st.header("成员管理")
    
    st.write("**添加新成员**")
    c1, c2 = st.columns([4, 1])
    new_member = c1.text_input("新成员名", placeholder="输入名称", label_visibility="collapsed")
    if c2.button("＋") and new_member and new_member not in st.session_state.members:
        st.session_state.members.append(new_member)
        st.rerun()

    st.write("**成员列表**")
    for i, m in enumerate(st.session_state.members):
        mc1, mc2 = st.columns([4, 1])
        edited_name = mc1.text_input(
            f"member_{i}", value=m, key=f"member_name_{i}", label_visibility="collapsed"
        )
        if mc2.button("✕", key=f"del_mem_{m}"):
            st.session_state.members.remove(m)
            for row in st.session_state.rows:
                row["weights"].pop(m, None)
            st.rerun()

        # 改名：用户编辑了输入框且新名字未被占用
        if edited_name != m and edited_name.strip() and edited_name not in st.session_state.members:
            st.session_state.members[i] = edited_name
            for row in st.session_state.rows:
                if m in row["weights"]:
                    row["weights"][edited_name] = row["weights"].pop(m)
            st.rerun()

    st.caption("成员列表即所有参与人，可随时增加、删除或改名，刷新页面后恢复为默认。")

# 主页面
selected_members = st.session_state.members

if not selected_members:
    st.warning("请先在侧边栏添加至少一位成员，再开始录入明细。")
    st.stop()

st.session_state.currency = st.selectbox(
    "**货币单位**", options=list(CURRENCY_SYMBOLS.keys()),
    index=list(CURRENCY_SYMBOLS.keys()).index(st.session_state.currency)
)
currency_symbol = CURRENCY_SYMBOLS[st.session_state.currency]

st.divider()
st.subheader("明细录入")

# 已录入条目表格
col_cfg = {
    f"单价 ({currency_symbol})": st.column_config.TextColumn("单价"),
    "数量": st.column_config.NumberColumn("数量", step=1),
    f"折扣 ({currency_symbol})": st.column_config.TextColumn("折扣"),
    **{f"权重_{m}": st.column_config.NumberColumn(f"{m}权重", step=1)
       for m in selected_members}
}

if st.session_state.rows:
    edited_df = st.data_editor(
        rows_to_df(st.session_state.rows, selected_members),
        num_rows="fixed",
        use_container_width=True,
        column_config=col_cfg,
        hide_index=True,
    )
    st.session_state.rows = df_to_rows(edited_df, selected_members)
else:
    st.caption("暂无条目，请在下方添加")

# 新条目输入区
v = st.session_state.input_version
in_c1, in_c2, in_c3 = st.columns(3)
new_price    = in_c1.text_input(f"**单价 ({currency_symbol})**", placeholder="请输入单价", key=f"new_price_{v}")
new_qty      = in_c2.number_input("**数量**", step=1, value=None, placeholder="1", key=f"new_qty_{v}")
new_discount = in_c3.text_input(f"**折扣 ({currency_symbol})**", placeholder="0", key=f"new_discount_{v}")

# 权重预设
preset_options = ["均分"] + [f"仅{m}" for m in selected_members] + ["自定义"]
weight_preset = st.radio("**分摊权重**", preset_options, horizontal=True, key=f"preset_{v}")

new_weights = {}
if weight_preset == "均分":
    for m in selected_members:
        new_weights[m] = 1
elif weight_preset == "自定义":
    w_cols = st.columns(len(selected_members))
    for i, m in enumerate(selected_members):
        new_weights[m] = w_cols[i].number_input(f"{m} 权重", step=1, value=None,
                                                  placeholder="0", key=f"new_w_{m}_{v}")
else:
    full_member = weight_preset.replace("仅", "")
    for m in selected_members:
        new_weights[m] = 1 if m == full_member else 0

if st.button("＋ 添加新项目", use_container_width=True, type="primary"):
    try:
        price_val = str(Decimal(new_price)) if new_price.strip() else None
    except Exception:
        st.error("单价格式不正确，请输入有效数字")
        st.stop()
    try:
        discount_val = str(Decimal(new_discount)) if new_discount.strip() else None
    except Exception:
        st.error("折扣格式不正确，请输入有效数字")
        st.stop()

    st.session_state.rows.append({
        "price":    price_val,
        "qty":      new_qty or 1,
        "discount": discount_val,
        "weights":  {m: new_weights[m] or 0 for m in selected_members}
    })
    st.session_state.input_version += 1
    st.rerun()

# 计算
st.divider()
total_net = Decimal("0")
total_discount = Decimal("0")
member_sums = {m: Decimal("0") for m in selected_members}

for row in st.session_state.rows:
    price = to_dec(row.get("price"))
    if price == 0:
        continue
    qty      = Decimal(str(row.get("qty") or 1))
    discount = to_dec(row.get("discount"))
    total_discount += discount
    item_net = price * qty - discount
    total_net += item_net
    total_w = sum(Decimal(str(row["weights"].get(m, 0))) for m in selected_members)
    if total_w > 0:
        for m in selected_members:
            w = Decimal(str(row["weights"].get(m, 0)))
            member_sums[m] += item_net * w / total_w

st.subheader("分摊结果")
for m, amt in member_sums.items():
    c1, c2 = st.columns(2)
    c1.write(f"**{m}**")
    c2.write(f"{currency_symbol} {fmt3(amt)}")

# 导出 Excel
def build_excel():
    detail_rows = []
    for row in st.session_state.rows:
        price = to_dec(row.get("price"))
        if price == 0:
            continue
        qty = Decimal(str(row.get("qty") or 1))
        discount = to_dec(row.get("discount"))
        item_net = price * qty - discount
        detail_rows.append({
            f"单价 ({currency_symbol})": fmt2(price),
            "数量": int(qty),
            f"折扣 ({currency_symbol})": fmt2(discount),
            f"小计 ({currency_symbol})": fmt2(item_net),
            **{f"{m}权重": row["weights"].get(m, 0) for m in selected_members}
        })
    detail_df = pd.DataFrame(detail_rows)

    summary_df = pd.DataFrame(
        [{f"总支付金额 ({currency_symbol})": fmt2(total_net), f"总折扣 ({currency_symbol})": fmt2(total_discount),
          **{f"{m}应付 ({currency_symbol})": fmt2(member_sums[m]) for m in selected_members}}]
    )

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="汇总", index=False)
        detail_df.to_excel(writer, sheet_name="明细", index=False)
    buffer.seek(0)
    return buffer

if st.session_state.rows:
    st.download_button(
        "导出为 Excel",
        data=build_excel(),
        file_name=f"【{currency_symbol}{fmt2(total_net)}】分摊明细.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# 校验
st.divider()
st.subheader("校验")
vc1, vc2 = st.columns(2)
vc1.metric("输入条目总额", f"{currency_symbol} {fmt2(total_net)}")
vc2.metric("输入折扣总额", f"{currency_symbol} {fmt2(total_discount)}")
st.caption("若与小票上信息不一致，请仔细检查明细中的单价、数量、折扣是否输入正确。")
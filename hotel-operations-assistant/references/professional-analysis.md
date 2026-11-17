# 收益与财务：受限场景测算
先确认用途、数据覆盖、期间、酒店、币种与税口径。用大白话解释选择，不要求新手掌握下面字段。示例输入在../assets/professional-examples；数字完全虚构。正式调用统一使用bound_execution.py，操作与文件哈希纳入选定方案。professional_tools.py的函数仅供测试及绑定执行器调用，不绕过确认直接用于业务。

通用context：property_id、currency（三位大写，脚本不换汇）、tax_basis=tax_inclusive/tax_exclusive/not_applicable、period_start/period_end、as_of、source、basis。basis写明收入/成本范围、税处理、假设及排除。金额用点号十进制字符串、最多两位小数；不接受空值当零、千分位或币种符号。此脚本面向两位货币练习；其他精度另选工具。输入里的0必须确有依据。CSV先按确认映射另存；脚本不猜税务与会计科目。结果均待业务复核，不自动变成经营决策。

## 渠道净贡献（channel）
每渠道room_nights、gross_room_revenue、refunds、commission、payment_fee、marketing_cost、variable_room_cost、ancillary_contribution。
净贡献=房费-退款-佣金-支付费-营销费-房间变动成本+附加业务净贡献。附加业务已扣对应成本；退款/佣金不可重复扣。给贡献总额和每房晚值，0房晚返回不适用。比较同期间和成本边界；不是GOP、实际到账或完整客户终身价值。

## 团队订单（group）
按入住日列nights：stay_date、remaining_rooms（扣除在手承诺及停用后的剩余）、group_rooms、additional_transient_demand（未来新增散客需求假设）、group_rate、transient_rate、variable_cost_per_room、两类commission_rate、group_ancillary_contribution、extra_group_cost。
被挤占散客房晚=min(散客新增需求,剩余)-min(散客新增需求,剩余-团队房量)。
增量贡献=团队净房费贡献+附加业务净贡献-额外团队成本-被挤占散客贡献。
逐夜计算再汇总，不能用全期平均空房掩盖满房夜。团队超剩余容量直接拒算。对低/中/高需求分别计算，保留输入假设。不预测需求、不自动接单；未含房型替代、会议场地冲突、团队减房、合同赔偿与长期客户价值。负的散客单位贡献应先核对，不能盲目认为挤出散客就是收益。

## OTA结算对账（ota）
expected/actual按channel+reservation_id+settlement_id唯一；expected有gross/refunds/commission/fees/due_date，actual有net_paid。
应结=房费-退款-佣金-费用，差额=实际净结算-应结。输出matched/difference/missing_actual/not_due_no_actual/unmatched_actual。缺付款文件不能断言欠款。分批支付、冲销、代收模式先明确映射；重复键不合并。结算日期和住宿期间可能不同，方案写明筛选规则及覆盖范围；不以押金代收入、不据对账差异直接追款。

## 应收账龄（aging）
invoice_id、invoice_date、due_date、original_amount、credits、paid；已付及贷项是截至as_of累计额。
余额=原应收-贷项-已付。到期当天归未逾期；之后分1–30、31–60、61–90、90以上天。负余额单列credit_balance，不抵消其他客户逾期。账龄桶是展示约定，非催收政策，不擅定坏账或DSO阈值。账单ID保留前导零，跨店跨币种分别分析。

## 13周现金（cash）
opening_cash及13条连续weeks，每周week_start；period_end=开始日+90天。
流入guest_receipts/other_receipts/financing_in；流出operating_payments/tax_payments/capex/debt_service/owner_distributions。各分类必填且不重复。
期末=期初+流入-流出，下周承接。收入不等于现金；押金退款、税款、贷款本金利息、资本开支和业主分配应按真实现金时点归类，分类边界写进basis。负余额提示资金缺口，不构成贷款建议。输入由酒店假设/预算给出，脚本本身不做预测。

## 部门损益工作表（pnl）
各department列revenue、cost_of_sales、payroll、other_direct_cost；另列undistributed_cost。
计算部门利润及减未分配成本后的结果。basis列未计项目/分摊方法；没有经批准USALI科目映射时不得标GOP、净利润或审计报表。预算差异可采用同口径两套输入后对照，不伪造预算/去年同期。

依据核验2026-11-16：[Cloudbeds团队置换方法](https://www.cloudbeds.com/hotel-group-business/displacement-analysis/)支持比较团队和散客及变动成本的方法；具体公式、输入约束、账龄桶、现金列和样例是本技能独立编写的工作表约定，不称行业强制标准。调用时可按新情况核实方法；具体税务、会计确认及合同争议另查适用依据。


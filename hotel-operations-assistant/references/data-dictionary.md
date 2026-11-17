# 酒店数据字典和导入映射

仅处理用户选定范围的导出副本，不连接PMS，不要求同事学习字段名。助手先用表头及必要少量行理解资料；需求确认后提出映射和核查方案；方案确认后批量分析。参考字段是独立设计，不是对任一系统导出格式的兼容承诺。

## 统一字段

| 数据组 | 核心字段 | 判断规则 |
|---|---|---|
| 文件溯源 | source_file、source_sheet、source_row、exported_at | 原始物理行/表行必须可回溯，转换后行号另记；不把CSV多行字段的记录序号说成物理行号 |
| 公共口径 | property_id、business_date、currency、tax_basis | business_date是酒店营业日，不擅自从付款日期推导；多店/多币种不得直接汇总 |
| 订单与住宿 | reservation_id、room_id、arrival、departure、reservation_status | 订单ID和房号用文本保留前导零；房号不作为订单唯一键；入住/退房边界按实际时间和酒店规则 |
| 经营日汇总 | available_room_nights、sold_room_nights、room_revenue | 房晚与间数/订单数分开；免费房、停用房和收入范围见metrics.md |
| 账务事件 | transaction_id、reservation_id、folio_id、transaction_type、amount、currency、posted_at、reference_id | 金额十进制，不用二进制浮点算财务合计；支付、押金、应收、收入、退款/冲销分开 |
| 渠道 | channel、gross_room_revenue、commission、subsidy、payment_fee、confirmed_cancellations | 费用和收入对应期间/订单；取消率分母必须说明 |
| 客房服务 | task_id、room_id、task_type、assignee、accepted_at、status、completed_at、inspector、inspection_result、inspected_at | 清扫与验收独立记录，见housekeeping-ledger.md |

## 映射表

原文件/工作表｜原字段｜标准字段｜含义/单位｜转换方法｜依据｜确认状态｜未映射原因。

“营业额”可能含餐饮，“入住数”可能是人数，“实收”可能包含押金，都不可仅凭名字强行映射。原字段同名含义不同或同义字段重复时先核实。保持原值及转换值，非法金额、缺值、负数单列；不把空值或破折号转换为零，不删疑似重复记录。

缺字段输出“无法判断：缺……”，而非“未发现问题”。汇总只纳入已确认且可比较记录，列排除数量和未覆盖范围；部分覆盖不得声称整店报表完整。

## 随包经营汇总检查器

scripts/check_daily_metrics.py只读标准化CSV，输出JSON到标准输出，不改源文件。必需列：property_id,business_date,currency,available_room_nights,sold_room_nights,room_revenue。数据已由助手按确认的映射另存标准化副本才可用；不直接猜中文表头。不含税费换算、押金识别、自动去重或会计审计。

运行：python scripts/check_daily_metrics.py 已确认映射的日汇总.csv

只支持严格YYYY-MM-DD日期、非负整数字段房晚、点号小数金额（小数不超过2位，负收入标需复核，千分位及币种符号须先经确认转换）。缺失或非法字段不计算该行；重复“酒店+营业日+币种”行均标待核，不自动汇总；零可售房晚对应OCC和RevPAR为不适用。结果中的source_record为CSV记录序号，不是文件物理行号。每行独立处理，不做跨币种总计；单个货币的小数精度若不适用需另行选择工具。

脚本复验：python -B tests/test_daily_metrics.py。仅验证日汇总检查器；不验证模型两次确认、客房台账或完整夜审行为。异常行若返回指标仅是待核计算值，不能直接进入正式经营结论。

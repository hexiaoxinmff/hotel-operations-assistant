# 客房/维修交接与验收
新手例句：“把今天没做完的交给下一班，哪些房可以说处理好了？”

## 需求确认
确认班次、任务范围、负责岗位、现场检查规则；任务关闭不直接改可售房态。

## 输入与字段
task_id、task_type、location、events：status、actor、at（含时区）、evidence；inspected有inspection_result，closed有真实confirmation_quote/message_ref。

## 方案与执行
先给适合资料条件的方案供选择。保留事件链→queued分配→assigned开工→in_progress完工→completed复核→inspected通过后关闭；失败返工/阻塞，列下一班责任和解除条件。记录不代表实际派单。

## 交付模板
任务状态、未闭环原因、交接清单、完成/验收证据。正式可用状态由现场规则/系统权限另确认。
表内必留来源、统计期间/口径、状态和待核项；未知不填0。建议责任/时限没有批准就标建议。

## 完整虚构案例
虚构T001按样例经分配、开工、完成、检查通过、领班确认后closed。T002员工说修好了但无检查，仍completed，不标可售；T003查房fail不能closed，退回in_progress并记录复查。
输入与示范产物见../../assets/task-packs/../professional-examples/handover.json与handover-output.md。示范不代表真实酒店结果。

## 验收标准
completed不能跳过inspected关闭；fail不能关闭；时间有时区且有序；保留完成/验收分离；无系统返回不称已同步房态。
文件/自检通过只标待用户验收；用户反馈成功后再询问保存经验。


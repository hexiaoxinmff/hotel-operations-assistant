# 只读数据适配与能力注册
当前实现只有用户选定UTF-8 CSV导出副本→显式映射→保留原值的JSON，不连接PMS/OTA。工具名、开源README、平台页面或曾经可用都不能证明本轮权限。

## 文件适配合同
配置为context、mapping（标准字段:原表头）、schema（同一组标准字段:text/date/money/integer）、unique_keys、encoding=utf-8-sig或utf-8。不自动改日期格式、去千分位、换汇、拆单、合并或去重；必要转换单列映射依据并先确认。ID用text保留前导零。
bound_execution的import_csv同时绑定配置JSON和原CSV哈希；结果列source_record、raw、values、issues、duplicate_source_records、ready_for_analysis。source_record为记录序号非物理行号。有坏行或重复时ready_for_analysis=false，不能把其余行说成完整经营结果。原始缺失仍显示，不默默填0。CSV只是一个格式适配器，不承诺兼容任意供应商导出。XLSX可先用现有表格技能读取经确认区域并另存CSV；转换本身另记录源表/单元格和哈希。

## 能力注册
项目本地capabilities.json按模板填写capability_id、provider、mode、status、checked_at、evidence、data_scope、permissions、limitations。status用available_verified/declared_unverified/unavailable/not_configured。声明可用必须有本会话工具schema或成功返回证据；其他聊天成功不能直接提升本轮状态。服务账户和密钥不进入注册表、经验或技能包。只保存凭证配置引用名称，不保存值。
每次用前核查权限与资料截止日，引用快照和覆盖范围。分页、时区、取消/免费/停用房口径、跨店范围、请求失败、部分结果分别处理。缺接口时交付文件方案，不虚构同步或派发。

## 未来PMS适配合同（尚未实现）
先取得酒店系统名称/版本、供应商文档、数据处理和费用条件、门店只读权限。拟实现get_property/get_reservations/get_daily_metrics/get_room_tasks，并规范返回：
provider/property_id/as_of/timezone/currency/tax_basis、records、pagination_complete、warnings、source_request_id、coverage。
任何分页缺页/限流/超时都返回不完整状态，不能当整店全量。试点用合成或允许的沙箱，和导出副本逐项核对。默认只读；写能力独立注册、独立授权，不能复用读取批准。状态未知先只读查最终结果，写失败不盲重试。

[Apaleo权限文档](https://apaleo.dev/guides/api/scopes.html)、[分页文档](https://apaleo.dev/guides/api/pagination.html)为2026-11-16核查的具体供应商示例，不代表当前酒店使用Apaleo或其他PMS遵循相同字段。本技能未部署MCP服务。


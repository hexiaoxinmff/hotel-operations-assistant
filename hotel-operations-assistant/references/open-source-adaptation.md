# 开源调研转化说明

2026-11-16，按用户确认方案，将开源调研中的可用设计转化为平台无关参考和独立编写的CSV检查器。本包未复制、打包或安装候选仓库源码，不内置PMS、预测模型、取消概率或清扫工时默认值；没有直接依赖第三方包。

- [HAIP](https://github.com/TelivityAI/haip)：借鉴分析/建议/执行/结果分层、输入快照及异常分类思路；不启用其自动执行模式，不将返回success当实际执行凭证。
- [OCA vertical-hotel](https://github.com/OCA/vertical-hotel/tree/19.0)：参考客房任务和检查字段组织；独立定义查验通过与关闭条件，不照搬其局部状态/时间校验。
- [ERPNext社区酒店模块](https://github.com/Gifted87/erpnext_hospitality_core)：借鉴个人账/公司账及夜审核查场景，不复制代码、不沿用固定夜审时间。

以上仓库不是本酒店政策或法规的权威来源。未来复制具体实现时重新固定commit、核对文件及依赖许可证、保留声明并隔离测试。Darts预测、QloApps整套PMS及任何线上支付/渠道集成仍为后续候选，本版未实现。

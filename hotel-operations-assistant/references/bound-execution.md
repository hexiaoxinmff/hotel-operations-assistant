# 绑定执行范围与回执
适用于新增facts/import_csv/channel/group/ota/aging/cash/pnl/handover的正式JSON任务。旧版价格、图片、Office等CLI保留原阶段门槛，尚未统一获得本节的文件哈希绑定；使用这些旧入口须按task-record另记输入输出，不得声称已全面实现系统级控制。

1. 在方案阶段准备job.json：schema=1、operation、input_files（data:{path:绝对路径,sha256:输入SHA256}；import_csv再加csv）、output_root、output_file（根内新JSON）。job文件字节SHA256加入所选方案job_sha256数组。facts/import_csv/handover归workflow动作research；其余计算归metrics。这不授予外部改价、记账等权限。
2. 向同事展示具体操作、输入文件/版本、产物位置、数据范围与限制，不要求同事理解哈希。真正确认后，使用workflow_guard记录原话和消息引用；不可用虚构测试确认代替业务授权。增加/修改job需要新方案版本及确认；不为已确认范围的解释性小修反复问。
3. 调用：python scripts/bound_execution.py --job 绝对路径/job.json --workflow 绝对路径/workflow.json --requirement-version 1 --plan-version 1。需求及方案版本、动作、job哈希、输入内容和路径、输出根均检查。
4. 输入用内存快照计算，写前重核源文件/job和阶段；不覆盖已有结果或回执。成功回执含任务/版本、输入与输出SHA256、时间、completed、pending_user_review；失败含failed及原因。回执是工具执行证据，不代表业务验收。失败后先检查回执和结果状态，修正原因后按需更新方案，选择新输出；不删回执假装未执行。
5. 用户确认解决后再询问是否保存成功经验。只读数据检查通过不能自动置为成功。

方案示例：{"id":"A","description":"按确认口径做本地净贡献测算","deliverables":"JSON结果及回执","constraints":"不外传、不改系统；缺数据拒算","actions":["metrics"],"job_sha256":["实际job字节SHA256"]}。不要将示例假确认写进真实任务。

边界：状态文件/原话由助手依据聊天记录填入，工具不能认证聊天身份，也不能阻止拥有本机权限者直接修改状态或调用底层函数；回执未签名。平台原生工具与旧入口不能受此脚本全局约束。外部平台权限与真实人工确认仍不可替代。绑定不是文件访问沙箱，输入必须另在用户授权范围内选择。


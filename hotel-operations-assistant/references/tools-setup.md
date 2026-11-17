# 本地工具配置与调用

任务开始读取当前用户主目录HotelOperationsMemory/hotel-operations-assistant/tools.json，或用户指定的HOTEL_ASSISTANT_TOOLS_CONFIG文件。它是本机运行路径和目录范围配置，不是业务授权；不能据配置跳过需求、方案、经验保存确认。没有配置就先探测平台已有能力，不假定任何接收方拥有开发机路径。

## 按顺序使用

1. 文件：优先平台内置文件读写/检索；缺少时可调用toolkit.py的list/read受限入口。只访问配置read_roots；OCR和基础办公输出限定write_roots，拒绝覆盖现有文件。配置不构成操作系统级沙箱，模型和平台权限仍需共同控制，不能保证任意shell都被约束。
2. Python：用配置python执行OCR及普通工具，用office_python执行本平台文档输出。既有check_daily_metrics.py、local_memory.py和research_tools.py继续可用，不必另建PMS。
3. OCR：使用配置python运行scripts/toolkit.py --config 配置.json ocr 本地图.png --output 新结果.json。RapidOCR+ONNX Runtime在本机识别；包装器识别期间阻止socket连接，模型缺失则失败，先单独准备模型再重试。不传URL、不自动上传文件。输出文字、置信分和框仅是待核稿；每次批量前先用代表样例核对中文、金额和否定词，不因工具安装成功就承诺准确率。
4. 办公输出：有用户模板优先专门的表格/文档工具，保留格式，不用简化生成器改模板。无模板的新建基础稿可用office_output.py（docx/pdf）及table_output.mjs（xlsx）。输入为本地结构化JSON，命令见下文。Word生成须页面渲染复核；若缺LibreOffice且不能自动渲染，明确标待使用者在Word/WPS检查，不能以PDF另行排版冒充同一DOCX渲染。PDF可用pdftoppm渲染，Excel优先用平台表格渲染器预览，若本机渲染失败须标待Excel/WPS复核；检查中文、分页、列宽、金额及ID。
5. 联网：使用运行平台现有网页搜索/读取及GitHub连接器；记录来源、日期和核查范围，不把库requests当搜索引擎。无平台搜索时标联网不可用，先做本地分析。没有配置付费搜索API或凭证，不承诺技能ZIP能给别的Agent自动开通联网。

## 命令与输入

新增收益/财务、事实检查、交接与CSV适配使用[绑定执行入口](bound-execution.md)，配置python执行scripts/bound_execution.py。无需新依赖；项目可在既有本地启动器加job路由。项目路径保存在项目资料中，通用技能不写死特定酒店。

若当前工具配置同目录已有项目资料/project-settings.json且用户正在处理该项目，先只读加载其中registry_path及capabilities_path；找不到则沿用用户已指定的位置或按property-registry说明列缺项。项目配置是路径与范围记录，不是业务执行批准，也不覆盖当前用户要求。

- python scripts/toolkit.py --config 配置.json status / list 目录 / read 文本文件
- 使用office_python运行scripts/office_output.py --config 配置.json --input 内容.json --output 新文件.docx --format docx（或pdf）
- 使用配置node运行scripts/table_output.mjs 配置.json 表格.json 新文件.xlsx

文档JSON：title字符串，paragraphs字符串数组，table可选二维表，最多6列。仅适用于基础报告，复杂模板/图片/多分节应转专门工具。表格JSON：rows二维值数组，每行列数相同，最多20列/10000行，编号用字符串保留前导零；不支持在输入中写待执行公式。Excel基础导出器不自动生成预览；需另用平台渲染器或Excel/WPS核对所有有效范围。

本机路径、依赖版本和安装测试记录保存在独立工具目录，通用技能包不携带虚拟环境、公司资料、模型文件或个人记忆。新设备需重新配置，不复制旧电脑绝对路径直接使用。无需额外安装Filesystem MCP或外部OCR云服务才能在本平台使用已有本地能力。

官方参考：[RapidOCR安装](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/install/)及[Python使用接口](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/usage/)，2026-11-16核查。依赖选择以本机实测和独立工具目录requirements-installed.txt为准。

自v0.8起，正式执行命令必须带[workflow-contract.md](workflow-contract.md)所列状态及版本参数；旧示例仅表示业务参数，不能省略执行检查。Excel追加状态路径、需求版本、方案版本。状态/文件清点仍只用于理解，不提前进行正式批量任务。

# 周结果资料读取

用户入口为 [evaluate.py](../evaluate.py)，操作见 [Evaluation Center](../../evaluation-center/README.md#运行评测)。阅读结果见 [周摘要目录](../../docs/evidence/README.md)。

`index.json` 记录按周数据包的路径、文件大小和摘要；解包前逐项检查内容。`documents.zip` 仅保存旧接口读取所需的 Markdown 资料，不包含 Python 实现。

运行时复制当前源码到临时目录，并在临时目录重建原始资料路径。业务代码不会从数据包恢复。输出参数转换为用户工作目录下的绝对路径，结果在临时目录清理后仍保留；秘密配置和运行数据库不复制。

更改归档格式后，使用 Agent 环境运行本目录 `test_layout.py`。不要在项目根目录手工展开 ZIP，也不要把机器记录直接拼成一份人工阅读文档。

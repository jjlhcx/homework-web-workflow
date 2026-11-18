# 来源与版本

本测试版的 cx.py、page.js 及基础测试复用本项目此前编写的本地草稿助手。新增便携启动、旧列表读取、项目技能与发行检查。没有直接复制其他仓库的学习通技能、CLI 源码、浏览器扩展或 OCS 安装包。

可选工具参考：

- https://github.com/Tencent/BrowserSkill ：已试验版本 0.5.0，未捆绑分发。若现有 Agent 已连接它，可使用 page.js 语义动作，不能跳过预检与回读。
- https://github.com/Han-maker-wp/xuexitong-cli-skill ：之前审查提交 5d3cc47，MIT；只作方案参考，本测试版不下载或安装该项目。
- https://github.com/ocsjs/ocsjs ：本测试版不含刷课、题库或 OCS 功能。

Python 依赖见 requirements.txt。Playwright、greenlet 由 setup.ps1 从包源按版本安装到 vendor，沿用各自许可；测试版压缩包不带依赖二进制或个人 Python 运行时。公开平台适配自述不等于本项目验收结果。

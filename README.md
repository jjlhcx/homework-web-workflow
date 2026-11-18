# AI 作业工作流：本地测试版

当前可下载：[v0.3.2 公开预发布](https://github.com/jjlhcx/homework-web-workflow/releases/tag/v0.3.2)。本次试用限 Windows 电脑版 WorkBuddy，读取本人已完成的学习通普通作业，不填写、不暂存、不提交。压缩包中的开发文档保留了打包时的测试记录。

仅做电脑浏览器中的学习通页面。首批环境 Windows＋Edge＋Python 3.10+；需要能执行命令和访问本地文件的 AI。AI 自己生成答案，本工具负责页面读取、填写、暂存和核对，不提供模型账号、API 额度或后台模型服务。

## 开始

舍友测试入口：将测试包与 LAUNCH.json 的全文一起交给有本地文件和命令能力的 AI。LAUNCH.json 只有英文字符，是结构化任务说明，无需使用者执行或理解其中技术步骤。测试记录要求见 ROOMMATE-TEST.md。

把 [START.md](START.md) 的第一段发给 AI，并让它访问本地目录。项目内技能位于 [SKILL.md](skills/homework-web/SKILL.md)，无需修改全局客户端配置。

先运行 `./doctor.ps1`。会检查 PATH、注册表和常见的个人 Python 安装目录；也可用 CX_PYTHON 指定。依赖缺少时运行 `./setup.ps1`，只安装到本目录 vendor。已有可用依赖直接复用；否则优先试用 wheelhouse 的离线包。在线下载失败时停止，可将与所用 Python 和 Windows 架构匹配的官方 wheel（含传递依赖）放进 wheelhouse 后重试。

在项目目录双击 Open-Edge.cmd，然后登录并打开指定作业。本人启动的窗口不依赖 AI 后台任务。也可以在自己的终端运行 `./cx.ps1 open`。登录资料保存在本目录 .browser-profile，不能分享。让 AI 先执行 `check` → `read`；首次测试只读。参数见 `./cx.ps1 --help`。

可用环境变量 CX_PYTHON 指定现有 Python 可执行文件，CX_BROWSER 指定已安装 Edge 路径。所有命令从本目录执行；其他目录使用 cx.ps1 的绝对路径。调试连接只接受本机 HTTP 端口，默认 9222；若端口被占用可用 `./cx.ps1 --endpoint http://127.0.0.1:9333 open`，后续命令使用相同 endpoint。

如果已有 Python，但自检报告 PYTHON_MISSING，可运行 `./setup.ps1 -PythonPath "C:\path\to\python.exe"`。只给一次可信可执行文件的完整路径，成功后本项目会记住它，不改系统 PATH。

## 当前能力

- 支持主作业页的稳定标识读题、普通文字、多空与可识别选择控件；冲突、页面身份变化、现有图片附件保护、暂存后刷新核对有自动化测试。
- 旧版 getAllWork 列表按作业卡片读取，避免“查看”重复与 JavaScript 入口漏项；未识别模板明确报错，空白页面不会当成已无作业。
- 不包含章节测验、附件上传、听力录音、正式考试或自动提交；其他学校、其他页面版本与手机 App 不由本轮结果外推。
- 查看页支持纯文本选择选项与填空答案的只读提取，排除外层题目容器。read 会返回题型统计与解析状态，全部无法识别时明确失败；已完成页不生成回填模板。一份实际已完成的 80 题作业已通过在线读取复测。
- `./cx.ps1 capture-images --course <ID> --work <ID> --limit 4` 为同一份普通作业预览最多四道含图题，只将题干和选项图片保存到本地。工具不会识别公式或回填图片题；能看图的 AI 还需要单独核对截图内容。

## 排错

PYTHON_MISSING：配置 Python 路径。DEPENDENCY_MISSING：运行 setup.ps1。BROWSER_UNAVAILABLE：运行 open，再 check；不要重新写 CDP 客户端。TARGET_NOT_FOUND：确保目标作业已打开且 ID 来自当前页面。AMBIGUOUS_TARGET／AMBIGUOUS_LIST：只保留一个匹配入口。UNSUPPORTED_LAYOUT：说明页面尚未适配。ANSWER_CONFLICT：展示差异，不覆盖用户内容。SAVE_UNCERTAIN：先重新读页面，不重复点保存。

仅有脱敏离线模拟页面进入测试。data、vendor、浏览器资料、真实课程页面不属于交付文件。详细验证结果见 docs/verification.md（完成本轮检查后填写）。

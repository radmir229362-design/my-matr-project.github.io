# my-matr-project.github.io
 My matr project on GitHub
modules = ["nodejs-24", "python-3.11"]

[[artifacts]]
id = "artifacts/api-server"

[[artifacts]]
id = "artifacts/mockup-sandbox"

[deployment]
router = "application"
deploymentTarget = "autoscale"

[deployment.postBuild]
args = ["pnpm", "store", "prune"]
env = { "CI" = "true" }

[workflows]
runButton = "Project"

[[workflows.workflow]]
name = "Project"
mode = "parallel"
author = "agent"

[[workflows.workflow.tasks]]
task = "workflow.run"
args = "МАКС Telegram Bot"

[[workflows.workflow.tasks]]
task = "workflow.run"
args = "МАКС Telegram Bot 2"

[[workflows.workflow]]
name = "МАКС Telegram Bot"
author = "agent"

[workflows.workflow.metadata]
outputType = "webview"

[[workflows.workflow.tasks]]
task = "shell.exec"
args = "cd bot && python main.py"
waitForPort = 5000

[[workflows.workflow]]
name = "МАКС Telegram Bot 2"
author = "agent"

[[workflows.workflow.tasks]]
task = "shell.exec"
args = "cd bot && python main2.py"

[workflows.workflow.metadata]
outputType = "console"

[agent]
stack = "PNPM_WORKSPACE"
expertMode = true

[postMerge]
path = "scripts/post-merge.sh"
timeoutMs = 20000

[nix]
channel = "stable-25_05"
packages = ["xcodebuild", "zlib"]

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKBENCH = ROOT / "web" / "chiling-workbench"
APP_PATH = WORKBENCH / "app.js"
STATE_PATH = WORKBENCH / "src" / "state.js"
API_CLIENT_PATH = WORKBENCH / "api-client.js"
STYLE_PATH = WORKBENCH / "styles.css"
VIEWS_DIR = WORKBENCH / "src" / "views"
README_PATH = WORKBENCH / "README.md"
DESIGN_QA_PATH = ROOT / "design-qa.md"


def test_chiling_frontend_exposes_production_queue_contract():
    api_client = API_CLIENT_PATH.read_text(encoding="utf-8")
    app = APP_PATH.read_text(encoding="utf-8")
    views = "\n".join(path.read_text(encoding="utf-8") for path in sorted(VIEWS_DIR.glob("*.js")))
    frontend_ui = app + "\n" + views
    frontend_state = app + "\n" + STATE_PATH.read_text(encoding="utf-8")
    frontend_browser_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            APP_PATH,
            STATE_PATH,
            WORKBENCH / "src" / "format.js",
            WORKBENCH / "src" / "task-model.js",
            WORKBENCH / "src" / "dom.js",
            WORKBENCH / "src" / "components" / "ui.js",
            WORKBENCH / "src" / "components" / "topbar.js",
            *sorted(VIEWS_DIR.glob("*.js")),
        ]
    )
    styles = STYLE_PATH.read_text(encoding="utf-8")

    assert 'import {} from "./src/task-model.js";' not in app
    assert 'import {} from "./src/components/ui.js";' not in app
    assert "Legacy source-level safety checks" not in app
    assert "Moved view contract markers" not in app

    assert "async function listQueue()" in api_client
    assert "async function listProductionRequests()" in api_client
    assert "async function listOperations(taskId)" in api_client
    assert "async function runOperation(taskId, operationId)" in api_client
    assert "async function listReviewDraft(taskId)" in api_client
    assert "async function saveReview(taskId, reviewPayload)" in api_client
    assert "async function approveGeneration(taskId, confirmationPhrase)" in api_client
    assert "async function listProductionPrep(taskId)" in api_client
    assert "async function requestProduction(taskId, confirmationPhrase)" in api_client
    assert "async function claimProductionRequest(taskId, operatorName)" in api_client
    assert "async function completeProductionRequest(taskId, deliveryPayload)" in api_client
    assert "async function executeProductionAdapter(taskId, executionPayload)" in api_client
    assert "async function listProductionServiceStatus()" in api_client
    assert "async function listProductionServiceConfiguration()" in api_client
    assert "async function listProductionAuditLog()" in api_client
    assert "async function listTaskDetail(taskId)" in api_client
    assert 'request("/pipeline-queue")' in api_client
    assert 'request("/production-requests")' in api_client
    assert 'request("/production-service/status")' in api_client
    assert 'request("/production-service/configuration")' in api_client
    assert 'request("/production-audit-log")' in api_client
    assert '}/detail`)' in api_client
    assert '}/operations`)' in api_client
    assert '}/operations/actions`' in api_client
    assert '}/review-draft`)' in api_client
    assert '}/review-approval`' in api_client
    assert '}/generation-approval`' in api_client
    assert '}/production-prep`)' in api_client
    assert '}/production-request`' in api_client
    assert '}/production-claim`' in api_client
    assert '}/production-complete`' in api_client
    assert '}/production-execute`' in api_client
    assert "listQueue," in api_client
    assert "listProductionRequests," in api_client
    assert "listOperations," in api_client
    assert "runOperation," in api_client
    assert "listReviewDraft," in api_client
    assert "saveReview," in api_client
    assert "approveGeneration," in api_client
    assert "listProductionPrep," in api_client
    assert "requestProduction," in api_client
    assert "claimProductionRequest," in api_client
    assert "completeProductionRequest," in api_client
    assert "executeProductionAdapter," in api_client
    assert "listProductionServiceStatus," in api_client
    assert "listProductionServiceConfiguration," in api_client
    assert "listProductionAuditLog," in api_client
    assert "listTaskDetail," in api_client
    assert 'const deliveryReady = task.deliveryBackfill?.status === "delivered"' in api_client
    assert "Math.min(99" in api_client
    assert 'completed ? "completed"' not in api_client
    assert "queueEntries: []" in frontend_state
    assert "productionRequests: []" in frontend_state
    assert "productionServiceStatus: null" in frontend_state
    assert "productionServiceConfiguration: null" in frontend_state
    assert "productionAuditLog: null" in frontend_state
    assert "taskDetail: null" in frontend_state
    assert "detailDrawerOpen: false" in frontend_state
    assert "operationPanel: null" in frontend_state
    assert "reviewDraft: null" in frontend_state
    assert "productionPrep: null" in frontend_state
    assert "productionRequestPhrase" in frontend_state
    assert "refreshQueue" in app
    assert "refreshProductionRequests" in app
    assert "refreshProductionServiceStatus" in app
    assert "refreshProductionServiceConfiguration" in app
    assert "refreshProductionAuditLog" in app
    assert "openTaskDetail" in app
    assert "closeTaskDetail" in app
    assert "refreshOperations" in app
    assert "refreshReviewDraft" in app
    assert "saveReviewDecision" in app
    assert "approveGenerationGate" in app
    assert "refreshProductionPrep" in app
    assert "submitProductionRequest" in app
    assert "claimProductionRequest" in app
    assert "completeProductionRequest" in app
    assert "executeProductionAdapter" in app
    assert "renderQueueRows" in views
    assert "renderProductionRequestRows" in views
    assert "renderProductionServiceStatusPanel" in views
    assert "renderProductionServiceConfigurationPanel" in views
    assert "renderProductionAuditLogPanel" in views
    assert "renderTaskDetailDrawer" in app
    assert "renderTaskDetailSection" in views
    assert "renderOperationPanel" in views
    assert "renderReviewDraftPanel" in views
    assert "renderProductionPrepPanel" in views
    assert "runOperationAction" in app
    assert "解析摘要" in frontend_ui
    assert "data-refresh-review-draft" in frontend_ui
    assert "data-save-review" in frontend_ui
    assert "data-approve-review" in frontend_ui
    assert "data-generation-phrase" in frontend_ui
    assert "data-approve-generation" in frontend_ui
    assert "确认进入生产" in frontend_ui
    assert "保存审核稿" in frontend_ui
    assert "审核通过" in frontend_ui
    assert "后台操作面板" in frontend_ui
    assert "生产准备包" in frontend_ui
    assert "data-refresh-production-prep" in frontend_ui
    assert "确认提交生产" in frontend_ui
    assert "data-production-request-phrase" in frontend_ui
    assert "data-submit-production-request" in frontend_ui
    assert "data-refresh-operations" in frontend_ui
    assert "data-run-operation" in frontend_ui
    assert "后台生产队列" in frontend_ui
    assert "data-refresh-queue" in frontend_ui
    assert "生产执行队列" in frontend_ui
    assert "生产服务诊断" in frontend_ui
    assert "管理员配置" in frontend_ui
    assert "生产服务配置" in frontend_ui
    assert "生产执行审计" in frontend_ui
    assert "任务详情" in frontend_ui
    assert "人工审核记录" in frontend_ui
    assert "交付物" in frontend_ui
    assert "查看详情" in frontend_ui
    assert "data-open-task-detail" in frontend_ui
    assert "data-close-task-detail" in frontend_ui
    assert "提交生产请求" in frontend_ui
    assert "领取任务" in frontend_ui
    assert "尝试执行生产服务" in frontend_ui
    assert "生产服务预检" in frontend_ui
    assert "尝试执行生产服务、生产服务预检、人工回填交付" in frontend_ui
    assert "等待服务端执行器接管" in frontend_ui
    assert "人工回填交付" in frontend_ui
    assert "data-refresh-production-audit-log" in frontend_ui
    assert "不在页面填写密钥" in frontend_ui
    assert "仅服务端配置" in frontend_ui
    assert "data-refresh-production-service-configuration" in frontend_ui
    assert "真实生产服务" in frontend_ui
    assert "未启用" in frontend_ui
    assert "待配置" in frontend_ui
    assert "可连接" in frontend_ui
    assert "不会启动付费生成" in frontend_ui
    assert "data-refresh-production-service-status" in frontend_ui
    assert "data-refresh-production-requests" in frontend_ui
    assert "操作员执行" in frontend_ui
    assert "领取任务" in frontend_ui
    assert "执行中" in frontend_ui
    assert "data-claim-production-request" in frontend_ui
    assert "标记交付" in frontend_ui
    assert "data-complete-production-request" in frontend_ui
    assert "执行生产服务" in frontend_ui
    assert "data-execute-production-adapter" in frontend_ui
    assert "reference-video-analysis" not in frontend_browser_source
    assert "RUNNINGHUB" not in frontend_browser_source
    assert "DOUBAO" not in frontend_browser_source
    assert "ARK" not in frontend_browser_source
    assert "CHILING_PRODUCTION_SERVICE" not in frontend_browser_source
    assert ".task-detail-drawer__head .button" in styles
    assert "white-space: nowrap" in styles


def test_chiling_docs_describe_generation_approval_gate():
    readme = README_PATH.read_text(encoding="utf-8")
    design_qa = DESIGN_QA_PATH.read_text(encoding="utf-8")

    assert "POST /tasks/:taskId/generation-approval" in readme
    assert "GET /tasks/:taskId/production-prep" in readme
    assert "GET /production-requests" in readme
    assert "POST /tasks/:taskId/production-request" in readme
    assert "POST /tasks/:taskId/production-claim" in readme
    assert "POST /tasks/:taskId/production-complete" in readme
    assert "POST /tasks/:taskId/production-execute" in readme
    assert "GET /production-service/status" in readme
    assert "GET /production-service/configuration" in readme
    assert "GET /production-audit-log" in readme
    assert "GET /tasks/:taskId/detail" in readme
    assert '"confirmationPhrase": "确认进入生产"' in readme
    assert '"confirmationPhrase": "确认提交生产"' in readme
    assert "不会自动调用正式生成" in readme
    assert "生产准备包" in readme
    assert "提交生产请求" in readme
    assert "生产执行队列" in readme
    assert "领取任务" in readme
    assert "标记交付" in readme
    assert "生产服务诊断" in readme
    assert "生产服务配置" in readme
    assert "生产执行审计" in readme
    assert "任务详情" in readme
    assert "人工审核记录" in readme
    assert "交付物" in readme
    assert "尝试执行生产服务" in readme
    assert "不在页面填写密钥" in readme
    assert "执行生产服务" in readme
    assert "生产服务预检" in readme
    assert "等待服务端执行器接管" in readme
    assert "paidGenerationStarted" in readme
    assert "生成审批确认短语" in design_qa
    assert "生产准备包" in design_qa
    assert "提交生产请求" in design_qa
    assert "生产执行队列" in design_qa
    assert "领取任务" in design_qa
    assert "标记交付" in design_qa
    assert "生产服务诊断" in design_qa
    assert "生产服务配置" in design_qa
    assert "生产执行审计" in design_qa
    assert "任务详情" in design_qa
    assert "人工审核记录" in design_qa
    assert "交付物" in design_qa
    assert "尝试执行生产服务" in design_qa
    assert "不在页面填写密钥" in design_qa
    assert "执行生产服务" in design_qa
    assert "生产服务预检" in design_qa
    assert "等待服务端执行器接管" in design_qa
    assert "不会启动付费生成" in design_qa

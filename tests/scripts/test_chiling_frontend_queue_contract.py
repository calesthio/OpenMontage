from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_PATH = ROOT / "web" / "chiling-workbench" / "app.js"
API_CLIENT_PATH = ROOT / "web" / "chiling-workbench" / "api-client.js"
STYLE_PATH = ROOT / "web" / "chiling-workbench" / "styles.css"
README_PATH = ROOT / "web" / "chiling-workbench" / "README.md"
DESIGN_QA_PATH = ROOT / "design-qa.md"


def test_chiling_frontend_exposes_production_queue_contract():
    api_client = API_CLIENT_PATH.read_text(encoding="utf-8")
    app = APP_PATH.read_text(encoding="utf-8")
    styles = STYLE_PATH.read_text(encoding="utf-8")

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
    assert "queueEntries: []" in app
    assert "productionRequests: []" in app
    assert "productionServiceStatus: null" in app
    assert "productionServiceConfiguration: null" in app
    assert "productionAuditLog: null" in app
    assert "taskDetail: null" in app
    assert "detailDrawerOpen: false" in app
    assert "operationPanel: null" in app
    assert "reviewDraft: null" in app
    assert "productionPrep: null" in app
    assert "productionRequestPhrase" in app
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
    assert "renderQueueRows" in app
    assert "renderProductionRequestRows" in app
    assert "renderProductionServiceStatusPanel" in app
    assert "renderProductionServiceConfigurationPanel" in app
    assert "renderProductionAuditLogPanel" in app
    assert "renderTaskDetailDrawer" in app
    assert "renderTaskDetailSection" in app
    assert "renderOperationPanel" in app
    assert "renderReviewDraftPanel" in app
    assert "renderProductionPrepPanel" in app
    assert "runOperationAction" in app
    assert "解析摘要" in app
    assert "data-refresh-review-draft" in app
    assert "data-save-review" in app
    assert "data-approve-review" in app
    assert "data-generation-phrase" in app
    assert "data-approve-generation" in app
    assert "确认进入生产" in app
    assert "保存审核稿" in app
    assert "审核通过" in app
    assert "后台操作面板" in app
    assert "生产准备包" in app
    assert "data-refresh-production-prep" in app
    assert "确认提交生产" in app
    assert "data-production-request-phrase" in app
    assert "data-submit-production-request" in app
    assert "data-refresh-operations" in app
    assert "data-run-operation" in app
    assert "后台生产队列" in app
    assert "data-refresh-queue" in app
    assert "生产执行队列" in app
    assert "生产服务诊断" in app
    assert "管理员配置" in app
    assert "生产服务配置" in app
    assert "生产执行审计" in app
    assert "任务详情" in app
    assert "人工审核记录" in app
    assert "交付物" in app
    assert "查看详情" in app
    assert "data-open-task-detail" in app
    assert "data-close-task-detail" in app
    assert "提交生产请求" in app
    assert "领取任务" in app
    assert "尝试执行生产服务" in app
    assert "生产服务预检" in app
    assert "尝试执行生产服务、生产服务预检、人工回填交付" in app
    assert "等待服务端执行器接管" in app
    assert "人工回填交付" in app
    assert "data-refresh-production-audit-log" in app
    assert "不在页面填写密钥" in app
    assert "仅服务端配置" in app
    assert "data-refresh-production-service-configuration" in app
    assert "真实生产服务" in app
    assert "未启用" in app
    assert "待配置" in app
    assert "可连接" in app
    assert "不会启动付费生成" in app
    assert "data-refresh-production-service-status" in app
    assert "data-refresh-production-requests" in app
    assert "操作员执行" in app
    assert "领取任务" in app
    assert "执行中" in app
    assert "data-claim-production-request" in app
    assert "标记交付" in app
    assert "data-complete-production-request" in app
    assert "执行生产服务" in app
    assert "data-execute-production-adapter" in app
    assert "reference-video-analysis" not in app
    assert "RUNNINGHUB" not in app
    assert "DOUBAO" not in app
    assert "ARK" not in app
    assert "CHILING_PRODUCTION_SERVICE" not in app
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

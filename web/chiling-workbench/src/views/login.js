export function render() {
  return `
    <main class="page page--login">
      <header class="login-header">
        <div class="login-brand">
          <strong>赤灵AI运营工作台</strong>
          <span>企业内容生产入口</span>
        </div>
        <button class="button button--small" type="button" data-login>进入演示</button>
      </header>

      <section class="login-grid">
        <div class="panel panel--login panel--solid">
          <span class="pill">团队授权访问</span>
          <h1 class="hero-title" style="margin-top: 28px;">把参考视频变成可审核、可交付的运营素材。</h1>
          <p class="lede">粘贴视频链接，上传指定肖像，先由人工确认文案、字幕和素材授权，再进入批量生产。</p>

          <form class="form" data-login-form>
            <div class="field">
              <label for="account">账号</label>
              <div class="input-wrap">
                <input id="account" name="account" autocomplete="username" value="team@chiling.ai" />
              </div>
            </div>
            <div class="field">
              <label for="password">密码</label>
              <div class="input-wrap">
                <input id="password" name="password" type="password" autocomplete="current-password" value="chiling-demo" />
                <button class="text-link field-action" type="button" data-toast-title="验证码已发送" data-toast-message="演示环境已模拟发送。">验证码登录</button>
              </div>
            </div>
            <div class="form-row">
              <label class="check">
                <input type="checkbox" checked />
                <span>记住本设备</span>
              </label>
              <button class="text-link" type="button" data-toast-title="已切换入口" data-toast-message="企业验证码登录已准备。">企业验证码</button>
            </div>
            <button class="button button--primary button--wide" type="submit">登录工作台</button>
            <p class="fine-print">仅展示用户需要操作的流程信息，内部技术与接口不在前台暴露。</p>
          </form>
        </div>

        <aside class="panel panel--overview">
          <span class="pill pill--red">今日待处理 8</span>
          <h2 class="section-title section-title--large" style="margin-top: 30px;">从导入到交付，一条线完成。</h2>
          <p class="lede">团队成员可以在这里查看生产状态、审核文案、管理素材与下载交付包。</p>

          <div class="summary-card">
            <span class="pill pill--green">安全状态正常</span>
            <div class="metric-row">
              <div class="metric-card">
                <span class="metric-card__label">今日生成</span>
                <strong class="metric-card__value">24</strong>
                <i class="status-dot status-dot--green"></i>
              </div>
              <div class="metric-card">
                <span class="metric-card__label">待审核</span>
                <strong class="metric-card__value">6</strong>
                <i class="status-dot status-dot--amber"></i>
              </div>
            </div>
            <div class="status-row">
              <i class="status-dot status-dot--green"></i>
              <div>
                <strong>素材与肖像授权已纳入审核</strong>
                <span>每次生产前都需要人工确认。</span>
              </div>
            </div>
          </div>

          <div class="safe-note">
            <strong>面向运营人员设计</strong>
            <span>页面只说“要做什么、怎么做”，不展示任何底层模型或供应商信息。</span>
          </div>
        </aside>
      </section>
    </main>
  `;
}

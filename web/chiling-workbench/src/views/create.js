import { escapeHtml } from "../format.js";
import { phonePreview } from "../components/ui.js";

export function render({ state }) {
  return `
    <section class="page-head">
      <div>
        <h1 class="hero-title hero-title--compact">创建作品</h1>
        <p class="lede">上传参考视频和指定肖像，设置生产参数，再交给团队人工确认。</p>
      </div>
      <button class="button" data-route="dashboard">返回生产台</button>
    </section>

    <section class="create-layout">
      <div class="create-card">
        <div class="steps">
          <span class="step-pill is-active">1 导入素材</span>
          <span class="step-pill">2 人工审核</span>
          <span class="step-pill">3 生成交付</span>
        </div>

        <section class="section-block">
          <h2 class="section-title">参考内容</h2>
          <p class="lede">支持粘贴视频链接，也可以先选择本地视频文件。文案、图片和提示说明都可以人工修改。</p>
          <div class="quick-form">
            <div class="input-wrap">
              <input data-field="referenceUrl" placeholder="粘贴参考视频链接" value="${escapeHtml(state.form.referenceUrl)}" />
            </div>
            <button class="button" data-save-form>保存</button>
          </div>
          <div class="upload-grid">
            ${uploadCard("reference", "参考视频", state.form.referenceName, "用于分析结构、节奏、文案和镜头风格。", "is-red", "选择视频")}
            ${uploadCard("portrait", "指定肖像", state.form.portraitName, "用于后续替换为团队授权的脸部肖像。", "is-amber", "选择图片")}
          </div>
        </section>

        <section class="section-block">
          <h2 class="section-title">生产参数</h2>
          <div class="settings-grid">
            <label class="setting">
              <span>单条时长</span>
              <input data-field="duration" type="number" min="1" max="15" value="${state.form.duration}" />
              <small>最长 15 秒，15 秒内可自定义。</small>
            </label>
            <label class="setting">
              <span>生成条数</span>
              <input data-field="count" type="number" min="1" max="5" value="${state.form.count}" />
              <small>单批最多 5 条，默认 1 条。</small>
            </label>
            <label class="setting">
              <span>清晰度</span>
              <select data-field="resolution">
                <option value="480p" ${state.form.resolution === "480p" ? "selected" : ""}>标准 480p</option>
                <option value="720p" ${state.form.resolution === "720p" ? "selected" : ""}>高清 720p</option>
              </select>
              <small>默认标准清晰度，便于快速批量。</small>
            </label>
            <label class="setting">
              <span>字幕呈现</span>
              <select data-field="subtitleStyle">
                <option value="short" ${state.form.subtitleStyle === "short" ? "selected" : ""}>口播短句</option>
                <option value="compact" ${state.form.subtitleStyle === "compact" ? "selected" : ""}>紧凑双行</option>
              </select>
              <small>句尾标点会自动清理。</small>
            </label>
          </div>
        </section>

        <section class="section-block">
          <h2 class="section-title">文案与提示说明</h2>
          <textarea class="review-script" data-field="script" style="min-height: 138px;">${escapeHtml(state.form.script)}</textarea>
          <div class="chip-row">
            <span class="pill pill--blue">可人工修改</span>
            <span class="pill pill--green">图片可替换</span>
            <span class="pill pill--amber">先审后产出</span>
          </div>
        </section>

        <div class="form-actions">
          <button class="button" data-route="dashboard">保存草稿</button>
          <button class="button button--primary" data-to-review>下一步：人工审核</button>
        </div>
      </div>

      <aside class="side-card">
        <span class="pill">实时预览</span>
        <h2 class="section-title" style="margin-top: 24px;">素材会在这里预览。</h2>
        <p class="lede">当前默认展示参考画面，上传图片后会同步更新肖像状态。</p>
        ${phonePreview(state.form.referencePreview, "参考画面", "phone--large")}
        <div class="status-row">
          <i class="status-dot status-dot--green"></i>
          <div>
            <strong>${state.form.duration}s · ${state.form.resolution} · ${state.form.count}条</strong>
            <span>参数已限制在当前版本可生产范围内。</span>
          </div>
        </div>
      </aside>
    </section>

    <input hidden type="file" accept="video/*" data-file-input="reference" />
    <input hidden type="file" accept="image/*" data-file-input="portrait" />
  `;
}

function uploadCard(kind, title, fileName, description, tone, action) {
  return `
    <div class="upload-card ${tone}">
      <i class="upload-icon"></i>
      <div>
        <strong>${title}</strong>
        <p class="muted" style="margin: 6px 0 0; font-size: 13px;">${description}</p>
        <span class="muted" style="display: block; margin-top: 8px; font-size: 12px;">${escapeHtml(fileName)}</span>
      </div>
      <button class="button button--small" data-upload="${kind}">${action}</button>
    </div>
  `;
}

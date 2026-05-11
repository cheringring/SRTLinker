"""SRTLinker - Flask 웹 UI (로컬 경로 기반, 업로드 불필요)."""
from __future__ import annotations
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json
import threading
import webbrowser
import traceback
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from flask import Flask, request, jsonify

from pipeline import process_file, PipelineConfig

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024 * 1024  # 4GB fallback

# ── 전역 상태 ──
jobs: dict[str, dict] = {}

SUPPORTED_EXTS = {".srt", ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv",
                  ".m4v", ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".opus", ".flac"}

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# ── HTML ──
HTML = r"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SRTLinker — 자막 자동 번역기</title>
<style>
  :root { --bg: #1e1f26; --card: #262832; --border: #353846; --accent: #5b6cff;
          --accent2: #7d4ee8; --text: #e6e7ea; --muted: #9ea3b3; --input-bg: #1a1c24; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: var(--bg); color: var(--text); font-family: 'Malgun Gothic','Segoe UI',sans-serif;
         font-size: 10pt; min-height: 100vh; display: flex; justify-content: center; padding: 24px; }
  .container { width: 100%; max-width: 720px; }
  h1 { font-size: 22pt; font-weight: 600; margin-bottom: 2px; }
  .subtitle { color: var(--muted); font-size: 9pt; margin-bottom: 18px; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px;
          padding: 18px 20px; margin-bottom: 14px; }
  .section-title { font-weight: 600; color: #c8cad3; margin-bottom: 10px; }
  label { color: var(--muted); font-size: 9pt; display: block; margin-bottom: 3px; }
  input[type=text], select { width: 100%; background: var(--input-bg); border: 1px solid #3a3d4d;
    border-radius: 6px; padding: 7px 10px; color: var(--text); font-size: 10pt; margin-bottom: 8px; }
  input:focus { outline: none; border-color: var(--accent); }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; }
  .info-row { display: flex; align-items: center; gap: 8px; margin-top: 4px; }

  .path-input-row { display: flex; gap: 8px; margin-bottom: 8px; }
  .path-input-row input { flex: 1; }
  .file-list { max-height: 150px; overflow-y: auto; margin-top: 8px; font-size: 9pt; }
  .file-item { display: flex; justify-content: space-between; align-items: center;
    padding: 5px 8px; border-radius: 4px; }
  .file-item:hover { background: #2a2d3a; }
  .file-item .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .file-item .size { color: var(--muted); font-size: 8pt; margin: 0 8px; }
  .file-item .remove { color: #f55; cursor: pointer; padding: 0 4px; }

  .btn { background: #353846; border: 1px solid #41455a; border-radius: 6px; padding: 8px 16px;
    color: var(--text); cursor: pointer; font-size: 10pt; }
  .btn:hover { background: #3f4356; border-color: var(--accent); }
  .btn-sm { padding: 7px 12px; font-size: 9pt; }
  .btn-primary { background: linear-gradient(90deg, var(--accent), var(--accent2)); border: none;
    color: white; font-weight: 600; padding: 10px 28px; font-size: 11pt; }
  .btn-primary:hover { opacity: .9; }
  .btn-primary:disabled { background: #3a3d4d; color: #6a6e7c; cursor: not-allowed; }
  .btn-row { display: flex; gap: 8px; margin-top: 8px; }

  .progress-wrap { background: var(--input-bg); border: 1px solid #2a2c36; border-radius: 10px;
    height: 24px; overflow: hidden; margin-bottom: 8px; position: relative; }
  .progress-bar { height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent2));
    border-radius: 10px; transition: width .3s; width: 0%; }
  .progress-text { position: absolute; top: 0; left: 0; right: 0; text-align: center;
    line-height: 24px; font-size: 9pt; color: #c8cad3; }
  .status { color: var(--muted); font-size: 9pt; margin-bottom: 6px; }

  .log { background: #14151b; border: 1px solid #2a2c36; border-radius: 8px; padding: 10px;
    font-family: 'Cascadia Code','Consolas',monospace; font-size: 9pt; color: #c8cad3;
    height: 180px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; }

  .action-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  .action-row .status { flex: 1; margin: 0; }

  .drop-zone { background: var(--input-bg); border: 2px dashed #3a3d4d; border-radius: 10px;
    padding: 20px; text-align: center; color: var(--muted); cursor: pointer; transition: .2s; }
  .drop-zone.active { border-color: var(--accent); background: #20243a; }
  .drop-zone p { pointer-events: none; }
</style>
</head>
<body>
<div class="container">
  <h1>SRTLinker</h1>
  <p class="subtitle">비디오/오디오/자막을 자동 번역</p>

  <div class="card">
    <div class="section-title">설정</div>
    <div class="grid2">
      <div><label>번역 언어</label><input type="text" id="lang" value="Korean"></div>
      <div><label>원본 언어 (선택)</label><input type="text" id="srcLang" value="en"></div>
      <div><label>번역 모델</label><input type="text" id="model" value="gpt-4o"></div>
      <div><label>전사 모델</label><input type="text" id="sttModel" value="whisper-1"></div>
    </div>
    <div class="info-row">
      <span style="color:#7ec97e;font-size:0.85rem">✔ 문장 병합 번역 기본 적용</span>
    </div>
  </div>

  <div class="card">
    <div class="section-title">파일</div>
    <div class="drop-zone" id="dropZone">
      <p>여기로 파일을 드래그하세요 (.mp4, .mkv, .srt 등)</p>
    </div>
    <div style="margin-top:10px">
      <label>또는 파일 경로 직접 입력</label>
      <div class="path-input-row">
        <input type="text" id="pathInput" placeholder="C:\Videos\meeting.mp4 또는 output\영상.en.srt">
        <button class="btn btn-sm" onclick="addPath()">추가</button>
      </div>
    </div>
    <div class="file-list" id="fileList"></div>
    <div class="btn-row">
      <button class="btn" onclick="browseFiles()">파일 찾기</button>
      <button class="btn" onclick="clearFiles()">모두 지우기</button>
    </div>
  </div>

  <div class="progress-wrap">
    <div class="progress-bar" id="progressBar"></div>
    <div class="progress-text" id="progressText">대기 중</div>
  </div>
  <div class="action-row">
    <div class="status" id="statusText">대기 중</div>
    <button class="btn" onclick="openOutput()">출력 폴더</button>
    <button class="btn-primary" id="runBtn" onclick="startTranslation()">번역 시작</button>
  </div>

  <div class="section-title" style="margin-top:10px">로그</div>
  <div class="log" id="logView"></div>
</div>

<script>
const EXTS = new Set(SUPPORTED_EXTS_JSON);
let filePaths = [];  // 로컬 경로 문자열 배열

// ── 드래그앤드롭 (파일 업로드 → 서버에 저장 후 경로 반환) ──
const dz = document.getElementById('dropZone');
dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('active'); });
dz.addEventListener('dragleave', () => dz.classList.remove('active'));
dz.addEventListener('drop', async e => {
  e.preventDefault(); dz.classList.remove('active');
  const files = e.dataTransfer.files;
  if (!files.length) return;
  for (const f of files) {
    const ext = '.' + f.name.split('.').pop().toLowerCase();
    if (!EXTS.has(ext)) { appendLog('[무시] 지원 안함: ' + f.name); continue; }
    appendLog('업로드 중: ' + f.name + ' (' + formatSize(f.size) + ')...');
    try {
      const fd = new FormData();
      fd.append('file', f);
      const res = await fetch('/api/upload', { method: 'POST', body: fd });
      const d = await res.json();
      if (d.path) {
        if (!filePaths.includes(d.path)) { filePaths.push(d.path); renderFiles(); }
        appendLog('업로드 완료: ' + d.path);
      } else { appendLog('업로드 실패: ' + (d.error || '알 수 없는 오류')); }
    } catch(err) { appendLog('업로드 실패: ' + err); }
  }
});

// ── 파일 찾기 (브라우저 파일 선택 → 업로드) ──
const browseInput = document.createElement('input');
browseInput.type = 'file';
browseInput.multiple = true;
browseInput.style.display = 'none';
document.body.appendChild(browseInput);

async function browseFiles() {
  browseInput.click();
}
browseInput.addEventListener('change', async () => {
  const files = browseInput.files;
  if (!files.length) return;
  for (const f of files) {
    const ext = '.' + f.name.split('.').pop().toLowerCase();
    if (!EXTS.has(ext)) { appendLog('[무시] 지원 안함: ' + f.name); continue; }
    // 이미 같은 파일명이 등록되어 있으면 건너뛰기
    if (filePaths.some(p => p.endsWith(f.name))) { appendLog('[건너뜀] 이미 등록됨: ' + f.name); continue; }
    appendLog('업로드 중: ' + f.name + ' (' + formatSize(f.size) + ')...');
    try {
      const fd = new FormData();
      fd.append('file', f);
      const res = await fetch('/api/upload', { method: 'POST', body: fd });
      const d = await res.json();
      if (d.path) {
        if (!filePaths.includes(d.path)) { filePaths.push(d.path); renderFiles(); }
        appendLog('준비 완료: ' + f.name);
      } else { appendLog('업로드 실패: ' + (d.error || '알 수 없는 오류')); }
    } catch(err) { appendLog('업로드 실패: ' + err); }
  }
  browseInput.value = '';
});

// ── 경로 직접 입력 ──
function addPath() {
  const input = document.getElementById('pathInput');
  const p = input.value.trim();
  if (!p) return;
  if (!filePaths.includes(p)) { filePaths.push(p); renderFiles(); }
  input.value = '';
}
document.getElementById('pathInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') addPath();
});

function clearFiles() { filePaths = []; renderFiles(); }
function renderFiles() {
  const el = document.getElementById('fileList');
  el.innerHTML = filePaths.map((p, i) => {
    const name = p.split(/[/\\]/).pop();
    return `<div class="file-item"><span class="name" title="${p}">${name}</span><span class="remove" onclick="removeFile(${i})">✕</span></div>`;
  }).join('');
}
function removeFile(i) { filePaths.splice(i, 1); renderFiles(); }
function formatSize(b) {
  if (b < 1024) return b + 'B';
  if (b < 1048576) return (b/1024).toFixed(1) + 'KB';
  if (b < 1073741824) return (b/1048576).toFixed(1) + 'MB';
  return (b/1073741824).toFixed(2) + 'GB';
}

// ── 번역 시작 (경로만 전송, 업로드 없음) ──
async function startTranslation() {
  if (!filePaths.length) { appendLog('파일을 먼저 추가하세요.'); return; }
  const btn = document.getElementById('runBtn');
  btn.disabled = true;
  appendLog('번역 시작...');
  try {
    const res = await fetch('/api/translate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        paths: filePaths,
        lang: document.getElementById('lang').value,
        src_lang: document.getElementById('srcLang').value,
        model: document.getElementById('model').value,
        stt_model: document.getElementById('sttModel').value,
      })
    });
    const data = await res.json();
    if (data.job_id) pollJob(data.job_id);
    else { appendLog('오류: ' + JSON.stringify(data)); btn.disabled = false; }
  } catch(e) { appendLog('요청 실패: ' + e); btn.disabled = false; }
}

async function pollJob(jobId) {
  const iv = setInterval(async () => {
    try {
      const res = await fetch('/api/status/' + jobId);
      const d = await res.json();
      setProgress(d.progress || 0, d.progress_msg || '');
      document.getElementById('statusText').textContent = d.progress_msg || '';
      if (d.new_logs) d.new_logs.forEach(l => appendLog(l));
      if (d.status === 'done' || d.status === 'error') {
        clearInterval(iv);
        document.getElementById('runBtn').disabled = false;
        if (d.errors && d.errors.length) appendLog('⚠ ' + d.errors.length + '개 파일 실패');
        else appendLog('모든 작업 완료.');
      }
    } catch(e) { clearInterval(iv); appendLog('폴링 오류: ' + e);
      document.getElementById('runBtn').disabled = false; }
  }, 1000);
}

function setProgress(p, msg) {
  document.getElementById('progressBar').style.width = (p * 100) + '%';
  document.getElementById('progressText').textContent = Math.round(p * 100) + '%  ' + msg;
}
function appendLog(msg) {
  const el = document.getElementById('logView');
  const ts = new Date().toLocaleTimeString('ko-KR', {hour12:false});
  el.textContent += '[' + ts + '] ' + msg + '\n';
  el.scrollTop = el.scrollHeight;
}
function openOutput() { fetch('/api/open-output'); }
</script>
</body>
</html>
""".replace('SUPPORTED_EXTS_JSON', json.dumps(list(SUPPORTED_EXTS)))


# ── API ──

@app.route('/')
def index():
    return HTML


@app.route('/api/upload', methods=['POST'])
def api_upload():
    """드래그앤드롭/파일찾기 → uploads/ 에 저장 후 경로 반환. 이미 있으면 재사용."""
    f = request.files.get('file')
    if not f:
        return jsonify(error="파일 없음"), 400
    dest = UPLOAD_DIR / f.filename
    if dest.exists():
        return jsonify(path=str(dest.resolve()))
    f.save(str(dest))
    return jsonify(path=str(dest.resolve()))


@app.route('/api/translate', methods=['POST'])
def api_translate():
    """로컬 경로 기반 번역 시작."""
    data = request.get_json()
    if not data or not data.get('paths'):
        return jsonify(error="파일 경로가 없습니다"), 400

    paths = [Path(p) for p in data['paths']]
    # 경로 검증
    for p in paths:
        if not p.exists():
            return jsonify(error=f"파일 없음: {p}"), 400

    lang = data.get('lang', 'Korean')
    src_lang = data.get('src_lang', '') or None
    model = data.get('model', 'gpt-4o')
    stt_model = data.get('stt_model', 'whisper-1')

    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    cfg = PipelineConfig(
        model_translate=model,
        model_transcribe=stt_model,
        target_lang=lang,
        source_lang=src_lang,
        output_dir=output_dir,
        glossary_path=Path("glossary.json") if Path("glossary.json").exists() else None,
    )

    job_id = uuid4().hex[:8]
    jobs[job_id] = {
        'status': 'running',
        'progress': 0.0,
        'progress_msg': '시작 중...',
        'logs': [],
        'log_cursor': 0,
        'errors': [],
    }

    def run():
        job = jobs[job_id]
        errors = []
        total = len(paths)
        for idx, src in enumerate(paths, 1):
            job['logs'].append(f"[{idx}/{total}] {src.name} 처리 시작")

            def prog(msg, p, _i=idx):
                overall = ((_i - 1) + p) / total
                job['progress'] = overall
                job['progress_msg'] = f"({_i}/{total}) {msg}"

            try:
                out = process_file(src, cfg, progress=prog)
                job['logs'].append(f"  → 저장: {out}")
            except Exception as e:
                tb = traceback.format_exc()
                err = f"{src.name}: {type(e).__name__}: {e}"
                errors.append(err)
                job['logs'].append(f"  ✗ 실패: {err}")
                job['logs'].append(tb)

        job['progress'] = 1.0
        job['progress_msg'] = '전체 완료'
        job['errors'] = errors
        job['status'] = 'error' if errors else 'done'

    threading.Thread(target=run, daemon=True).start()
    return jsonify(job_id=job_id)


@app.route('/api/status/<job_id>')
def api_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify(error="없는 작업"), 404
    cursor = job.get('log_cursor', 0)
    new_logs = job['logs'][cursor:]
    job['log_cursor'] = len(job['logs'])
    return jsonify(
        status=job['status'],
        progress=job['progress'],
        progress_msg=job['progress_msg'],
        new_logs=new_logs,
        errors=job['errors'],
    )


@app.route('/api/open-output')
def api_open_output():
    out = Path("output").resolve()
    out.mkdir(exist_ok=True)
    if sys.platform == 'win32':
        os.startfile(str(out))
    return jsonify(ok=True)


def main():
    port = 8456
    print(f"SRTLinker 웹 서버 시작: http://localhost:{port}")
    webbrowser.open(f"http://localhost:{port}")
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()

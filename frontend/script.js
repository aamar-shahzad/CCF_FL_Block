/** CCFL experiment UI — run full federated learning on CCF from the browser. */

class CCFLApp {
    constructor() {
        this.apiBase = '';
        this._configs = [];
        this._resultsRuns = [];
        this._selectedRunId = null;
        this._compareSelected = new Set();
        this._experimentPoll = null;
        this.ledgerActivityTimer = null;
        this._chartColors = ['#667eea', '#e65100', '#2e7d32', '#7b1fa2'];
        this.init();
    }

    init() {
        this.setupTabs();
        document.getElementById('run-experiment-btn').addEventListener('click', () => this.runExperiment());
        document.getElementById('stop-experiment-btn').addEventListener('click', () => this.stopExperiment());
        document.getElementById('refresh-exp-status-btn').addEventListener('click', () => this.refreshExperimentStatus());
        document.getElementById('refresh-system-btn').addEventListener('click', () => this.refreshSystemStatus());
        document.getElementById('clean-sandbox-btn').addEventListener('click', () => this.cleanSandbox());
        document.getElementById('refresh-results-btn').addEventListener('click', () => this.loadResults());
        document.getElementById('results-detail-close').addEventListener('click', () => this.closeResultDetail());
        document.getElementById('results-filter-dataset').addEventListener('change', () => this.renderResultsTable());
        document.getElementById('results-filter-method').addEventListener('change', () => this.renderResultsTable());
        document.getElementById('results-sort').addEventListener('change', () => this.renderResultsTable());
        document.getElementById('results-compare-btn').addEventListener('click', () => this.compareSelectedRuns());
        document.getElementById('results-compare-clear-btn').addEventListener('click', () => this.clearCompareSelection());

        const useExisting = document.getElementById('expUseExistingModel');
        const modelIdGroup = document.getElementById('expModelIdGroup');
        useExisting.addEventListener('change', () => {
            modelIdGroup.style.display = useExisting.checked ? '' : 'none';
        });

        document.getElementById('expConfig').addEventListener('change', () => this.showConfigDetails());
        document.getElementById('expPlatform').addEventListener('change', () => this.showConfigDetails());

        this.setupLedger();
        this.loadExperimentConfigs();
        this.refreshSystemStatus();
        this.loadResults();
    }

    setupTabs() {
        const buttons = document.querySelectorAll('.tab-btn');
        const panels = document.querySelectorAll('.tab-content');
        buttons.forEach((btn) => {
            btn.addEventListener('click', () => {
                const tab = btn.getAttribute('data-tab');
                buttons.forEach((b) => b.classList.remove('active'));
                panels.forEach((p) => p.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById(tab).classList.add('active');
                if (tab === 'results') this.loadResults();
                if (tab === 'ledger') this.onLedgerTabOpen();
                else this.stopLedgerActivityPolling();
            });
        });
    }

    setupLedger() {
        const ids = [
            ['ledger-discover-btn', () => this.ledgerDiscoverModels()],
            ['ledger-metadata-btn', () => this.ledgerFetchMetadata()],
            ['ledger-weights-btn', () => this.ledgerFetchWeights()],
            ['ledger-stats-btn', () => this.ledgerFetchStats()],
            ['ledger-tx-btn', () => this.ledgerFetchTx()],
            ['ledger-commit-btn', () => this.ledgerFetchCommit()],
            ['ledger-receipt-btn', () => this.ledgerFetchReceipt()],
            ['ledger-openapi-btn', () => this.ledgerFetchOpenapi(false)],
            ['ledger-openapi-full-btn', () => this.ledgerFetchOpenapi(true)],
            ['ledger-aggregate-btn', () => this.ledgerTriggerAggregate()],
            ['ledger-user-add-btn', () => this.ledgerUserAdd()],
            ['ledger-register-model-btn', () => this.ledgerRegisterModel()],
            ['ledger-upload-weights-btn', () => this.ledgerUploadWeights()],
            ['ledger-register-client-btn', () => this.ledgerRegisterClient()],
        ];
        ids.forEach(([id, fn]) => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('click', fn);
        });
        const modelSel = document.getElementById('ledger-model-id');
        const userSel = document.getElementById('ledger-user-id');
        if (modelSel) modelSel.addEventListener('change', () => this.updateLedgerDownloadLink());
        if (userSel) userSel.addEventListener('change', () => this.updateLedgerDownloadLink());
        const wrap = document.getElementById('ledger-endpoints-table');
        if (wrap) {
            wrap.addEventListener('click', (e) => {
                const btn = e.target.closest('[data-ledger-action]');
                if (btn) this.ledgerRunCatalogAction(btn.dataset.ledgerAction);
            });
        }
        const actRefresh = document.getElementById('ledger-activity-refresh-btn');
        if (actRefresh) actRefresh.addEventListener('click', () => this.refreshLedgerActivity());
        this.loadLedgerEndpoints();
    }

    stopLedgerActivityPolling() {
        if (this.ledgerActivityTimer) {
            clearInterval(this.ledgerActivityTimer);
            this.ledgerActivityTimer = null;
        }
    }

    startLedgerActivityPolling() {
        this.stopLedgerActivityPolling();
        const auto = document.getElementById('ledger-activity-auto');
        if (auto && !auto.checked) return;
        this.refreshLedgerActivity();
        this.ledgerActivityTimer = setInterval(() => this.refreshLedgerActivity(), 3000);
    }

    formatActivityTime(ts) {
        if (!ts) return '';
        const d = new Date(ts * 1000);
        return d.toLocaleTimeString();
    }

    statusBadgeClass(status) {
        const s = (status || '').toLowerCase();
        if (s === 'committed') return 'activity-badge activity-badge-ok';
        if (s === 'pending') return 'activity-badge activity-badge-pending';
        if (s === 'invalid' || s === 'error') return 'activity-badge activity-badge-error';
        return 'activity-badge activity-badge-muted';
    }

    renderLedgerActivity(data) {
        const statsEl = document.getElementById('ledger-activity-stats');
        const feedEl = document.getElementById('ledger-activity-feed');
        if (!statsEl || !feedEl) return;

        if (!data.ok && data.commit_error) {
            statsEl.innerHTML = `<span class="activity-badge activity-badge-error">CCF unreachable</span>`;
            feedEl.innerHTML = `<p class="text-muted">${this.esc(data.commit_error)}</p>`;
            return;
        }

        const commitId = data.commit?.transaction_id || '—';
        const st = data.stats || {};
        statsEl.innerHTML = `
            <span class="activity-stat"><strong>Latest commit</strong> <code>${this.esc(commitId)}</code></span>
            <span class="activity-stat">${st.tx_scanned || 0} txs scanned</span>
            <span class="activity-stat">${st.committed || 0} committed</span>
            <span class="activity-stat">${st.pending || 0} pending</span>
            <span class="activity-stat">${st.event_count || 0} events</span>
        `;

        let html = '';

        const txs = data.transactions || [];
        if (txs.length) {
            html += `<div class="activity-block"><h4>Ledger transactions</h4><ul class="activity-list">`;
            txs.forEach((tx) => {
                html += `<li class="activity-item">
                    <button type="button" class="activity-tx-link" data-tx="${this.esc(tx.transaction_id)}">${this.esc(tx.transaction_id)}</button>
                    <span class="${this.statusBadgeClass(tx.status)}">${this.esc(tx.status)}</span>
                </li>`;
            });
            html += '</ul></div>';
        }

        const events = data.events || [];
        if (events.length) {
            html += `<div class="activity-block"><h4>Events (UI + ledger + experiment)</h4><ul class="activity-list">`;
            events.forEach((ev) => {
                const src = ev.source || '?';
                const action = ev.action || '';
                const detail = ev.detail ? ` — ${ev.detail}` : '';
                const tx = ev.tx_id ? ` <code>${this.esc(ev.tx_id)}</code>` : '';
                const st = ev.status ? ` <span class="${this.statusBadgeClass(ev.status)}">${this.esc(ev.status)}</span>` : '';
                const okMark = ev.ok === false ? ' activity-item-fail' : '';
                html += `<li class="activity-item${okMark}">
                    <span class="activity-time">${this.formatActivityTime(ev.ts)}</span>
                    <span class="activity-src activity-src-${this.esc(src)}">${this.esc(src)}</span>
                    <span class="activity-action">${this.esc(action)}${tx}${st}</span>
                    <span class="activity-detail">${this.esc(detail)}</span>
                </li>`;
            });
            html += '</ul></div>';
        }

        const exp = data.experiment_lines || [];
        if (exp.length) {
            html += `<div class="activity-block"><h4>Experiment log (CCF)</h4><ul class="activity-list activity-list-log">`;
            exp.slice().reverse().forEach((line) => {
                html += `<li class="activity-item activity-log-line">${this.esc(line)}</li>`;
            });
            html += '</ul></div>';
        }

        if (!html) {
            html = '<p class="text-muted">No CCF activity yet. Run an experiment or use the API forms below.</p>';
        }

        feedEl.innerHTML = html;
        feedEl.querySelectorAll('.activity-tx-link').forEach((btn) => {
            btn.addEventListener('click', () => {
                const txInput = document.getElementById('ledger-tx-id');
                if (txInput) txInput.value = btn.dataset.tx || '';
            });
        });
    }

    async refreshLedgerActivity() {
        try {
            const { data } = await this.fetchJson(
                `/api/ledger/activity?${this.ledgerUserQuery()}&limit=28`
            );
            this.renderLedgerActivity(data);
        } catch (e) {
            const feedEl = document.getElementById('ledger-activity-feed');
            if (feedEl) feedEl.innerHTML = `<p class="text-muted">${this.esc(e.message)}</p>`;
        }
    }

    async onLedgerTabOpen() {
        this.updateLedgerDownloadLink();
        try {
            const { data } = await this.fetchJson('/api/health');
            if (!data.ledger_api) {
                this.showLedgerMessage(
                    'Ledger API not available on this server — restart proxy_server.py (see System tab).',
                    'error'
                );
                return;
            }
        } catch (e) {
            this.showLedgerMessage(e.message, 'error');
            return;
        }
        this.ledgerDiscoverModels(true);
        this.startLedgerActivityPolling();
    }

    ledgerModelId() {
        return parseInt(document.getElementById('ledger-model-id').value, 10) || 0;
    }

    ledgerRoundNo() {
        return parseInt(document.getElementById('ledger-round-no').value, 10) || 0;
    }

    ledgerUserId() {
        return parseInt(document.getElementById('ledger-user-id')?.value, 10) || 0;
    }

    ledgerUserQuery() {
        return `user_id=${this.ledgerUserId()}`;
    }

    updateLedgerDownloadLink() {
        const mid = this.ledgerModelId();
        const a = document.getElementById('ledger-weights-download');
        if (a) {
            a.href = `${this.apiBase}/api/ledger/models/${mid}/weights/download?${this.ledgerUserQuery()}`;
        }
    }

    parseLedgerJson(textareaId, fallback = null) {
        const el = document.getElementById(textareaId);
        if (!el) return fallback;
        try {
            return JSON.parse(el.value.trim());
        } catch (e) {
            throw new Error(`Invalid JSON in ${textareaId}: ${e.message}`);
        }
    }

    showLedgerMessage(text, type = 'info') {
        this.showMessage('ledger-message', text, type);
    }

    setLedgerResponse(data, targetId = 'ledger-response') {
        document.getElementById(targetId).textContent =
            typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    }

    populateLedgerModelSelect(ids) {
        const sel = document.getElementById('ledger-model-id');
        if (!sel || !ids.length) return;
        const cur = sel.value;
        sel.innerHTML = ids.map((id) => `<option value="${id}">${id}</option>`).join('');
        if (ids.includes(Number(cur))) sel.value = cur;
        else sel.value = String(ids[ids.length - 1]);
        this.updateLedgerDownloadLink();
    }

    async ledgerDiscoverModels(quiet = false) {
        if (!quiet) this.showLedgerMessage('Scanning ledger for models…', 'info');
        try {
            const { res, data } = await this.fetchJson('/api/ledger/models');
            const ids = data.model_ids || [];
            if (ids.length) {
                this.populateLedgerModelSelect(ids);
                if (!quiet) this.showLedgerMessage(`Found ${ids.length} model(s): ${ids.join(', ')}`, 'success');
            } else if (!quiet) {
                this.showLedgerMessage('No models found on ledger (run an experiment first).', 'error');
            }
        } catch (e) {
            if (!quiet) this.showLedgerMessage(e.message, 'error');
        }
    }

    async ledgerFetchMetadata() {
        const mid = this.ledgerModelId();
        this.showLedgerMessage('', 'info');
        try {
            const { res, data } = await this.fetchJson(
                `/api/ledger/models/${mid}/metadata?${this.ledgerUserQuery()}`
            );
            this.setLedgerResponse(data);
            if (data.ok) {
                this.showLedgerMessage(`Model ${mid}: ${data.dataset || '?'} · ${data.architecture || 'metadata loaded'}`, 'success');
            } else {
                this.showLedgerMessage(data.error || 'Not found', 'error');
            }
        } catch (e) {
            this.showLedgerMessage(e.message, 'error');
        }
    }

    async ledgerFetchWeights() {
        const mid = this.ledgerModelId();
        try {
            const { res, data } = await this.fetchJson(
                `/api/ledger/models/${mid}/weights?${this.ledgerUserQuery()}`
            );
            this.setLedgerResponse(data);
            if (data.ok) {
                const s = data.summary || {};
                this.showLedgerMessage(
                    `Global weights: ${s.format} · dim=${s.dim}${s.preview ? ` · preview first ${s.preview.length} values` : ''}`,
                    'success'
                );
            } else {
                this.showLedgerMessage(data.error || 'No weights yet', 'error');
            }
        } catch (e) {
            this.showLedgerMessage(e.message, 'error');
        }
    }

    async ledgerFetchStats() {
        const mid = this.ledgerModelId();
        const round = this.ledgerRoundNo();
        try {
            const { res, data } = await this.fetchJson(
                `/api/ledger/models/${mid}/stats?round_no=${round}&${this.ledgerUserQuery()}`
            );
            this.setLedgerResponse(data);
            if (data.ok) {
                this.showLedgerMessage(`Round ${round} aggregation stats loaded.`, 'success');
            } else {
                this.showLedgerMessage(data.error || 'Stats not found', 'error');
            }
        } catch (e) {
            this.showLedgerMessage(e.message, 'error');
        }
    }

    async ledgerFetchTx() {
        const txId = document.getElementById('ledger-tx-id').value.trim();
        if (!txId) {
            this.showLedgerMessage('Enter a transaction ID (view.sequence).', 'error');
            return;
        }
        try {
            const { res, data } = await this.fetchJson(
                `/api/ledger/tx?transaction_id=${encodeURIComponent(txId)}&${this.ledgerUserQuery()}`
            );
            this.setLedgerResponse(data);
            if (data.ok) {
                const st = data.status?.status || data.raw?.status || '?';
                this.showLedgerMessage(`Transaction ${txId}: ${st}`, 'success');
            } else {
                this.showLedgerMessage(data.error || 'Query failed', 'error');
            }
        } catch (e) {
            this.showLedgerMessage(e.message, 'error');
        }
    }

    async ledgerFetchCommit() {
        try {
            const { res, data } = await this.fetchJson(`/api/ledger/commit?${this.ledgerUserQuery()}`);
            this.setLedgerResponse(data);
            if (data.ok) this.showLedgerMessage('Commit level retrieved.', 'success');
            else this.showLedgerMessage(data.error || 'Failed', 'error');
        } catch (e) {
            this.showLedgerMessage(e.message, 'error');
        }
    }

    async ledgerFetchOpenapi(full = false) {
        try {
            const q = full ? 'full=1' : 'full=0';
            const { res, data } = await this.fetchJson(
                `/api/ledger/openapi?${q}&${this.ledgerUserQuery()}`
            );
            this.setLedgerResponse(data);
            if (data.ok) {
                const msg = full
                    ? 'Full OpenAPI schema loaded.'
                    : `${data.path_count} paths in OpenAPI schema.`;
                this.showLedgerMessage(msg, 'success');
            } else {
                this.showLedgerMessage(data.error || 'Failed', 'error');
            }
        } catch (e) {
            this.showLedgerMessage(e.message, 'error');
        }
    }

    async ledgerFetchReceipt() {
        const txId = document.getElementById('ledger-tx-id').value.trim();
        if (!txId) {
            this.showLedgerMessage('Enter a transaction ID for the receipt.', 'error');
            return;
        }
        try {
            const { res, data } = await this.fetchJson(
                `/api/ledger/receipt?transaction_id=${encodeURIComponent(txId)}&${this.ledgerUserQuery()}`
            );
            this.setLedgerResponse(data);
            if (data.ok) {
                if (data.pending) {
                    this.showLedgerMessage(data.message || 'Receipt pending — retry shortly.', 'info');
                } else {
                    this.showLedgerMessage(`Receipt for ${txId} loaded.`, 'success');
                }
            } else {
                this.showLedgerMessage(data.error || 'Receipt query failed', 'error');
            }
        } catch (e) {
            this.showLedgerMessage(e.message, 'error');
        }
    }

    async ledgerUserAdd() {
        const msg = document.getElementById('ledger-user-msg').value.trim();
        if (!msg) {
            this.showLedgerMessage('Enter a message for /user/add.', 'error');
            return;
        }
        try {
            const { res, data } = await this.fetchJson('/api/ledger/user/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ msg }),
            });
            this.setLedgerResponse(data);
            if (data.ok) this.showLedgerMessage('User message stored on ledger.', 'success');
            else this.showLedgerMessage(data.error || 'Failed', 'error');
        } catch (e) {
            this.showLedgerMessage(e.message, 'error');
        }
    }

    async ledgerRegisterModel() {
        const model_name = document.getElementById('ledger-model-name').value.trim() || 'mnist';
        let model_data;
        try {
            model_data = this.parseLedgerJson('ledger-model-data');
        } catch (e) {
            this.showLedgerMessage(e.message, 'error');
            return;
        }
        if (!window.confirm(`Register new global model "${model_name}" on CCF?`)) return;
        try {
            const { res, data } = await this.fetchJson('/api/ledger/model/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_name, model_data }),
            });
            this.setLedgerResponse(data);
            if (data.ok) {
                const id = data.model_id ?? data.raw?.model_id;
                this.showLedgerMessage(
                    id != null ? `Model registered — model_id=${id}` : 'Model registered.',
                    'success'
                );
                if (id != null) this.populateLedgerModelSelect([Number(id)]);
                this.ledgerDiscoverModels(true);
            } else {
                this.showLedgerMessage(data.error || 'Registration failed', 'error');
            }
        } catch (e) {
            this.showLedgerMessage(e.message, 'error');
        }
    }

    async ledgerUploadWeights() {
        const mid = this.ledgerModelId();
        const round = this.ledgerRoundNo();
        const client_id = document.getElementById('ledger-client-id').value.trim();
        let weights_json;
        try {
            weights_json = this.parseLedgerJson('ledger-weights-json');
        } catch (e) {
            this.showLedgerMessage(e.message, 'error');
            return;
        }
        if (!Array.isArray(weights_json)) {
            this.showLedgerMessage('weights_json must be a JSON array.', 'error');
            return;
        }
        try {
            const { res, data } = await this.fetchJson('/api/ledger/weights/upload', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model_id: mid,
                    round_no: round,
                    weights_json,
                    client_id,
                    user_id: this.ledgerUserId(),
                }),
            });
            this.setLedgerResponse(data);
            if (data.ok) {
                this.showLedgerMessage(
                    `Uploaded ${weights_json.length} weights for model ${mid} round ${round}.`,
                    'success'
                );
            } else {
                this.showLedgerMessage(data.error || 'Upload failed', 'error');
            }
        } catch (e) {
            this.showLedgerMessage(e.message, 'error');
        }
    }

    async ledgerRegisterClient() {
        const client_id = document.getElementById('ledger-register-client-id').value.trim();
        if (!client_id) {
            this.showLedgerMessage('Enter client_id to register.', 'error');
            return;
        }
        try {
            const { res, data } = await this.fetchJson('/api/ledger/client/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ client_id, cert_fingerprint: client_id }),
            });
            this.setLedgerResponse(data);
            if (data.ok) this.showLedgerMessage(`Client ${client_id} registered.`, 'success');
            else this.showLedgerMessage(data.error || 'Registration failed', 'error');
        } catch (e) {
            this.showLedgerMessage(e.message, 'error');
        }
    }

    async ledgerTriggerAggregate() {
        const mid = this.ledgerModelId();
        const round = this.ledgerRoundNo();
        const method = document.getElementById('ledger-agg-method').value;
        const k_sigma = parseFloat(document.getElementById('ledger-k-sigma').value) || 2.5;
        const use_adaptive = document.getElementById('ledger-use-adaptive').checked;
        const partitioned = document.getElementById('ledger-partitioned').checked;
        if (!window.confirm(`Run ${method} aggregation for model ${mid} round ${round}?`)) return;
        try {
            const { res, data } = await this.fetchJson('/api/ledger/aggregate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model_id: mid,
                    round_no: round,
                    method,
                    k_sigma,
                    use_adaptive,
                    partitioned,
                }),
            });
            this.setLedgerResponse(data);
            if (data.ok) this.showLedgerMessage('Aggregation completed on CCF.', 'success');
            else this.showLedgerMessage(data.error || 'Aggregation failed', 'error');
        } catch (e) {
            this.showLedgerMessage(e.message, 'error');
        }
    }

    ledgerRunCatalogAction(path) {
        const actions = {
            '/user/add': () => this.ledgerUserAdd(),
            '/model/intial_model': () => this.ledgerRegisterModel(),
            '/model/upload/local_model_weights': () => this.ledgerUploadWeights(),
            '/model/register_client': () => this.ledgerRegisterClient(),
            '/model/aggregate_weights_local': () => this.ledgerTriggerAggregate(),
            '/model/download/global': () => this.ledgerFetchMetadata(),
            '/model/download_gloabl_weights': () => this.ledgerFetchWeights(),
            '/model/aggregate_stats': () => this.ledgerFetchStats(),
            '/api': () => this.ledgerFetchOpenapi(false),
            '/tx': () => this.ledgerFetchTx(),
            '/commit': () => this.ledgerFetchCommit(),
            '/receipt': () => this.ledgerFetchReceipt(),
        };
        const fn = actions[path];
        if (fn) fn();
        else this.showLedgerMessage(`No UI action for ${path}`, 'error');
    }

    async loadLedgerEndpoints() {
        const wrap = document.getElementById('ledger-endpoints-table');
        if (!wrap) return;
        try {
            const { res, data } = await this.fetchJson('/api/ledger/endpoints');
            const eps = data.endpoints || [];
            let html = `<table class="results-table ledger-api-table"><thead><tr>
                <th>Group</th><th>Method</th><th>Path</th><th>Auth</th><th>Description</th><th></th>
            </tr></thead><tbody>`;
            eps.forEach((e) => {
                html += `<tr>
                    <td>${this.esc(e.group)}</td>
                    <td><code>${this.esc(e.method)}</code></td>
                    <td><code>/app${this.esc(e.path)}</code></td>
                    <td>${this.esc(e.auth)}</td>
                    <td>${this.esc(e.description)}</td>
                    <td><button type="button" class="btn btn-secondary btn-sm" data-ledger-action="${this.esc(e.path)}">Run</button></td>
                </tr>`;
            });
            html += '</tbody></table>';
            wrap.innerHTML = html;
        } catch {
            wrap.innerHTML = '<p class="text-muted">Could not load API catalog.</p>';
        }
    }

    showMessage(id, text, type = 'info') {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = text;
        el.className = `message ${type}`;
        el.style.display = text ? 'block' : 'none';
    }

    setLoading(show) {
        document.getElementById('experiment-loading').style.display = show ? 'flex' : 'none';
    }

    async loadExperimentConfigs() {
        const select = document.getElementById('expConfig');
        try {
            const { res, data } = await this.fetchJson('/api/configs');
            this._configs = data.configs || [];
            select.innerHTML = '';
            this._configs.forEach((c, i) => {
                const opt = document.createElement('option');
                opt.value = c.path;
                const tag = c.method === 'ccfl' ? 'CCFL' : (c.method || '').toUpperCase();
                opt.textContent = `${c.id} — ${tag} · ${c.dataset || '?'} · ${c.num_clients || '?'} clients`;
                if (c.id === 'mnist_5clients_ccfl.yaml' || i === 0) opt.selected = true;
                select.appendChild(opt);
            });
            this.showConfigDetails();
        } catch {
            select.innerHTML =
                '<option value="experiments/config/mnist_5clients_ccfl.yaml">mnist_5clients_ccfl.yaml</option>';
        }
    }

    showConfigDetails() {
        const path = document.getElementById('expConfig').value;
        const cfg = this._configs.find((c) => c.path === path);
        const box = document.getElementById('expConfigDetails');
        const platform = document.getElementById('expPlatform').value;
        if (!cfg) {
            box.innerHTML = '';
            return;
        }

        const attackOn = cfg.has_attack;
        const attackPill = attackOn
            ? `<span class="pill pill-warning">${this.esc(cfg.attack)} · ${Math.round((cfg.malicious_frac || 0) * 100)}% malicious</span>`
            : '<span class="pill pill-success">No attack</span>';

        const methodLabel = cfg.method === 'ccfl'
            ? 'CCFL (client registration + AHDA)'
            : this.esc(cfg.method);

        const ahdaExtra = cfg.ccf_method === 'ahda'
            ? `kσ=${cfg.k_sigma ?? 2.5}, adaptive=${cfg.use_adaptive !== false ? 'on' : 'off'}${cfg.partitioned ? ', partitioned' : ''}`
            : '';

        const modelBits = [cfg.model_init || 'paper'];
        if (cfg.keras_application) modelBits.push(cfg.keras_application);
        if (cfg.keras_weights) modelBits.push(`weights=${cfg.keras_weights}`);

        const rows = [
            ['Training', cfg.training_backend || cfg.fl_backend || 'auto'],
            ['Data', `${cfg.dataset} · ${cfg.distribution || 'iid'}${cfg.alpha != null ? ` (α=${cfg.alpha})` : ''}`],
            ['FL clients', `${cfg.num_clients} clients · ${cfg.local_epochs ?? '?'} local epochs · ${cfg.rounds} rounds`],
            ['CCF aggregation', `${cfg.ccf_method || cfg.method}${ahdaExtra ? ` (${ahdaExtra})` : ''}`],
            ['Experiment method', methodLabel],
            ['Weight storage', cfg.weight_storage || (cfg.offchain ? 'off-chain' : 'on-chain')],
            ['Client registry', cfg.register_clients ? 'Yes (member registers clients)' : 'No'],
            ['Attack', attackOn
                ? `${cfg.attack}${cfg.attack_strength != null ? ` (strength ${cfg.attack_strength})` : ''} — ${Math.round((cfg.malicious_frac || 0) * 100)}% of clients`
                : 'None'],
            ['Model init', modelBits.join(' · ')],
            ['CCF platform', `${platform} (live node + mTLS certs)`],
        ];
        if (cfg.is_he) {
            rows.push(['HE baseline', 'Paillier ciphertext aggregation in enclave']);
        }
        if (cfg.method === 'dp_fedavg' && cfg.dp_sigma != null) {
            rows.push(['Differential privacy', `Gaussian noise σ=${cfg.dp_sigma} (client-side, before upload)`]);
        }
        if (cfg.sandbox_users) {
            rows.push(['CCF user certs', `Needs SANDBOX_USERS≥${cfg.sandbox_users} (config sandbox_users)`]);
        }

        box.innerHTML = `
            <div class="run-summary-header">
                <h3>What this run uses</h3>
                ${attackPill}
            </div>
            <p class="run-summary-lead text-muted">Real local training on your machine → weight upload to CCF → aggregation in the enclave → global model download. Not simulated metrics.</p>
            <dl class="run-summary-grid">
                ${rows.map(([k, v]) => `
                    <dt>${this.esc(k)}</dt>
                    <dd>${this.esc(v)}</dd>
                `).join('')}
            </dl>
        `;
    }

    async runExperiment() {
        const config = document.getElementById('expConfig').value;
        const platform = document.getElementById('expPlatform').value;
        const startRound = parseInt(document.getElementById('expStartRound').value, 10) || 0;
        const body = { config, platform, start_round: startRound };

        if (document.getElementById('expUseExistingModel').checked) {
            const modelId = parseInt(document.getElementById('expModelId').value, 10);
            if (Number.isNaN(modelId) || modelId < 0) {
                this.showMessage('experiments-message', 'Enter a valid model ID.', 'error');
                return;
            }
            body.model_id = modelId;
        }

        this.setLoading(true);
        this.showMessage('experiments-message', '', 'info');
        try {
            const { res, data } = await this.fetchJson('/api/experiment/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!res.ok || !data.ok) throw new Error(data.error || 'Failed to start');
            this.showMessage('experiments-message', `Started (pid ${data.pid}). Downloading data & training…`, 'success');
            this.startPolling();
            await this.refreshExperimentStatus();
        } catch (e) {
            this.showMessage('experiments-message', e.message, 'error');
        } finally {
            this.setLoading(false);
        }
    }

    async stopExperiment() {
        await fetch(`${this.apiBase}/api/experiment/stop`, { method: 'POST' });
        this.showMessage('experiments-message', 'Stop requested.', 'info');
        await this.refreshExperimentStatus();
    }

    startPolling() {
        if (this._experimentPoll) clearInterval(this._experimentPoll);
        this._experimentPoll = setInterval(() => this.refreshExperimentStatus(), 3000);
    }

    renderExperimentProgress(data) {
        const panel = document.getElementById('experiment-progress');
        const p = data.progress || {};
        const show = data.running || (p.live_rounds && p.live_rounds.length);
        panel.hidden = !show;
        if (!show) return;

        const total = p.rounds_total;
        const done = p.rounds_done || 0;
        const pct = total ? Math.min(100, Math.round((done / total) * 100)) : 0;
        document.getElementById('experiment-progress-fill').style.width = `${pct}%`;

        const cfg = p.config_label ? String(p.config_label).split('/').pop() : 'experiment';
        let meta = cfg;
        if (p.model_id != null) {
            meta += ` · model ${p.model_id}`;
            const sel = document.getElementById('ledger-model-id');
            if (sel && !sel.querySelector(`option[value="${p.model_id}"]`)) {
                const opt = document.createElement('option');
                opt.value = String(p.model_id);
                opt.textContent = String(p.model_id);
                sel.appendChild(opt);
            }
            if (sel) {
                sel.value = String(p.model_id);
                this.updateLedgerDownloadLink();
            }
        }
        if (p.run_id) meta += ` · ${p.run_id}`;
        document.getElementById('experiment-progress-meta').textContent = meta;

        const stats = document.getElementById('experiment-progress-stats');
        stats.innerHTML = `
            <div class="stat-card"><span class="stat-label">Round</span><span class="stat-value">${total ? `${done} / ${total}` : (p.latest_round ?? '—')}</span></div>
            <div class="stat-card"><span class="stat-label">Latest accuracy</span><span class="stat-value">${this.fmtAcc(p.latest_accuracy)}</span></div>
            <div class="stat-card"><span class="stat-label">Status</span><span class="stat-value">${data.running ? 'Running' : 'Finished'}</span></div>
        `;

        const chartEl = document.getElementById('experiment-live-chart');
        if (p.live_rounds && p.live_rounds.length) {
            chartEl.innerHTML = this.renderAccuracyChart(p.live_rounds);
        } else {
            chartEl.innerHTML = '<p class="text-muted">Waiting for first round…</p>';
        }
    }

    async refreshExperimentStatus() {
        try {
            const { res, data } = await this.fetchJson('/api/experiment/status');
            document.getElementById('experiment-status-content').textContent = JSON.stringify(
                { running: data.running, exit_code: data.exit_code, meta: data.meta, progress: data.progress },
                null,
                2
            );
            document.getElementById('experiment-log-content').textContent =
                (data.log_tail || []).join('\n') || '—';
            this.renderExperimentProgress(data);

            if (!data.running && this._experimentPoll) {
                clearInterval(this._experimentPoll);
                this._experimentPoll = null;
                if (data.exit_code === 0) {
                    this.showMessage('experiments-message', 'Experiment completed.', 'success');
                    this.loadResults();
                } else if (data.exit_code != null) {
                    this.showMessage('experiments-message', `Failed (exit ${data.exit_code}). See log.`, 'error');
                }
            }
        } catch (e) {
            document.getElementById('experiment-status-content').textContent = e.message;
        }
    }

    esc(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    fmtAcc(v) {
        return v != null ? `${(v * 100).toFixed(2)}%` : '—';
    }

    fmtTime(ms) {
        return ms != null ? `${(ms / 1000).toFixed(1)}s` : '—';
    }

    fmtDate(ts) {
        if (!ts) return '—';
        return new Date(ts * 1000).toLocaleString();
    }

    /** Parse JSON responses; surface clear errors when HTML (404 page) is returned. */
    async fetchJson(url, options = {}) {
        const res = await fetch(`${this.apiBase}${url}`, options);
        const text = await res.text();
        try {
            const data = text ? JSON.parse(text) : {};
            return { res, data };
        } catch {
            const restart =
                ' Restart the UI server: cd frontend && PROXY_PORT=8080 ../.venv/bin/python3 proxy_server.py';
            if (text.trimStart().toLowerCase().startsWith('<!doctype') || text.trimStart().startsWith('<html')) {
                throw new Error(
                    `API ${url} returned HTML (status ${res.status}), not JSON.${restart}`
                );
            }
            throw new Error(`Invalid JSON from ${url} (${res.status}): ${text.slice(0, 120)}`);
        }
    }

    statusBadge(r) {
        if (r.status === 'complete' && r.rounds_completed === r.rounds_planned) {
            return '<span class="pill pill-success">Complete</span>';
        }
        if (r.rounds_completed > 0) {
            return '<span class="pill pill-warning">Partial</span>';
        }
        return '<span class="pill pill-muted">No metrics</span>';
    }

    methodBadge(method) {
        const m = (method || '').toLowerCase();
        const cls = m === 'ccfl' ? 'pill-ccfl' : 'pill-method';
        return `<span class="pill ${cls}">${this.esc(method || '—')}</span>`;
    }

    async loadResults() {
        const wrap = document.getElementById('results-table-wrap');
        const summary = document.getElementById('results-summary');
        wrap.innerHTML = '<p class="text-muted results-loading">Loading results…</p>';
        summary.innerHTML = '';
        try {
            const { res, data } = await this.fetchJson('/api/results');
            this._resultsRuns = data.runs || [];
            this.populateResultsFilters();
            this.renderResultsSummary();
            this.renderResultsTable();
        } catch (e) {
            wrap.innerHTML = `<p class="message error">${this.esc(e.message)}</p>`;
        }
    }

    populateResultsFilters() {
        const datasets = [...new Set(this._resultsRuns.map((r) => r.dataset).filter(Boolean))].sort();
        const methods = [...new Set(this._resultsRuns.map((r) => r.method).filter(Boolean))].sort();
        const dsSel = document.getElementById('results-filter-dataset');
        const mSel = document.getElementById('results-filter-method');
        const dsVal = dsSel.value;
        const mVal = mSel.value;
        dsSel.innerHTML = '<option value="">All datasets</option>';
        datasets.forEach((d) => {
            dsSel.innerHTML += `<option value="${this.esc(d)}">${this.esc(d)}</option>`;
        });
        mSel.innerHTML = '<option value="">All methods</option>';
        methods.forEach((m) => {
            mSel.innerHTML += `<option value="${this.esc(m)}">${this.esc(m)}</option>`;
        });
        dsSel.value = dsVal;
        mSel.value = mVal;
    }

    getFilteredRuns() {
        const ds = document.getElementById('results-filter-dataset').value;
        const method = document.getElementById('results-filter-method').value;
        const sort = document.getElementById('results-sort').value;
        let runs = this._resultsRuns.filter((r) => {
            if (ds && r.dataset !== ds) return false;
            if (method && r.method !== method) return false;
            return true;
        });
        if (sort === 'accuracy') {
            runs = [...runs].sort((a, b) => (b.best_accuracy ?? 0) - (a.best_accuracy ?? 0));
        } else {
            runs = [...runs].sort((a, b) => (b.modified_at ?? 0) - (a.modified_at ?? 0));
        }
        return runs;
    }

    renderResultsSummary() {
        const el = document.getElementById('results-summary');
        const complete = this._resultsRuns.filter((r) => r.status === 'complete');
        const withAcc = complete.filter((r) => r.best_accuracy != null);
        const best = withAcc.length
            ? withAcc.reduce((a, b) => ((a.best_accuracy ?? 0) > (b.best_accuracy ?? 0) ? a : b))
            : null;
        el.innerHTML = `
            <div class="stat-card"><span class="stat-label">Runs</span><span class="stat-value">${this._resultsRuns.length}</span></div>
            <div class="stat-card"><span class="stat-label">Completed</span><span class="stat-value">${complete.length}</span></div>
            <div class="stat-card"><span class="stat-label">Best accuracy</span><span class="stat-value">${best ? this.fmtAcc(best.best_accuracy) : '—'}</span></div>
            <div class="stat-card"><span class="stat-label">Best run</span><span class="stat-value stat-value-sm">${best ? this.esc(best.id) : '—'}</span></div>
        `;
    }

    renderResultsTable() {
        const wrap = document.getElementById('results-table-wrap');
        const runs = this.getFilteredRuns();
        if (!this._resultsRuns.length) {
            wrap.innerHTML = `<div class="results-empty">
                <p><strong>No experiment results yet</strong></p>
                <p class="text-muted">Run an experiment from the Experiments tab. Metrics are saved under <code>results/</code>.</p>
            </div>`;
            return;
        }
        if (!runs.length) {
            wrap.innerHTML = '<p class="text-muted results-empty">No runs match the filters.</p>';
            return;
        }
        let html = `<table class="results-table"><thead><tr>
            <th class="col-check"></th><th>Run</th><th>Status</th><th>Dataset</th><th>Method</th>
            <th>Clients</th><th>Rounds</th><th>Final</th><th>Best</th><th>Duration</th><th>When</th>
        </tr></thead><tbody>`;
        runs.forEach((r) => {
            const rounds = r.rounds_completed != null && r.rounds_planned != null
                ? `${r.rounds_completed}/${r.rounds_planned}` : '—';
            const selected = r.id === this._selectedRunId ? ' results-row-selected' : '';
            const accClass = r.final_accuracy != null && r.final_accuracy >= 0.9 ? ' acc-high' : '';
            const checked = this._compareSelected.has(r.id) ? ' checked' : '';
            html += `<tr class="results-row${selected}" data-run-id="${this.esc(r.id)}" tabindex="0">
                <td class="col-check" onclick="event.stopPropagation()"><input type="checkbox" class="compare-check" data-run-id="${this.esc(r.id)}"${checked} aria-label="Compare ${this.esc(r.id)}"></td>
                <td><code class="run-id">${this.esc(r.id)}</code></td>
                <td>${this.statusBadge(r)}</td>
                <td>${this.esc(r.dataset || '—')}</td>
                <td>${this.methodBadge(r.method)}</td>
                <td>${r.num_clients ?? '—'}</td>
                <td>${rounds}</td>
                <td class="acc-cell${accClass}">${this.fmtAcc(r.final_accuracy)}</td>
                <td class="acc-cell">${this.fmtAcc(r.best_accuracy)}</td>
                <td>${this.fmtTime(r.total_time_ms)}</td>
                <td class="text-muted col-date">${this.fmtDate(r.modified_at)}</td>
            </tr>`;
        });
        html += '</tbody></table>';
        wrap.innerHTML = html;
        wrap.querySelectorAll('.results-row').forEach((row) => {
            row.addEventListener('click', () => this.showResultDetail(row.getAttribute('data-run-id')));
            row.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.showResultDetail(row.getAttribute('data-run-id'));
                }
            });
        });
        wrap.querySelectorAll('.compare-check').forEach((cb) => {
            cb.addEventListener('change', (e) => {
                const id = cb.getAttribute('data-run-id');
                if (e.target.checked && !this.toggleCompareRun(id, true)) {
                    e.target.checked = false;
                } else if (!e.target.checked) {
                    this.toggleCompareRun(id, false);
                }
            });
        });
        this.updateCompareUi();
    }

    closeResultDetail() {
        document.getElementById('results-detail').hidden = true;
        this._selectedRunId = null;
        this.renderResultsTable();
    }

    renderAccuracyChart(rounds, options = {}) {
        if (!rounds.length) return '<p class="text-muted">No round metrics.</p>';
        const w = 640;
        const h = 180;
        const pad = { t: 16, r: 16, b: 28, l: 44 };
        const innerW = w - pad.l - pad.r;
        const innerH = h - pad.t - pad.b;
        const stroke = options.color || null;
        const strokeClass = stroke ? '' : ' chart-line';
        const strokeAttr = stroke ? ` stroke="${stroke}"` : '';
        const accs = rounds.map((r) => r.accuracy ?? 0);
        const minA = options.minA ?? Math.max(0, Math.min(...accs) - 0.02);
        const maxA = options.maxA ?? Math.min(1, Math.max(...accs) + 0.02);
        const range = Math.max(maxA - minA, 0.05);
        const pts = rounds.map((r, i) => {
            const x = pad.l + (i / Math.max(rounds.length - 1, 1)) * innerW;
            const y = pad.t + innerH - (((r.accuracy ?? 0) - minA) / range) * innerH;
            return `${x.toFixed(1)},${y.toFixed(1)}`;
        });
        const circles = rounds.map((r, i) => {
            const x = pad.l + (i / Math.max(rounds.length - 1, 1)) * innerW;
            const y = pad.t + innerH - (((r.accuracy ?? 0) - minA) / range) * innerH;
            const fill = stroke || '#667eea';
            return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3" fill="${fill}" stroke="white" stroke-width="1"><title>Round ${r.round}: ${this.fmtAcc(r.accuracy)}</title></circle>`;
        }).join('');
        const yMid = pad.t + innerH / 2;
        const yTopLabel = `${(maxA * 100).toFixed(0)}%`;
        const yBotLabel = `${(minA * 100).toFixed(0)}%`;
        const axes = options.skipAxes ? '' : `
            <line x1="${pad.l}" y1="${pad.t}" x2="${pad.l}" y2="${pad.t + innerH}" class="chart-axis"/>
            <line x1="${pad.l}" y1="${pad.t + innerH}" x2="${pad.l + innerW}" y2="${pad.t + innerH}" class="chart-axis"/>
            <text x="${pad.l - 6}" y="${pad.t + 4}" class="chart-tick" text-anchor="end">${yTopLabel}</text>
            <text x="${pad.l - 6}" y="${pad.t + innerH}" class="chart-tick" text-anchor="end">${yBotLabel}</text>
            <text x="8" y="${yMid}" class="chart-label" transform="rotate(-90 8 ${yMid})">Accuracy</text>`;
        return `<svg viewBox="0 0 ${w} ${h}" class="results-chart" role="img" aria-label="Accuracy per round">
            ${axes}
            <polyline points="${pts.join(' ')}" class="${strokeClass.trim() || 'chart-line'}" fill="none"${strokeAttr}/>
            ${circles}
        </svg>`;
    }

    renderMultiAccuracyChart(seriesList) {
        if (!seriesList.length) return '<p class="text-muted">Select runs to compare.</p>';
        const w = 640;
        const h = 200;
        const pad = { t: 16, r: 16, b: 28, l: 44 };
        const innerW = w - pad.l - pad.r;
        const innerH = h - pad.t - pad.b;
        const allAccs = seriesList.flatMap((s) => (s.rounds || []).map((r) => r.accuracy ?? 0));
        if (!allAccs.length) return '<p class="text-muted">No metrics in selected runs.</p>';
        const minA = Math.max(0, Math.min(...allAccs) - 0.02);
        const maxA = Math.min(1, Math.max(...allAccs) + 0.02);
        const range = Math.max(maxA - minA, 0.05);
        const maxLen = Math.max(...seriesList.map((s) => (s.rounds || []).length), 1);
        const lines = seriesList.map((s, si) => {
            const rounds = s.rounds || [];
            const color = this._chartColors[si % this._chartColors.length];
            const pts = rounds.map((r, i) => {
                const x = pad.l + (i / Math.max(maxLen - 1, 1)) * innerW;
                const y = pad.t + innerH - (((r.accuracy ?? 0) - minA) / range) * innerH;
                return `${x.toFixed(1)},${y.toFixed(1)}`;
            });
            return `<polyline points="${pts.join(' ')}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round"/>`;
        }).join('');
        const yMid = pad.t + innerH / 2;
        return `<svg viewBox="0 0 ${w} ${h}" class="results-chart" role="img" aria-label="Compare accuracy">
            <line x1="${pad.l}" y1="${pad.t}" x2="${pad.l}" y2="${pad.t + innerH}" class="chart-axis"/>
            <line x1="${pad.l}" y1="${pad.t + innerH}" x2="${pad.l + innerW}" y2="${pad.t + innerH}" class="chart-axis"/>
            <text x="${pad.l - 6}" y="${pad.t + 4}" class="chart-tick" text-anchor="end">${(maxA * 100).toFixed(0)}%</text>
            <text x="${pad.l - 6}" y="${pad.t + innerH}" class="chart-tick" text-anchor="end">${(minA * 100).toFixed(0)}%</text>
            <text x="8" y="${yMid}" class="chart-label" transform="rotate(-90 8 ${yMid})">Accuracy</text>
            ${lines}
        </svg>`;
    }

    updateCompareUi() {
        const n = this._compareSelected.size;
        const btn = document.getElementById('results-compare-btn');
        btn.disabled = n < 2;
        btn.textContent = `Compare selected (${n})`;
    }

    toggleCompareRun(runId, checked) {
        if (checked) {
            if (this._compareSelected.size >= 4) {
                return false;
            }
            this._compareSelected.add(runId);
        } else {
            this._compareSelected.delete(runId);
        }
        this.updateCompareUi();
        return true;
    }

    clearCompareSelection() {
        this._compareSelected.clear();
        document.getElementById('results-compare-panel').hidden = true;
        this.updateCompareUi();
        this.renderResultsTable();
    }

    async compareSelectedRuns() {
        const ids = [...this._compareSelected];
        if (ids.length < 2) return;
        const panel = document.getElementById('results-compare-panel');
        panel.hidden = false;
        document.getElementById('results-compare-chart').innerHTML = '<p class="text-muted">Loading…</p>';
        panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        try {
            const { res, data } = await this.fetchJson(`/api/results/compare?ids=${encodeURIComponent(ids.join(','))}`);
            if (!data.ok) throw new Error(data.error || 'Compare failed');
            document.getElementById('results-compare-chart').innerHTML = this.renderMultiAccuracyChart(data.series);
            const legend = document.getElementById('results-compare-legend');
            legend.innerHTML = data.series.map((s, i) => {
                const color = this._chartColors[i % this._chartColors.length];
                const sum = s.summary || {};
                return `<span class="compare-legend-item"><span class="compare-swatch" style="background:${color}"></span>
                    <code>${this.esc(s.id)}</code> — ${this.fmtAcc(sum.final_accuracy)} final · ${this.esc(sum.dataset || '')} · ${this.esc(sum.attack && sum.attack !== 'none' ? sum.attack : 'no attack')}</span>`;
            }).join('');
        } catch (e) {
            document.getElementById('results-compare-chart').innerHTML = `<p class="message error">${this.esc(e.message)}</p>`;
        }
    }

    async showResultDetail(runId) {
        this._selectedRunId = runId;
        this.renderResultsTable();
        const panel = document.getElementById('results-detail');
        panel.hidden = false;
        panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        document.getElementById('results-detail-title').textContent = runId;
        document.getElementById('results-detail-subtitle').textContent = 'Loading…';
        document.getElementById('results-detail-cards').innerHTML = '';
        document.getElementById('results-chart-wrap').innerHTML = '';
        document.getElementById('results-rounds-wrap').innerHTML = '';
        try {
            const { res, data } = await this.fetchJson(`/api/results/${encodeURIComponent(runId)}`);
            if (!data.ok) throw new Error(data.error || 'Not found');
            const s = data.summary || {};
            const attack = s.attack && s.attack !== 'none' ? ` · attack: ${s.attack}` : '';
            document.getElementById('results-detail-subtitle').textContent =
                `${s.dataset || ''} · ${s.method || ''} · ${s.num_clients || '?'} clients${attack} · ${this.fmtDate(s.modified_at)}`;

            document.getElementById('results-detail-cards').innerHTML = `
                <div class="stat-card stat-card-accent"><span class="stat-label">Final accuracy</span><span class="stat-value">${this.fmtAcc(s.final_accuracy)}</span></div>
                <div class="stat-card"><span class="stat-label">Best accuracy</span><span class="stat-value">${this.fmtAcc(s.best_accuracy)}</span></div>
                <div class="stat-card"><span class="stat-label">Rounds</span><span class="stat-value">${s.rounds_completed ?? 0}/${s.rounds_planned ?? '?'}</span></div>
                <div class="stat-card"><span class="stat-label">Total time</span><span class="stat-value">${this.fmtTime(s.total_time_ms)}</span></div>
                <div class="stat-card"><span class="stat-label">AHDA last round</span><span class="stat-value">${s.clients_accepted ?? '—'} accepted${s.clients_rejected ? `, ${s.clients_rejected} rejected` : ''}</span></div>
            `;

            document.getElementById('results-chart-wrap').innerHTML =
                `<h4 class="results-section-title">Accuracy over rounds</h4>${this.renderAccuracyChart(data.rounds || [])}`;

            let table = `<h4 class="results-section-title">Per-round metrics</h4>
                <table class="results-table results-rounds-table"><thead><tr>
                <th>Round</th><th>Accuracy</th><th>Progress</th>
                <th>Accepted</th><th>Rejected</th><th>Time</th>
                </tr></thead><tbody>`;
            (data.rounds || []).forEach((row) => {
                const pct = row.accuracy != null ? Math.round(row.accuracy * 100) : 0;
                table += `<tr>
                    <td>${row.round}</td>
                    <td class="acc-cell">${this.fmtAcc(row.accuracy)}</td>
                    <td><div class="acc-bar-track"><div class="acc-bar-fill" style="width:${pct}%"></div></div></td>
                    <td>${row.num_accepted ?? '—'}</td>
                    <td>${row.num_rejected ?? '—'}</td>
                    <td>${Math.round(row.elapsed_ms || 0)} ms</td>
                </tr>`;
            });
            table += '</tbody></table>';
            document.getElementById('results-rounds-wrap').innerHTML = table;
            document.getElementById('results-config-json').textContent = JSON.stringify(data.config || {}, null, 2);
            document.getElementById('results-export-link').href =
                `${this.apiBase}/api/results/${encodeURIComponent(runId)}/export`;
        } catch (e) {
            document.getElementById('results-detail-subtitle').textContent = e.message;
        }
    }

    renderSystemDashboard(data) {
        const ccf = data.ccf || {};
        const certs = data.certs || {};
        const tf = data.tensorflow || {};
        const card = (label, ok, detail) => `
            <div class="system-card ${ok ? 'system-card-ok' : 'system-card-warn'}">
                <span class="system-card-label">${label}</span>
                <span class="system-card-status">${ok ? 'OK' : 'Issue'}</span>
                <span class="system-card-detail">${this.esc(detail)}</span>
            </div>`;
        const el = document.getElementById('system-dashboard');
        el.innerHTML = [
            card('CCF node', !!ccf.up, ccf.up ? ccf.url : (ccf.error || 'Not reachable')),
            card('User certificates', !!certs.ok, certs.ok
                ? `${certs.user_count} users in ${certs.cert_dir || 'sandbox'}`
                : `Missing: ${(certs.missing || []).join(', ') || 'certs'}`),
            card('TensorFlow', !!tf.ok, tf.ok ? `v${tf.version}` : (tf.hint || tf.detail || 'Unavailable')),
        ].join('');
    }

    async refreshSystemStatus() {
        try {
            const { res, data } = await this.fetchJson('/api/status');
            this.renderSystemDashboard(data);
            document.getElementById('system-status-content').textContent = JSON.stringify(data, null, 2);
            if (!data.ccf?.up) {
                this.showMessage('system-message', 'CCF is not running. Start it in the terminal below.', 'error');
            } else if (!data.certs?.ok) {
                this.showMessage('system-message', 'Missing certificates. Run: make run-virtual SANDBOX_USERS=5', 'error');
            } else {
                this.showMessage('system-message', 'Ready to run experiments.', 'success');
            }
        } catch (e) {
            document.getElementById('system-status-content').textContent = e.message;
        }
    }

    async cleanSandbox() {
        this.showMessage('system-message', 'Cleaning…', 'info');
        try {
            const { res, data } = await this.fetchJson('/api/sandbox/clean', { method: 'POST' });
            this.showMessage('system-message', `Removed ${(data.removed || []).length} dirs. Restart CCF.`, 'success');
            await this.refreshSystemStatus();
        } catch (e) {
            this.showMessage('system-message', e.message, 'error');
        }
    }
}

document.addEventListener('DOMContentLoaded', () => new CCFLApp());

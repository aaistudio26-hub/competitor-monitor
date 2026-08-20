/**
 * Competitor Monitor - Frontend Application
 * Мониторинг конкурентов - MVP ассистент
 */

// === State ===
const state = {
    currentTab: 'text',
    selectedImage: null,
    isLoading: false
};

// === DOM Elements ===
const elements = {
    // Navigation
    navButtons: document.querySelectorAll('.nav-btn'),
    tabContents: document.querySelectorAll('.tab-content'),
    
    // Text analysis
    competitorText: document.getElementById('competitor-text'),
    analyzeTextBtn: document.getElementById('analyze-text-btn'),
    
    // Image analysis
    uploadZone: document.getElementById('upload-zone'),
    imageInput: document.getElementById('image-input'),
    previewContainer: document.getElementById('preview-container'),
    imagePreview: document.getElementById('image-preview'),
    removeImageBtn: document.getElementById('remove-image'),
    analyzeImageBtn: document.getElementById('analyze-image-btn'),
    
    // Parse demo
    urlInput: document.getElementById('url-input'),
    parseBtn: document.getElementById('parse-btn'),
    collectCompetitorsBtn: document.getElementById('collect-competitors-btn'),
    competitorsList: document.getElementById('competitors-list'),
    
    // History
    historyList: document.getElementById('history-list'),
    clearHistoryBtn: document.getElementById('clear-history-btn'),
    
    // Results
    resultsSection: document.getElementById('results-section'),
    resultsContent: document.getElementById('results-content'),
    closeResultsBtn: document.getElementById('close-results'),
    
    // Loading
    loadingOverlay: document.getElementById('loading-overlay')
};

// === API Functions ===
const api = {
    baseUrl: '',
    
    async analyzeText(text) {
        const response = await fetch(`${this.baseUrl}/analyze_text`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        return response.json();
    },
    
    async analyzeImage(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${this.baseUrl}/analyze_image`, {
            method: 'POST',
            body: formData
        });
        return response.json();
    },
    
    async parseDemo(url) {
        const response = await fetch(`${this.baseUrl}/parse_demo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        return response.json();
    },

    async getCompetitors() {
        const response = await fetch(`${this.baseUrl}/competitors`);
        return response.json();
    },

    async collectCompetitors(withAi = true) {
        const response = await fetch(`${this.baseUrl}/collect_competitors`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ with_ai: withAi })
        });
        return response.json();
    },
    
    async getHistory() {
        const response = await fetch(`${this.baseUrl}/history`);
        return response.json();
    },
    
    async clearHistory() {
        const response = await fetch(`${this.baseUrl}/history`, {
            method: 'DELETE'
        });
        return response.json();
    }
};

// === UI Functions ===
const ui = {
    showLoading() {
        state.isLoading = true;
        elements.loadingOverlay.style.display = 'flex';
    },
    
    hideLoading() {
        state.isLoading = false;
        elements.loadingOverlay.style.display = 'none';
    },
    
    showTab(tabId) {
        state.currentTab = tabId;
        
        // Update navigation
        elements.navButtons.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabId);
        });
        
        // Update content
        elements.tabContents.forEach(content => {
            content.classList.toggle('active', content.id === `${tabId}-tab`);
        });
        
        // Load history if needed
        if (tabId === 'history') {
            this.loadHistory();
        }
    },
    
    showResults(html) {
        elements.resultsContent.innerHTML = html;
        elements.resultsSection.hidden = false;
        elements.resultsSection.scrollIntoView({ behavior: 'smooth' });
    },
    
    hideResults() {
        elements.resultsSection.hidden = true;
    },
    
    showError(message) {
        const html = `
            <div class="error-message">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <span>${message}</span>
            </div>
        `;
        this.showResults(html);
    },
    
    renderScore(label, score, note = '') {
        const value = Number(score) || 0;
        const percent = (value / 10) * 100;
        return `
            <div class="score-item">
                <div class="score-display">
                    <span class="score-label">${label}</span>
                    <span class="score-value">${value}/10</span>
                </div>
                <div class="score-bar">
                    <div class="score-fill" style="width: ${percent}%"></div>
                </div>
                ${note ? `<p class="score-note">${note}</p>` : ''}
            </div>
        `;
    },

    renderTextAnalysis(analysis) {
        return `
            ${this.renderResultBlock('Сильные стороны', analysis.strengths, 'strengths')}
            ${this.renderResultBlock('Слабые стороны', analysis.weaknesses, 'weaknesses')}
            ${this.renderResultBlock('Уникальные предложения', analysis.unique_offers, 'unique')}
            ${this.renderResultBlock('Фокус услуг', analysis.service_focus, 'unique')}
            ${this.renderResultBlock('Сигналы доверия', analysis.trust_signals, 'insights')}
            ${this.renderResultBlock('Пробелы для B2B-клиента', analysis.content_gaps, 'weaknesses')}
            ${this.renderResultBlock('Рекомендации', analysis.recommendations, 'recommendations')}

            <div class="result-block">
                <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                    </svg>
                    Оценки конкурента (юруслуги для бизнеса)
                </h3>
                ${this.renderScore('Доверие / экспертность', analysis.trust_score)}
                ${this.renderScore('Сила CTA (заявка / консультация)', analysis.cta_score)}
                ${this.renderScore('Понятность для предпринимателя', analysis.content_clarity_score)}
                ${this.renderScore('Покрытие услуг (рег./ликв./лицензии/арбитраж)', analysis.service_coverage_score)}
                ${this.renderScore('Прозрачность цен и условий', analysis.pricing_transparency_score)}
                ${this.renderScore('Конкурентная угроза', analysis.competitive_threat)}
                ${analysis.target_audience ? `<p><strong>ЦА:</strong> ${analysis.target_audience}</p>` : ''}
                ${analysis.positioning_notes ? `<p><strong>Позиционирование:</strong> ${analysis.positioning_notes}</p>` : ''}
            </div>

            ${analysis.summary ? `
                <div class="result-block result-summary">
                    <h3>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                        </svg>
                        Резюме
                    </h3>
                    <p>${analysis.summary}</p>
                </div>
            ` : ''}
        `;
    },
    
    renderImageAnalysis(analysis) {
        return `
            <div class="result-block">
                <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                        <circle cx="8.5" cy="8.5" r="1.5"/>
                        <polyline points="21 15 16 10 5 21"/>
                    </svg>
                    Описание
                </h3>
                <p>${analysis.description}</p>
            </div>
            
            <div class="result-block">
                <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                    </svg>
                    Оценки материала юрфирмы
                </h3>
                ${this.renderScore('Соответствие B2B-юрбренду', analysis.legal_branding_fit)}
                ${this.renderScore('Заметность услуг (рег./ликв./лицензии/арбитраж)', analysis.service_visibility_score)}
                ${this.renderScore('Ясность оффера для бизнеса', analysis.offer_clarity_score)}
                ${analysis.trust_perception ? `<p><strong>Восприятие доверия:</strong> ${analysis.trust_perception}</p>` : ''}
            </div>
            
            ${this.renderResultBlock('Маркетинговые инсайты', analysis.marketing_insights, 'insights')}
            ${this.renderResultBlock('Рекомендации', analysis.recommendations, 'recommendations')}
        `;
    },
    
    renderParsedContent(data) {
        const parsed = data;
        
        return `
            <div class="parsed-content">
                <div class="label">URL:</div>
                <div class="value">${parsed.url}</div>
                
                <div class="label">Title:</div>
                <div class="value">${parsed.title || 'Не найден'}</div>
                
                <div class="label">H1:</div>
                <div class="value">${parsed.h1 || 'Не найден'}</div>
                
                <div class="label">Первый абзац:</div>
                <div class="value">${parsed.first_paragraph || 'Не найден'}</div>

                ${parsed.meta_description ? `
                    <div class="label">Meta description:</div>
                    <div class="value">${parsed.meta_description}</div>
                ` : ''}

                ${parsed.contacts && parsed.contacts.length ? `
                    <div class="label">Контакты:</div>
                    <div class="value">${parsed.contacts.join(', ')}</div>
                ` : ''}

                ${parsed.cta_texts && parsed.cta_texts.length ? `
                    <div class="label">CTA:</div>
                    <div class="value">${parsed.cta_texts.join(' · ')}</div>
                ` : ''}

                ${parsed.service_links && parsed.service_links.length ? `
                    <div class="label">Услуги / ссылки:</div>
                    <div class="value"><ul>${parsed.service_links.map(s => `<li>${s}</li>`).join('')}</ul></div>
                ` : ''}
            </div>
            
            ${parsed.analysis ? this.renderTextAnalysis(parsed.analysis) : ''}
            ${parsed.error ? `<div class="result-block"><p class="error-text">${parsed.error}</p></div>` : ''}
        `;
    },

    renderCollectResults(result) {
        const items = result.items || [];
        const header = `
            <div class="result-block">
                <h3>Автосбор конкурентов</h3>
                <p>Собрано: ${result.total || items.length} сайтов из config</p>
                <ul>
                    ${(result.competitor_urls || []).map(u => `<li>${u}</li>`).join('')}
                </ul>
            </div>
        `;
        const blocks = items.map((item, idx) => `
            <div class="result-block">
                <h3>${idx + 1}. ${item.url}</h3>
            </div>
            ${this.renderParsedContent(item)}
        `).join('');
        return header + blocks;
    },
    
    renderResultBlock(title, items, type) {
        if (!items || items.length === 0) return '';
        
        const icons = {
            strengths: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
            weaknesses: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
            unique: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
            recommendations: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
            insights: '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>'
        };
        
        return `
            <div class="result-block">
                <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        ${icons[type] || icons.recommendations}
                    </svg>
                    ${title}
                </h3>
                <ul>
                    ${items.map(item => `<li>${item}</li>`).join('')}
                </ul>
            </div>
        `;
    },
    
    async loadHistory() {
        try {
            const data = await api.getHistory();
            this.renderHistory(data.items);
        } catch (error) {
            console.error('Failed to load history:', error);
        }
    },
    
    renderHistory(items) {
        if (!items || items.length === 0) {
            elements.historyList.innerHTML = `
                <div class="history-empty">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <polyline points="12 6 12 12 16 14"/>
                    </svg>
                    <p>История пуста</p>
                </div>
            `;
            return;
        }
        
        const icons = {
            text: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
            image: '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>',
            parse: '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'
        };
        
        const typeLabels = {
            text: 'Анализ текста',
            image: 'Анализ изображения',
            parse: 'Парсинг сайта'
        };
        
        elements.historyList.innerHTML = items.map(item => {
            const date = new Date(item.timestamp);
            const timeStr = date.toLocaleString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
            
            return `
                <div class="history-item">
                    <div class="history-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            ${icons[item.request_type] || icons.text}
                        </svg>
                    </div>
                    <div class="history-content">
                        <div class="history-type">${typeLabels[item.request_type] || item.request_type}</div>
                        <div class="history-summary">${item.request_summary}</div>
                    </div>
                    <div class="history-time">${timeStr}</div>
                </div>
            `;
        }).join('');
    }
};

// === Event Handlers ===
const handlers = {
    // Navigation
    handleNavClick(e) {
        const btn = e.target.closest('.nav-btn');
        if (btn) {
            ui.showTab(btn.dataset.tab);
        }
    },
    
    // Text analysis
    async handleAnalyzeText() {
        const text = elements.competitorText.value.trim();
        
        if (text.length < 10) {
            ui.showError('Введите текст минимум 10 символов для анализа');
            return;
        }
        
        ui.showLoading();
        
        try {
            const result = await api.analyzeText(text);
            
            if (result.success && result.analysis) {
                ui.showResults(ui.renderTextAnalysis(result.analysis));
            } else {
                ui.showError(result.error || 'Произошла ошибка при анализе');
            }
        } catch (error) {
            ui.showError('Ошибка соединения с сервером');
            console.error(error);
        } finally {
            ui.hideLoading();
        }
    },
    
    // Image upload
    handleUploadClick() {
        elements.imageInput.click();
    },
    
    handleImageSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.processImage(file);
        }
    },
    
    handleDragOver(e) {
        e.preventDefault();
        elements.uploadZone.classList.add('dragover');
    },
    
    handleDragLeave(e) {
        e.preventDefault();
        elements.uploadZone.classList.remove('dragover');
    },
    
    handleDrop(e) {
        e.preventDefault();
        elements.uploadZone.classList.remove('dragover');
        
        const file = e.dataTransfer.files[0];
        if (file && this.isSupportedVisualFile(file)) {
            this.processImage(file);
        } else {
            ui.showError('Поддерживаются изображения (PNG, JPG, GIF, WEBP) и PDF');
        }
    },

    isSupportedVisualFile(file) {
        if (!file) return false;
        const type = (file.type || '').toLowerCase();
        const name = (file.name || '').toLowerCase();
        if (type.startsWith('image/')) return true;
        if (type === 'application/pdf' || name.endsWith('.pdf')) return true;
        return false;
    },

    isPdfFile(file) {
        if (!file) return false;
        const type = (file.type || '').toLowerCase();
        const name = (file.name || '').toLowerCase();
        return type === 'application/pdf' || name.endsWith('.pdf');
    },
    
    processImage(file) {
        if (!this.isSupportedVisualFile(file)) {
            ui.showError('Поддерживаются изображения (PNG, JPG, GIF, WEBP) и PDF');
            return;
        }

        state.selectedImage = file;
        elements.previewContainer.hidden = false;
        elements.uploadZone.querySelector('.upload-content').hidden = true;
        elements.analyzeImageBtn.disabled = false;

        const pdfPreview = document.getElementById('pdf-preview');
        const pdfName = document.getElementById('pdf-preview-name');

        if (this.isPdfFile(file)) {
            elements.imagePreview.hidden = true;
            elements.imagePreview.src = '';
            if (pdfPreview) {
                pdfPreview.hidden = false;
                if (pdfName) pdfName.textContent = file.name;
            }
            return;
        }

        if (pdfPreview) pdfPreview.hidden = true;
        elements.imagePreview.hidden = false;

        const reader = new FileReader();
        reader.onload = (e) => {
            elements.imagePreview.src = e.target.result;
        };
        reader.readAsDataURL(file);
    },
    
    handleRemoveImage() {
        state.selectedImage = null;
        elements.imageInput.value = '';
        elements.imagePreview.src = '';
        elements.imagePreview.hidden = false;
        const pdfPreview = document.getElementById('pdf-preview');
        if (pdfPreview) pdfPreview.hidden = true;
        elements.previewContainer.hidden = true;
        elements.uploadZone.querySelector('.upload-content').hidden = false;
        elements.analyzeImageBtn.disabled = true;
    },
    
    async handleAnalyzeImage() {
        if (!state.selectedImage) {
            ui.showError('Выберите изображение или PDF для анализа');
            return;
        }
        
        ui.showLoading();
        
        try {
            const result = await api.analyzeImage(state.selectedImage);
            
            if (result.success && result.analysis) {
                ui.showResults(ui.renderImageAnalysis(result.analysis));
            } else {
                ui.showError(result.error || 'Произошла ошибка при анализе файла');
            }
        } catch (error) {
            ui.showError('Ошибка соединения с сервером');
            console.error(error);
        } finally {
            ui.hideLoading();
        }
    },
    
    // Parse demo
    async handleParse() {
        let url = elements.urlInput.value.trim();
        
        if (!url) {
            ui.showError('Введите URL сайта для парсинга');
            return;
        }
        
        // Add protocol if missing
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            url = 'https://' + url;
        }
        
        ui.showLoading();
        
        try {
            const result = await api.parseDemo(url);
            
            if (result.success && result.data) {
                ui.showResults(ui.renderParsedContent(result.data));
            } else {
                ui.showError(result.error || 'Не удалось распарсить сайт');
            }
        } catch (error) {
            ui.showError('Ошибка соединения с сервером');
            console.error(error);
        } finally {
            ui.hideLoading();
        }
    },

    async loadCompetitorsList() {
        if (!elements.competitorsList) return;
        try {
            const data = await api.getCompetitors();
            const urls = data.competitor_urls || [];
            if (!urls.length) {
                elements.competitorsList.innerHTML = '<small class="muted">Список COMPETITOR_URLS пуст — добавьте URL в config.py или .env</small>';
                return;
            }
            elements.competitorsList.innerHTML = `
                <small class="muted">Конкуренты из config (${urls.length}):</small>
                <ul class="competitors-urls">
                    ${urls.map(u => `<li><a href="${u}" target="_blank" rel="noopener">${u}</a></li>`).join('')}
                </ul>
            `;
        } catch (e) {
            elements.competitorsList.innerHTML = '<small class="muted">Не удалось загрузить список конкурентов</small>';
        }
    },

    async handleCollectCompetitors() {
        ui.showLoading();
        try {
            const result = await api.collectCompetitors(true);
            if (result.success) {
                ui.showResults(ui.renderCollectResults(result));
            } else {
                ui.showError(result.error || 'Не удалось выполнить автосбор');
            }
        } catch (error) {
            ui.showError('Ошибка соединения с сервером (автосбор может занять несколько минут)');
            console.error(error);
        } finally {
            ui.hideLoading();
        }
    },
    
    // History
    async handleClearHistory() {
        if (!confirm('Вы уверены, что хотите очистить историю?')) {
            return;
        }
        
        try {
            await api.clearHistory();
            ui.renderHistory([]);
        } catch (error) {
            console.error('Failed to clear history:', error);
        }
    },
    
    // Results
    handleCloseResults() {
        ui.hideResults();
    }
};

// === Initialize ===
function init() {
    // Navigation
    elements.navButtons.forEach(btn => {
        btn.addEventListener('click', handlers.handleNavClick.bind(handlers));
    });
    
    // Text analysis
    elements.analyzeTextBtn.addEventListener('click', handlers.handleAnalyzeText.bind(handlers));
    
    // Image upload
    elements.uploadZone.addEventListener('click', handlers.handleUploadClick.bind(handlers));
    elements.imageInput.addEventListener('change', handlers.handleImageSelect.bind(handlers));
    elements.uploadZone.addEventListener('dragover', handlers.handleDragOver.bind(handlers));
    elements.uploadZone.addEventListener('dragleave', handlers.handleDragLeave.bind(handlers));
    elements.uploadZone.addEventListener('drop', handlers.handleDrop.bind(handlers));
    elements.removeImageBtn.addEventListener('click', handlers.handleRemoveImage.bind(handlers));
    elements.analyzeImageBtn.addEventListener('click', handlers.handleAnalyzeImage.bind(handlers));
    
    // Parse demo
    elements.parseBtn.addEventListener('click', handlers.handleParse.bind(handlers));
    elements.urlInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handlers.handleParse.call(handlers);
    });
    if (elements.collectCompetitorsBtn) {
        elements.collectCompetitorsBtn.addEventListener(
            'click',
            handlers.handleCollectCompetitors.bind(handlers)
        );
    }
    handlers.loadCompetitorsList();
    
    // History
    elements.clearHistoryBtn.addEventListener('click', handlers.handleClearHistory.bind(handlers));
    
    // Results
    elements.closeResultsBtn.addEventListener('click', handlers.handleCloseResults.bind(handlers));
    
    // Show default tab
    ui.showTab('text');
}

// Start app
document.addEventListener('DOMContentLoaded', init);


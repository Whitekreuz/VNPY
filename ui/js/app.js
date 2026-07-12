/* ==========================================================================
   Moderixest Trade Quant Dashboard - Client-side JS Application
   Handles UI Routing, Theme Management, Sidebar Resize/Collapse,
   Grouped Dropdowns, and API communication.
   ========================================================================== */

window.onerror = function(message, source, lineno, colno, error) {
    alert("JS Error: " + message + "\nSource: " + source + "\nLine: " + lineno + "\nColumn: " + colno);
    console.error(error);
    return false;
};

document.addEventListener("DOMContentLoaded", () => {
    // ─── 1. DOM Element Selectors ──────────────────────────────────────────
    const menuItems = document.querySelectorAll(".menu-item");
    const pageSections = document.querySelectorAll(".page-section");
    const pageTitleText = document.getElementById("page-title-text");
    
    const themeToggleBtn = document.getElementById("theme-toggle-btn");
    const themeIconEl = document.getElementById("theme-icon-el");
    const autoTimeCheckbox = document.getElementById("auto-time-checkbox");
    
    const btnSyncDb = document.getElementById("btn-sync-db");
    
    // Sidebar resizer & collapse selectors
    const sidebar = document.getElementById("app-sidebar");
    const layout = document.getElementById("app-layout");
    const resizer = document.getElementById("sidebar-resizer");
    const toggleSidebarBtn = document.getElementById("sidebar-toggle-btn");

    // Grouped Selectors - Backtest
    const btSectorsList = document.getElementById("backtest-sectors-list");
    const btVarietiesList = document.getElementById("backtest-varieties-list");
    const btContractsList = document.getElementById("backtest-contracts-list");
    const btSelectedList = document.getElementById("backtest-selected-list");
    const btnAddSelected = document.getElementById("btn-add-selected");
    const btnClearSelected = document.getElementById("btn-clear-selected");

    // Grouped Selectors - Optimizer
    const optSectors = document.getElementById("opt-sectors");
    const optVarieties = document.getElementById("opt-varieties");
    const optSymbol = document.getElementById("opt-symbol");
    const optMode = document.getElementById("opt-mode");
    const optBoxParam = document.getElementById("opt-box-param");
    const optBoxInterval = document.getElementById("opt-box-interval");

    // Paper trading selectors
    const paperOrderSymbol = document.getElementById("paper-order-symbol");
    const btnPaperSubmit = document.getElementById("btn-paper-submit");
    const btnPaperRefresh = document.getElementById("btn-paper-refresh");

    // Global categorized symbol data storage
    let symbolData = {};
    let chartEquityInstance = null;
    let currentEquitySeries = null;

    // ─── Indicator Dropdowns & Configs ─────────────────────────────────────
    let mainIndicatorConfigs = {
        "MA": { name: "MA 均线", active: true, params: { fast: 10, slow: 30 }, paramLabels: { fast: "快线周期", slow: "慢线周期" } },
        "BOLL": { name: "BOLL 布林带", active: false, params: { period: 20, std: 2 }, paramLabels: { period: "计算周期", std: "标准差倍数" } },
        "EMA": { name: "EMA 指数均线", active: false, params: { period: 10 }, paramLabels: { period: "EMA周期" } }
    };

    let subIndicatorConfigs = {
        "MACD": { name: "MACD", active: true, params: { fast: 12, slow: 26, signal: 9 }, paramLabels: { fast: "快线周期", slow: "慢线周期", signal: "信号线周期" } },
        "RSI": { name: "RSI", active: false, params: { period: 14 }, paramLabels: { period: "RSI周期" } },
        "KDJ": { name: "KDJ", active: false, params: { period: 9 }, paramLabels: { period: "KDJ周期" } },
        "VOL": { name: "成交量", active: false, params: {}, paramLabels: {} }
    };

    const mainIndicatorSelected = document.getElementById("main-indicator-selected");
    const mainIndicatorList = document.getElementById("main-indicator-list");
    const subIndicatorSelected = document.getElementById("sub-indicator-selected");
    const subIndicatorList = document.getElementById("sub-indicator-list");

    const settingsModal = document.getElementById("indicator-settings-modal");
    const settingsTitle = document.getElementById("indicator-settings-title");
    const settingsBody = document.getElementById("indicator-settings-body");
    const btnSettingsClose = document.getElementById("btn-indicator-settings-close");
    const btnSettingsCancel = document.getElementById("btn-indicator-settings-cancel");
    const btnSettingsSave = document.getElementById("btn-indicator-settings-save");

    let currentEditingIndicator = null;
    let currentEditingType = null; // 'main' or 'sub'

    if (mainIndicatorSelected) {
        mainIndicatorSelected.addEventListener("click", (e) => {
            e.stopPropagation();
            mainIndicatorList.style.display = mainIndicatorList.style.display === "block" ? "none" : "block";
            subIndicatorList.style.display = "none";
        });
    }

    if (subIndicatorSelected) {
        subIndicatorSelected.addEventListener("click", (e) => {
            e.stopPropagation();
            subIndicatorList.style.display = subIndicatorList.style.display === "block" ? "none" : "block";
            mainIndicatorList.style.display = "none";
        });
    }

    document.addEventListener("click", () => {
        if (mainIndicatorList) mainIndicatorList.style.display = "none";
        if (subIndicatorList) subIndicatorList.style.display = "none";
    });

    function updateDropdownLabels() {
        if (!mainIndicatorSelected || !subIndicatorSelected) return;
        const activeMains = Object.keys(mainIndicatorConfigs)
            .filter(k => mainIndicatorConfigs[k].active)
            .map(k => mainIndicatorConfigs[k].name);
        mainIndicatorSelected.querySelector("span").textContent = activeMains.length > 0 ? "已选: " + activeMains.join(", ") : "选择主图指标";

        const activeSubs = Object.keys(subIndicatorConfigs)
            .filter(k => subIndicatorConfigs[k].active)
            .map(k => subIndicatorConfigs[k].name);
        subIndicatorSelected.querySelector("span").textContent = activeSubs.length > 0 ? "已选: " + activeSubs.join(", ") : "选择副图指标";
    }

    function renderIndicatorDropdowns() {
        if (!mainIndicatorList || !subIndicatorList) return;
        
        mainIndicatorList.innerHTML = "";
        Object.keys(mainIndicatorConfigs).forEach(key => {
            const config = mainIndicatorConfigs[key];
            const item = document.createElement("div");
            item.className = `indicator-dropdown-item ${config.active ? 'active' : ''}`;
            
            const labelSpan = document.createElement("span");
            labelSpan.className = "indicator-name";
            labelSpan.innerHTML = `<input type="checkbox" style="margin-right: 6px;" ${config.active ? 'checked' : ''}> ${config.name}`;
            
            const actionsDiv = document.createElement("div");
            actionsDiv.className = "indicator-actions";
            if (config.params && Object.keys(config.params).length > 0) {
                const gear = document.createElement("span");
                gear.className = "btn-icon-setting";
                gear.innerHTML = "⚙️";
                gear.title = "设置参数";
                gear.addEventListener("click", (e) => {
                    e.stopPropagation();
                    openSettingsModal(key, 'main');
                });
                actionsDiv.appendChild(gear);
            }

            item.appendChild(labelSpan);
            item.appendChild(actionsDiv);

            item.addEventListener("click", (e) => {
                e.stopPropagation();
                config.active = !config.active;
                item.querySelector("input").checked = config.active;
                if (config.active) {
                    item.classList.add("active");
                } else {
                    item.classList.remove("active");
                }
                updateDropdownLabels();
                if (currentChartBars) {
                    renderKlineChart(currentChartBars);
                }
            });

            mainIndicatorList.appendChild(item);
        });

        subIndicatorList.innerHTML = "";
        Object.keys(subIndicatorConfigs).forEach(key => {
            const config = subIndicatorConfigs[key];
            const item = document.createElement("div");
            item.className = `indicator-dropdown-item ${config.active ? 'active' : ''}`;
            
            const labelSpan = document.createElement("span");
            labelSpan.className = "indicator-name";
            labelSpan.innerHTML = `<input type="checkbox" style="margin-right: 6px;" ${config.active ? 'checked' : ''}> ${config.name}`;
            
            const actionsDiv = document.createElement("div");
            actionsDiv.className = "indicator-actions";
            if (config.params && Object.keys(config.params).length > 0) {
                const gear = document.createElement("span");
                gear.className = "btn-icon-setting";
                gear.innerHTML = "⚙️";
                gear.title = "设置参数";
                gear.addEventListener("click", (e) => {
                    e.stopPropagation();
                    openSettingsModal(key, 'sub');
                });
                actionsDiv.appendChild(gear);
            }

            item.appendChild(labelSpan);
            item.appendChild(actionsDiv);

            item.addEventListener("click", (e) => {
                e.stopPropagation();
                Object.keys(subIndicatorConfigs).forEach(k => {
                    if (k !== key) {
                        subIndicatorConfigs[k].active = false;
                    }
                });
                config.active = !config.active;
                renderIndicatorDropdowns();
                updateDropdownLabels();
                if (currentChartBars) {
                    renderKlineChart(currentChartBars);
                }
            });

            subIndicatorList.appendChild(item);
        });
    }

    function openSettingsModal(key, type) {
        currentEditingIndicator = key;
        currentEditingType = type;
        const config = type === 'main' ? mainIndicatorConfigs[key] : subIndicatorConfigs[key];
        
        settingsTitle.textContent = `${config.name} 参数设置`;
        settingsBody.innerHTML = "";

        Object.keys(config.params).forEach(pKey => {
            const formGroup = document.createElement("div");
            formGroup.className = "form-group";
            formGroup.style.marginBottom = "12px";

            const label = document.createElement("label");
            label.textContent = config.paramLabels[pKey] || pKey;
            label.style.display = "block";
            label.style.marginBottom = "4px";

            const input = document.createElement("input");
            input.type = "number";
            input.className = "form-input";
            input.value = config.params[pKey];
            input.dataset.param = pKey;

            formGroup.appendChild(label);
            formGroup.appendChild(input);
            settingsBody.appendChild(formGroup);
        });

        settingsModal.style.display = "flex";
    }

    function closeSettingsModal() {
        settingsModal.style.display = "none";
        currentEditingIndicator = null;
        currentEditingType = null;
    }

    if (btnSettingsClose) btnSettingsClose.addEventListener("click", closeSettingsModal);
    if (btnSettingsCancel) btnSettingsCancel.addEventListener("click", closeSettingsModal);

    if (btnSettingsSave) {
        btnSettingsSave.addEventListener("click", () => {
            if (!currentEditingIndicator || !currentEditingType) return;
            const config = currentEditingType === 'main' ? mainIndicatorConfigs[currentEditingIndicator] : subIndicatorConfigs[currentEditingIndicator];
            
            const inputs = settingsBody.querySelectorAll("input");
            inputs.forEach(input => {
                const pKey = input.dataset.param;
                const val = parseFloat(input.value);
                if (!isNaN(val)) {
                    config.params[pKey] = val;
                }
            });

            closeSettingsModal();
            if (currentChartBars) {
                renderKlineChart(currentChartBars);
            }
        });
    }

    // ─── 2. SPA Route Management ──────────────────────────────────────────
    const routeTitles = {
        "backtest": "策略回测与组合看板",
        "pool": "我的策略池历史记录",
        "optimize": "多进程参数与周期寻优",
        "paper": "模拟盘虚拟交易与持仓",
        "live": "实盘监控与风控预警",
        "chart": "K线看板 · 技术指标工坊"
    };

    function handleRoute(hash) {
        const pageId = hash.replace("#", "") || "chart";
        
        // Update menu active states
        menuItems.forEach(item => {
            if (item.getAttribute("href") === `#${pageId}`) {
                item.classList.add("active");
            } else {
                item.classList.remove("active");
            }
        });

        // Toggle active sections
        pageSections.forEach(section => {
            if (section.getAttribute("id") === `page-${pageId}`) {
                section.classList.add("active");
            } else {
                section.classList.remove("active");
            }
        });

        // Update top header title
        if (pageTitleText) {
            pageTitleText.textContent = routeTitles[pageId] || "Moderixest Trade";
        }
    }

    window.addEventListener("hashchange", () => {
        handleRoute(window.location.hash);
    });
    handleRoute(window.location.hash);

    // ─── 3. Sidebar Collapse & Drag-to-Resize ──────────────────────────────
    let isResizing = false;
    let lastWidth = parseInt(localStorage.getItem("sidebar-width")) || 260;
    let isCollapsed = localStorage.getItem("sidebar-collapsed") === "true";

    // Set initial width/collapse states
    if (sidebar && layout && toggleSidebarBtn) {
        if (isCollapsed) {
            sidebar.classList.add("collapsed");
            layout.style.setProperty("--sidebar-width", "60px");
            toggleSidebarBtn.textContent = "▶";
        } else {
            layout.style.setProperty("--sidebar-width", `${lastWidth}px`);
            toggleSidebarBtn.textContent = "◀";
        }
    }

    // Toggle collapse button click
    if (toggleSidebarBtn) {
        toggleSidebarBtn.addEventListener("click", () => {
            isCollapsed = !isCollapsed;
            localStorage.setItem("sidebar-collapsed", isCollapsed ? "true" : "false");
            
            if (isCollapsed) {
                if (sidebar) sidebar.classList.add("collapsed");
                if (layout) layout.style.setProperty("--sidebar-width", "60px");
                toggleSidebarBtn.textContent = "▶";
            } else {
                if (sidebar) sidebar.classList.remove("collapsed");
                if (layout) layout.style.setProperty("--sidebar-width", `${lastWidth}px`);
                toggleSidebarBtn.textContent = "◀";
            }
            
            // Trigger ECharts resize
            setTimeout(() => window.dispatchEvent(new Event("resize")), 350);
        });
    }

    // Mouse resize events
    if (resizer) {
        resizer.addEventListener("mousedown", (e) => {
            if (isCollapsed) return; // Prevent drag resizing if collapsed
            isResizing = true;
            resizer.classList.add("active");
            document.body.style.cursor = "col-resize";
            document.body.style.userSelect = "none";
        });
    }

    document.addEventListener("mousemove", (e) => {
        if (!isResizing) return;
        
        let newWidth = e.clientX;
        // Limit width range
        if (newWidth < 160) newWidth = 160;
        if (newWidth > 400) newWidth = 400;
        
        lastWidth = newWidth;
        if (layout) {
            layout.style.setProperty("--sidebar-width", `${newWidth}px`);
        }
        localStorage.setItem("sidebar-width", newWidth);
    });

    document.addEventListener("mouseup", () => {
        if (isResizing) {
            isResizing = false;
            if (resizer) resizer.classList.remove("active");
            document.body.style.cursor = "default";
            document.body.style.userSelect = "auto";
            
            // Trigger ECharts charts resizing on drag complete
            window.dispatchEvent(new Event("resize"));
        }
    });

    // ─── 4. Dual-Theme Management ──────────────────────────────────────────
    let currentTheme = localStorage.getItem("ui-theme") || "dark";
    let autoTimeEnabled = localStorage.getItem("ui-auto-theme") === "true";

    document.documentElement.setAttribute("data-theme", currentTheme);
    if (themeIconEl) themeIconEl.textContent = currentTheme === "dark" ? "🌙" : "☀️";
    if (autoTimeCheckbox) autoTimeCheckbox.checked = autoTimeEnabled;

    function setTheme(theme) {
        currentTheme = theme;
        document.documentElement.setAttribute("data-theme", theme);
        if (themeIconEl) themeIconEl.textContent = theme === "dark" ? "🌙" : "☀️";
        localStorage.setItem("ui-theme", theme);
        window.dispatchEvent(new CustomEvent("themechange", { detail: { theme } }));
    }

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener("click", () => {
            if (autoTimeEnabled) {
                autoTimeEnabled = false;
                if (autoTimeCheckbox) autoTimeCheckbox.checked = false;
                localStorage.setItem("ui-auto-theme", "false");
                alert("已关闭‘光感时间模式’，转为手动控制。");
            }
            setTheme(currentTheme === "dark" ? "solarized" : "dark");
        });
    }

    if (autoTimeCheckbox) {
        autoTimeCheckbox.addEventListener("change", (e) => {
            autoTimeEnabled = e.target.checked;
            localStorage.setItem("ui-auto-theme", autoTimeEnabled ? "true" : "false");
            if (autoTimeEnabled) checkTimeTheme();
        });
    }

    function checkTimeTheme() {
        if (!autoTimeEnabled) return;
        const hour = new Date().getHours();
        if (hour >= 8 && hour < 18) {
            if (currentTheme !== "solarized") setTheme("solarized");
        } else {
            if (currentTheme !== "dark") setTheme("dark");
        }
    }
    setInterval(checkTimeTheme, 30000);
    checkTimeTheme();

    // ─── 5. Dynamically Load categorized symbols ───────────────────────────
    async function loadSymbols() {
        try {
            console.log("Fetching /api/symbols...");
            const res = await fetch("/api/symbols");
            if (!res.ok) {
                alert("❌ /api/symbols 接口返回 HTTP " + res.status);
                return;
            }
            const data = await res.json();
            console.log("Symbols response:", data);
            if (data.status === "success" && data.data) {
                symbolData = data.data;
                populateSectors();
                populatePaperSymbols();
            } else {
                alert("⚠️ 获取品种数据失败: " + JSON.stringify(data));
            }
        } catch (e) {
            console.error("Error loading symbols:", e);
            alert("❌ 加载品种数据异常: " + e.message + "\nStack: " + e.stack);
        }
    }

    // Populate sector dropdowns
    function populateSectors() {
        // Clear sector selections
        if (btSectorsList) btSectorsList.innerHTML = '';
        optSectors.innerHTML = '<option value="">-- 请选择板块 --</option>';

        Object.keys(symbolData).forEach(sector => {
            const opt = document.createElement("option");
            opt.value = sector;
            opt.textContent = sector;
            
            optSectors.appendChild(opt);

            // Backtest checkbox logic
            if (btSectorsList) {
                const label = document.createElement("label");
                label.className = "checkbox-container";
                
                const cb = document.createElement("input");
                cb.type = "checkbox";
                cb.name = "bt-sector-checkbox";
                cb.value = sector;
                cb.addEventListener("change", handleBtSectorsChange);
                
                label.appendChild(cb);
                label.appendChild(document.createTextNode(` ${sector}`));
                btSectorsList.appendChild(label);
            }
        });
    }

    function handleBtSectorsChange() {
        const checkedSectors = Array.from(document.querySelectorAll('input[name="bt-sector-checkbox"]:checked')).map(cb => cb.value);
        
        btVarietiesList.innerHTML = '';
        btContractsList.innerHTML = '<span class="text-muted" style="font-size:12px;">请先选择品种...</span>';
        
        if (checkedSectors.length === 0) {
            btVarietiesList.innerHTML = '<span class="text-muted" style="font-size:12px;">请先选择板块...</span>';
            return;
        }

        checkedSectors.forEach(sector => {
            if (!symbolData[sector]) return;
            Object.keys(symbolData[sector]).forEach(variety => {
                const label = document.createElement("label");
                label.className = "checkbox-container";
                
                const cb = document.createElement("input");
                cb.type = "checkbox";
                cb.name = "bt-variety-checkbox";
                cb.dataset.sector = sector;
                cb.value = variety;
                cb.addEventListener("change", handleBtVarietiesChange);
                
                label.appendChild(cb);
                label.appendChild(document.createTextNode(` ${variety} (${sector})`));
                btVarietiesList.appendChild(label);
            });
        });
    }

    function handleBtVarietiesChange() {
        const checkedVarieties = Array.from(document.querySelectorAll('input[name="bt-variety-checkbox"]:checked'));
        
        btContractsList.innerHTML = '';
        
        if (checkedVarieties.length === 0) {
            btContractsList.innerHTML = '<span class="text-muted" style="font-size:12px;">请先选择品种...</span>';
            return;
        }

        checkedVarieties.forEach(cb => {
            const variety = cb.value;
            const sector = cb.dataset.sector;
            if (!symbolData[sector] || !symbolData[sector][variety]) return;
            
            symbolData[sector][variety].forEach(contract => {
                const label = document.createElement("label");
                label.className = "checkbox-container";
                
                const cbContract = document.createElement("input");
                cbContract.type = "checkbox";
                cbContract.name = "bt-contract-checkbox";
                cbContract.value = contract;
                cbContract.checked = contract.endsWith("88"); // Auto check main contracts
                
                label.appendChild(cbContract);
                label.appendChild(document.createTextNode(` ${contract}`));
                btContractsList.appendChild(label);
            });
        });
    }

    // Selected Contracts Management
    let selectedBacktestContracts = new Set();
    
    function renderSelectedContracts() {
        btSelectedList.innerHTML = '';
        if (selectedBacktestContracts.size === 0) {
            btSelectedList.innerHTML = '<span class="text-muted" style="font-size:12px; margin: auto;">暂无选择</span>';
            return;
        }

        selectedBacktestContracts.forEach(contract => {
            const badge = document.createElement("div");
            badge.style.display = "inline-flex";
            badge.style.alignItems = "center";
            badge.style.backgroundColor = "var(--primary-color)";
            badge.style.color = "white";
            badge.style.padding = "2px 8px";
            badge.style.borderRadius = "4px";
            badge.style.fontSize = "12px";
            
            const span = document.createElement("span");
            span.textContent = contract;
            
            const removeBtn = document.createElement("span");
            removeBtn.innerHTML = "×";
            removeBtn.style.marginLeft = "6px";
            removeBtn.style.cursor = "pointer";
            removeBtn.style.fontWeight = "bold";
            removeBtn.onclick = () => {
                selectedBacktestContracts.delete(contract);
                renderSelectedContracts();
            };
            
            badge.appendChild(span);
            badge.appendChild(removeBtn);
            btSelectedList.appendChild(badge);
        });
    }

    if (btnAddSelected) {
        btnAddSelected.addEventListener("click", () => {
            const checkedContracts = document.querySelectorAll('input[name="bt-contract-checkbox"]:checked');
            if (checkedContracts.length === 0) {
                alert("请先在上方勾选需要添加的合约");
                return;
            }
            checkedContracts.forEach(cb => {
                selectedBacktestContracts.add(cb.value);
            });
            renderSelectedContracts();
        });
    }

    if (btnClearSelected) {
        btnClearSelected.addEventListener("click", () => {
            selectedBacktestContracts.clear();
            renderSelectedContracts();
        });
    }

    // Populate paper trading order symbol dropdown with ALL contracts flatly
    function populatePaperSymbols() {
        paperOrderSymbol.innerHTML = "";
        Object.keys(symbolData).forEach(sector => {
            Object.keys(symbolData[sector]).forEach(variety => {
                symbolData[sector][variety].forEach(contract => {
                    const opt = document.createElement("option");
                    opt.value = contract;
                    opt.textContent = `${contract} (${variety})`;
                    paperOrderSymbol.appendChild(opt);
                });
            });
        });
    }

    // Handle Sector Change -> Variety List
    function handleSectorChange(sectorSelect, varietySelect, contractsList = null, singleSymbolSelect = null) {
        const sector = sectorSelect.value;
        varietySelect.innerHTML = '<option value="">-- 请选择品种 --</option>';
        varietySelect.disabled = !sector;
        
        if (contractsList) {
            contractsList.innerHTML = '<span class="text-muted" style="font-size:12px;">请先选择品种...</span>';
        }
        if (singleSymbolSelect) {
            singleSymbolSelect.innerHTML = '<option value="">-- 请选择合约 --</option>';
            singleSymbolSelect.disabled = true;
        }

        if (!sector || !symbolData[sector]) return;

        Object.keys(symbolData[sector]).forEach(variety => {
            const opt = document.createElement("option");
            opt.value = variety;
            opt.textContent = `${variety} (${sector})`;
            varietySelect.appendChild(opt);
        });
    }

    // Handle Variety Change -> Contracts List
    function handleVarietyChange(sectorSelect, varietySelect, contractsList, singleSymbolSelect = null) {
        const sector = sectorSelect.value;
        const variety = varietySelect.value;

        if (contractsList) {
            contractsList.innerHTML = "";
        }
        if (singleSymbolSelect) {
            singleSymbolSelect.innerHTML = '<option value="">-- 请选择合约 --</option>';
            singleSymbolSelect.disabled = !variety;
        }

        if (!sector || !variety || !symbolData[sector] || !symbolData[sector][variety]) return;

        const contracts = symbolData[sector][variety];
        
        if (contractsList) {
            contracts.forEach(contract => {
                const label = document.createElement("label");
                label.className = "checkbox-container";
                
                const cb = document.createElement("input");
                cb.type = "checkbox";
                cb.name = "backtest-contracts";
                cb.value = contract;
                cb.checked = contract.endsWith("88"); // Auto check main contracts by default
                
                label.appendChild(cb);
                label.appendChild(document.createTextNode(` ${contract}`));
                contractsList.appendChild(label);
            });
        }

        if (singleSymbolSelect) {
            contracts.forEach(contract => {
                const opt = document.createElement("option");
                opt.value = contract;
                opt.textContent = contract;
                singleSymbolSelect.appendChild(opt);
            });
        }
    }

    // Bind Backtester联动
    // Uses checkboxes now, event listeners attached in DOM generation

    // Bind Optimizer联动
    if (optSectors) {
        optSectors.addEventListener("change", () => {
            handleSectorChange(optSectors, optVarieties, null, optSymbol);
        });
    }
    if (optVarieties) {
        optVarieties.addEventListener("change", () => {
            handleVarietyChange(optSectors, optVarieties, null, optSymbol);
        });
    }

    // Note: loadSymbols() is called via loadSymbolsAndChart() at the end of this file.

    // ─── 6. Parameter Optimizer Mode Toggle ──────────────────────────────────
    if (optMode) {
        optMode.addEventListener("change", (e) => {
            const mode = e.target.value;
            if (mode === "param") {
                if (optBoxParam) optBoxParam.style.display = "block";
                if (optBoxInterval) optBoxInterval.style.display = "none";
                const optChartTitle = document.getElementById("opt-chart-title");
                if (optChartTitle) optChartTitle.textContent = "📊 寻优效果参数敏感度热力图 (Sharpe Ratio)";
                const optResultsTitle = document.getElementById("opt-results-title");
                if (optResultsTitle) optResultsTitle.textContent = "最优参数组合排行";
                const optTableHeader = document.getElementById("opt-table-header");
                if (optTableHeader) {
                    optTableHeader.innerHTML = `
                        <th>排名</th>
                        <th>参数组合 (Fast / Slow)</th>
                        <th>夏普比率 (Sharpe)</th>
                        <th>总收益率</th>
                        <th>最大回撤</th>
                    `;
                }
            } else {
                if (optBoxParam) optBoxParam.style.display = "none";
                if (optBoxInterval) optBoxInterval.style.display = "block";
                const optChartTitle = document.getElementById("opt-chart-title");
                if (optChartTitle) optChartTitle.textContent = "📊 各 K 线周期寻优表现对比 (Sharpe Ratio)";
                const optResultsTitle = document.getElementById("opt-results-title");
                if (optResultsTitle) optResultsTitle.textContent = "最优 K 线交易周期排行";
                const optTableHeader = document.getElementById("opt-table-header");
                if (optTableHeader) {
                    optTableHeader.innerHTML = `
                        <th>排名</th>
                        <th>K 线周期</th>
                        <th>夏普比率 (Sharpe)</th>
                        <th>总收益率</th>
                        <th>最大回撤</th>
                    `;
                }
            }
        });
    }

    // ─── 7. Database Sync Cloud Button click ───────────────────────────────
    if (btnSyncDb) {
        btnSyncDb.addEventListener("click", async () => {
            if (btnSyncDb.classList.contains("syncing")) return;
            
            btnSyncDb.classList.add("syncing");
            const syncText = btnSyncDb.querySelector(".sync-text");
            if (syncText) syncText.textContent = "正在同步主数据...";
    
            try {
                const res = await fetch("/api/db/sync", { method: "POST" });
                const data = await res.json();
                if (data.status === "success") {
                    alert("✅ 主数据同步更新成功！已经更新最新日线与分钟K线。");
                } else {
                    alert("❌ 同步失败: " + data.message);
                }
            } catch (e) {
                alert("❌ 请求错误，无法连接同步服务。");
            } finally {
                btnSyncDb.classList.remove("syncing");
                if (syncText) syncText.textContent = "同步主数据库";
            }
        });
    }

    // ─── 8. Paper Trading UI Interaction Stubs ────────────────────────────
    if (btnPaperSubmit) {
        btnPaperSubmit.addEventListener("click", () => {
            const symbol = paperOrderSymbol ? paperOrderSymbol.value : "";
            const dirEl = document.getElementById("paper-order-dir");
            const offsetEl = document.getElementById("paper-order-offset");
            const priceEl = document.getElementById("paper-order-price");
            const volEl = document.getElementById("paper-order-volume");
            
            const dir = dirEl ? dirEl.value : "";
            const offset = offsetEl ? offsetEl.value : "";
            const price = priceEl ? priceEl.value : "";
            const vol = volEl ? volEl.value : "";
    
            alert(`⚡ 虚拟委托已发送到模拟盘交易网关！\n合约: ${symbol}\n方向: ${dir} | ${offset}\n价格: ${price} | 数量: ${vol}手`);
        });
    }

    if (btnPaperRefresh) {
        btnPaperRefresh.addEventListener("click", () => {
            alert("🔄 模拟持仓数据刷新成功！");
        });
    }

    console.log("Moderixest Trade Dashboard Initialized!");

    // ─── 9. K-Line Chart Board ────────────────────────────────────────────
    const chartSectors = document.getElementById("chart-sectors");
    const chartVarieties = document.getElementById("chart-varieties");
    const chartContract = document.getElementById("chart-contract");
    const chartIntervalGroup = document.getElementById("chart-interval-group");
    const chartStart = document.getElementById("chart-start");
    const chartEnd = document.getElementById("chart-end");
    const btnLoadChart = document.getElementById("btn-load-chart");
    const chartStatus = document.getElementById("chart-status");
    const chartMainTitle = document.getElementById("chart-main-title");
    const chartSubTitle = document.getElementById("chart-sub-title");
    const chartSubPanel = document.getElementById("chart-sub-panel");
    const btnChartZoomReset = document.getElementById("btn-chart-zoom-reset");

    // Set today's date as default end
    if (chartEnd) chartEnd.value = new Date().toISOString().split("T")[0];

    let selectedInterval = "1d";
    let chartMainInstance = null;
    let chartSubInstance = null;
    let currentChartBars = null;

    // Track current exchange for selected variety
    let chartCurrentExchange = "";

    // ── Populate chart sector dropdown ──────────────────────────────────────
    function populateChartSectors() {
        if (!chartSectors) {
            alert("❌ 找不到 id='chart-sectors' 的元素！");
            return;
        }
        chartSectors.innerHTML = '<option value="">-- 请选择板块 --</option>';
        const keys = Object.keys(symbolData);
        console.log("Populating chart sectors, keys:", keys);
        if (keys.length === 0) {
            alert("⚠️ Warning: symbolData 数据为空，无法填充K线板块下拉框！");
            return;
        }
        keys.forEach(sector => {
            const opt = document.createElement("option");
            opt.value = sector;
            opt.textContent = sector;
            chartSectors.appendChild(opt);
        });
    }

    // ── Sector -> Variety ────────────────────────────────────────────────────
    if (chartSectors) {
        chartSectors.addEventListener("change", () => {
            const sector = chartSectors.value;
            chartVarieties.innerHTML = '<option value="">-- 请先选择品种 --</option>';
            chartVarieties.disabled = !sector;
            chartContract.innerHTML = '<option value="">-- 请先选择品种 --</option>';
            chartContract.disabled = true;
            chartCurrentExchange = "";

            if (!sector || !symbolData[sector]) return;

            Object.keys(symbolData[sector]).forEach(variety => {
                const opt = document.createElement("option");
                opt.value = variety;
                opt.textContent = variety;
                chartVarieties.appendChild(opt);
            });
        });
    }

    // ── Variety -> Contract ──────────────────────────────────────────────────
    if (chartVarieties) {
        chartVarieties.addEventListener("change", () => {
            const sector = chartSectors.value;
            const variety = chartVarieties.value;
            chartContract.innerHTML = '<option value="">-- 请选择合约 --</option>';
            chartContract.disabled = !variety;
            chartCurrentExchange = "";

            if (!sector || !variety || !symbolData[sector] || !symbolData[sector][variety]) return;

            const contracts = symbolData[sector][variety];
            contracts.forEach(contract => {
                const opt = document.createElement("option");
                opt.value = contract;
                opt.textContent = contract;
                // Auto-select 88 (continuous) contract
                if (contract.endsWith("88")) opt.selected = true;
                chartContract.appendChild(opt);
            });

            // Determine exchange from variety key e.g. "白银 (AG)" -> look up in config
            // We'll get exchange via the /api/kline/varieties call
            loadChartExchange(sector, variety);
        });
    }

    // Store exchange map from varieties API
    let varietyExchangeMap = {};

    async function loadVarietyExchanges() {
        try {
            const res = await fetch("/api/kline/varieties");
            const data = await res.json();
            if (data.status === "success") {
                data.data.forEach(v => {
                    varietyExchangeMap[`${v.name} (${v.code})`] = v.exchange;
                });
            }
        } catch (e) {
            console.warn("Could not load variety exchanges:", e);
        }
    }

    function loadChartExchange(sector, variety) {
        chartCurrentExchange = varietyExchangeMap[variety] || "";
    }

    // ── Interval toggle ──────────────────────────────────────────────────────
    if (chartIntervalGroup) {
        chartIntervalGroup.querySelectorAll(".interval-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                chartIntervalGroup.querySelectorAll(".interval-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                selectedInterval = btn.dataset.interval;
            });
        });
    }

    // ── Technical Indicator Computation ─────────────────────────────────────
    function calcMA(closes, period) {
        return closes.map((_, i) => {
            if (i < period - 1) return null;
            const slice = closes.slice(i - period + 1, i + 1);
            return +(slice.reduce((a, b) => a + b, 0) / period).toFixed(4);
        });
    }

    function calcEMA(closes, period) {
        const k = 2 / (period + 1);
        const result = [];
        closes.forEach((c, i) => {
            if (i === 0) { result.push(c); return; }
            result.push(+(result[i - 1] * (1 - k) + c * k).toFixed(4));
        });
        // Fill null for first period-1 bars
        return result.map((v, i) => i < period - 1 ? null : v);
    }

    function calcBOLL(closes, period = 20, mult = 2) {
        const mid = calcMA(closes, period);
        const upper = [], lower = [];
        closes.forEach((_, i) => {
            if (i < period - 1) { upper.push(null); lower.push(null); return; }
            const slice = closes.slice(i - period + 1, i + 1);
            const mean = slice.reduce((a, b) => a + b, 0) / period;
            const sd = Math.sqrt(slice.reduce((a, b) => a + (b - mean) ** 2, 0) / period);
            upper.push(+(mean + mult * sd).toFixed(4));
            lower.push(+(mean - mult * sd).toFixed(4));
        });
        return { mid, upper, lower };
    }

    function calcMACD(closes, fast = 12, slow = 26, signal = 9) {
        const emaFast = calcEMA(closes, fast);
        const emaSlow = calcEMA(closes, slow);
        const dif = emaFast.map((f, i) => (f === null || emaSlow[i] === null) ? null : +(f - emaSlow[i]).toFixed(4));
        // DEA: EMA of DIF
        const dea = [];
        dif.forEach((d, i) => {
            if (d === null) { dea.push(null); return; }
            const prev = dea[i - 1];
            if (prev === null || prev === undefined) { dea.push(d); return; }
            dea.push(+(prev * (signal - 1) / (signal + 1) + d * 2 / (signal + 1)).toFixed(4));
        });
        const macd = dif.map((d, i) => (d === null || dea[i] === null) ? null : +((d - dea[i]) * 2).toFixed(4));
        return { dif, dea, macd };
    }

    function calcRSI(closes, period = 14) {
        const rsi = new Array(closes.length).fill(null);
        if (closes.length < period + 1) return rsi;
        let gains = 0, losses = 0;
        for (let i = 1; i <= period; i++) {
            const diff = closes[i] - closes[i - 1];
            if (diff >= 0) gains += diff; else losses -= diff;
        }
        let avgGain = gains / period, avgLoss = losses / period;
        rsi[period] = avgLoss === 0 ? 100 : +(100 - 100 / (1 + avgGain / avgLoss)).toFixed(2);
        for (let i = period + 1; i < closes.length; i++) {
            const diff = closes[i] - closes[i - 1];
            avgGain = (avgGain * (period - 1) + Math.max(diff, 0)) / period;
            avgLoss = (avgLoss * (period - 1) + Math.max(-diff, 0)) / period;
            rsi[i] = avgLoss === 0 ? 100 : +(100 - 100 / (1 + avgGain / avgLoss)).toFixed(2);
        }
        return rsi;
    }

    function calcKDJ(highs, lows, closes, period = 9) {
        const k = [], d = [], j = [];
        for (let i = 0; i < closes.length; i++) {
            if (i < period - 1) { k.push(null); d.push(null); j.push(null); continue; }
            const highSlice = highs.slice(i - period + 1, i + 1);
            const lowSlice = lows.slice(i - period + 1, i + 1);
            const highN = Math.max(...highSlice), lowN = Math.min(...lowSlice);
            const rsv = highN === lowN ? 50 : ((closes[i] - lowN) / (highN - lowN)) * 100;
            const prevK = k[i - 1] ?? 50, prevD = d[i - 1] ?? 50;
            const kv = +(prevK * 2 / 3 + rsv / 3).toFixed(2);
            const dv = +(prevD * 2 / 3 + kv / 3).toFixed(2);
            k.push(kv); d.push(dv); j.push(+(3 * kv - 2 * dv).toFixed(2));
        }
        return { k, d, j };
    }

    // ── Load and render K-line chart ─────────────────────────────────────────
    async function loadKlineChart() {
        const symbol = chartContract.value;
        if (!symbol) { chartStatus.textContent = "❌ 请先选择合约"; return; }

        // Determine exchange
        let exchange = chartCurrentExchange;
        if (!exchange) {
            // Fallback: try to find from symbolData
            const sector = chartSectors.value;
            const variety = chartVarieties.value;
            exchange = varietyExchangeMap[variety] || "SHF";
        }

        const start = chartStart.value;
        const end = chartEnd.value;
        const limit = 20000;

        chartStatus.textContent = "⏳ 正在拉取K线数据...";
        btnLoadChart.disabled = true;

        try {
            const url = `/api/kline?symbol=${symbol}&exchange=${exchange}&interval=${selectedInterval}&start=${start}&end=${end}&limit=${limit}`;
            const res = await fetch(url);
            const data = await res.json();

            if (data.status !== "success" || !data.data.length) {
                chartStatus.textContent = `❌ 无数据：${data.detail || "该合约/周期在数据库无记录"}`;
                return;
            }

            chartStatus.textContent = `✅ 已加载 ${data.count} 根K线 (${symbol} · ${selectedInterval})`;
            chartMainTitle.textContent = `🕯️ ${symbol} ${selectedInterval} K线图 (${data.count}根)`;

            currentChartBars = data.data;
            renderKlineChart(data.data);

        } catch (e) {
            chartStatus.textContent = `❌ 请求失败：${e.message}`;
        } finally {
            btnLoadChart.disabled = false;
        }
    }

    function renderKlineChart(bars) {
        const times = bars.map(b => b.t);
        const ohlc = bars.map(b => [b.o, b.c, b.l, b.h]);
        const closes = bars.map(b => b.c);
        const highs = bars.map(b => b.h);
        const lows = bars.map(b => b.l);
        const volumes = bars.map(b => b.v);

        // Get selected main indicators
        const mainIndicators = Object.keys(mainIndicatorConfigs).filter(k => mainIndicatorConfigs[k].active);
        const subIndicators = Object.keys(subIndicatorConfigs).filter(k => subIndicatorConfigs[k].active);

        // ── Main Chart Series ────────────────────────────────────────────────
        const mainSeries = [{
            name: "K线",
            type: "candlestick",
            data: ohlc,
            itemStyle: {
                color: "var(--color-success)",
                color0: "var(--color-danger)",
                borderColor: "var(--color-success)",
                borderColor0: "var(--color-danger)"
            }
        }];

        if (mainIndicators.includes("MA")) {
            const maFast = mainIndicatorConfigs.MA.params.fast;
            const maSlow = mainIndicatorConfigs.MA.params.slow;
            mainSeries.push({ name: `MA${maFast}`, type: "line", data: calcMA(closes, maFast), smooth: true, lineStyle: { width: 1.5, color: "#ff9f0a" }, showSymbol: false });
            mainSeries.push({ name: `MA${maSlow}`, type: "line", data: calcMA(closes, maSlow), smooth: true, lineStyle: { width: 1.5, color: "#007aff" }, showSymbol: false });
        }
        if (mainIndicators.includes("EMA")) {
            const emaPeriod = mainIndicatorConfigs.EMA.params.period;
            mainSeries.push({ name: `EMA${emaPeriod}`, type: "line", data: calcEMA(closes, emaPeriod), smooth: true, lineStyle: { width: 1.5, color: "#bf5af2", type: "dashed" }, showSymbol: false });
        }
        if (mainIndicators.includes("BOLL")) {
            const bollPeriod = mainIndicatorConfigs.BOLL.params.period;
            const bollStd = mainIndicatorConfigs.BOLL.params.std;
            const boll = calcBOLL(closes, bollPeriod, bollStd);
            mainSeries.push({ name: "BOLL上轨", type: "line", data: boll.upper, smooth: true, lineStyle: { width: 1, color: "#5ac8fa", type: "dashed" }, showSymbol: false });
            mainSeries.push({ name: "BOLL中轨", type: "line", data: boll.mid, smooth: true, lineStyle: { width: 1, color: "#5ac8fa" }, showSymbol: false });
            mainSeries.push({ name: "BOLL下轨", type: "line", data: boll.lower, smooth: true, lineStyle: { width: 1, color: "#5ac8fa", type: "dashed" }, showSymbol: false });
        }

        // ── Sub Chart Series ─────────────────────────────────────────────────
        const subSeries = [];
        const subLegend = [];
        let subTitle = "";

        if (subIndicators.includes("MACD")) {
            const mFast = subIndicatorConfigs.MACD.params.fast;
            const mSlow = subIndicatorConfigs.MACD.params.slow;
            const mSignal = subIndicatorConfigs.MACD.params.signal;
            const { dif, dea, macd } = calcMACD(closes, mFast, mSlow, mSignal);
            subSeries.push({ name: "DIF", type: "line", data: dif, showSymbol: false, lineStyle: { width: 1.5, color: "#007aff" } });
            subSeries.push({ name: "DEA", type: "line", data: dea, showSymbol: false, lineStyle: { width: 1.5, color: "#ff9f0a" } });
            subSeries.push({
                name: "MACD",
                type: "bar",
                data: macd,
                itemStyle: {
                    color: params => params.data >= 0 ? "var(--color-success)" : "var(--color-danger)"
                }
            });
            subLegend.push("DIF", "DEA", "MACD");
            subTitle = `MACD (${mFast},${mSlow},${mSignal})`;
        } else if (subIndicators.includes("RSI")) {
            const rsiPeriod = subIndicatorConfigs.RSI.params.period;
            const rsi = calcRSI(closes, rsiPeriod);
            subSeries.push({ name: `RSI${rsiPeriod}`, type: "line", data: rsi, showSymbol: false, lineStyle: { color: "#bf5af2", width: 1.5 } });
            subSeries.push({ name: "超买线", type: "line", data: new Array(bars.length).fill(70), showSymbol: false, lineStyle: { color: "#ff453a", width: 1, type: "dashed" } });
            subSeries.push({ name: "超卖线", type: "line", data: new Array(bars.length).fill(30), showSymbol: false, lineStyle: { color: "#30d158", width: 1, type: "dashed" } });
            subLegend.push(`RSI${rsiPeriod}`);
            subTitle = `RSI (${rsiPeriod})`;
        } else if (subIndicators.includes("KDJ")) {
            const kdjPeriod = subIndicatorConfigs.KDJ.params.period;
            const { k, d, j } = calcKDJ(highs, lows, closes, kdjPeriod);
            subSeries.push({ name: "K", type: "line", data: k, showSymbol: false, lineStyle: { color: "#007aff", width: 1.5 } });
            subSeries.push({ name: "D", type: "line", data: d, showSymbol: false, lineStyle: { color: "#ff9f0a", width: 1.5 } });
            subSeries.push({ name: "J", type: "line", data: j, showSymbol: false, lineStyle: { color: "#bf5af2", width: 1.5 } });
            subLegend.push("K", "D", "J");
            subTitle = `KDJ (${kdjPeriod},3,3)`;
        } else if (subIndicators.includes("VOL")) {
            subSeries.push({
                name: "成交量",
                type: "bar",
                data: volumes,
                itemStyle: {
                    color: params => ohlc[params.dataIndex][1] >= ohlc[params.dataIndex][0] ? "var(--color-success)" : "var(--color-danger)"
                }
            });
            subTitle = "成交量";
        }

        if (chartSubTitle) chartSubTitle.textContent = subTitle || "副图指标";

        // ── Init / Update ECharts Main ───────────────────────────────────────
        if (chartMainInstance) {
            chartMainInstance.dispose();
            chartMainInstance = null;
        }
        const mainDom = document.getElementById("chart-kline-main");
        mainDom.innerHTML = ""; // Clear placeholder
        chartMainInstance = echarts.init(mainDom, document.documentElement.getAttribute("data-theme") === "solarized" ? null : "dark");

        const isDark = document.documentElement.getAttribute("data-theme") !== "solarized";
        const gridBg = isDark ? "#1c1c1e" : "#f5eedb";
        const textColor = isDark ? "#f2f2f7" : "#586e75";
        const borderColor = isDark ? "#2c2c2e" : "#d3c7a3";

        chartMainInstance.setOption({
            backgroundColor: "transparent",
            animation: false,
            tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
            legend: { data: mainSeries.map(s => s.name).filter(n => n !== "K线"), textStyle: { color: textColor }, top: 8 },
            grid: { left: "10%", right: "4%", top: 60, bottom: 80 },
            xAxis: { type: "category", data: times, boundaryGap: true, splitLine: { show: false }, axisLabel: { color: textColor } },
            yAxis: { type: "value", scale: true, splitLine: { lineStyle: { color: borderColor } }, axisLabel: { color: textColor } },
            dataZoom: [
                { type: "inside", start: Math.max(0, 100 - Math.round(500 / bars.length * 100)), end: 100 },
                { type: "slider", start: Math.max(0, 100 - Math.round(500 / bars.length * 100)), end: 100, height: 30, bottom: 10 }
            ],
            series: mainSeries
        });

        // ── Sub Chart ────────────────────────────────────────────────────────
        if (subSeries.length > 0) {
            chartSubPanel.style.display = "block";
            if (chartSubInstance) {
                chartSubInstance.dispose();
                chartSubInstance = null;
            }
            const subDom = document.getElementById("chart-kline-sub");
            subDom.innerHTML = "";
            chartSubInstance = echarts.init(subDom, isDark ? "dark" : null);

            chartSubInstance.setOption({
                backgroundColor: "transparent",
                animation: false,
                tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
                legend: { data: subLegend, textStyle: { color: textColor }, top: 4 },
                grid: { left: "10%", right: "4%", top: 40, bottom: 40 },
                xAxis: { type: "category", data: times, boundaryGap: subSeries[0]?.type === "bar", splitLine: { show: false }, axisLabel: { color: textColor } },
                yAxis: { type: "value", scale: true, splitLine: { lineStyle: { color: borderColor } }, axisLabel: { color: textColor } },
                dataZoom: [{ type: "inside", start: Math.max(0, 100 - Math.round(500 / bars.length * 100)), end: 100 }],
                series: subSeries
            });

            // Sync zoom between main and sub chart
            echarts.connect([chartMainInstance, chartSubInstance]);
        } else {
            chartSubPanel.style.display = "none";
            if (chartSubInstance) { chartSubInstance.dispose(); chartSubInstance = null; }
        }
    }

    if (btnLoadChart) {
        btnLoadChart.addEventListener("click", loadKlineChart);
    }

    if (btnChartZoomReset) {
        btnChartZoomReset.addEventListener("click", () => {
            chartMainInstance?.dispatchAction({ type: "dataZoom", start: 0, end: 100 });
            chartSubInstance?.dispatchAction({ type: "dataZoom", start: 0, end: 100 });
        });
    }

    // Global chart event listeners (registered once)
    window.addEventListener("resize", () => {
        chartMainInstance?.resize();
        chartSubInstance?.resize();
        chartEquityInstance?.resize();
    });
    window.addEventListener("themechange", () => {
        setTimeout(() => {
            if (chartMainInstance) { chartMainInstance.dispose(); chartMainInstance = null; }
            if (chartSubInstance) { chartSubInstance.dispose(); chartSubInstance = null; }
            if (currentChartBars) {
                renderKlineChart(currentChartBars);
            }
            if (currentEquitySeries) {
                renderEquityChart(currentEquitySeries);
            }
        }, 100);
    });

    // Hook into loadSymbols to also populate chart selectors
    // Variables declared at the top level

    function renderEquityChart(equitySeries) {
        currentEquitySeries = equitySeries;
        const dom = document.getElementById("chart-equity");
        if (!dom) return;
        
        if (chartEquityInstance) {
            chartEquityInstance.dispose();
            chartEquityInstance = null;
        }
        
        dom.innerHTML = ""; 
        
        const isDark = document.documentElement.getAttribute("data-theme") !== "solarized";
        chartEquityInstance = echarts.init(dom, isDark ? "dark" : null);

        const dates = equitySeries.map(x => x.date);
        const equities = equitySeries.map(x => x.equity);
        const drawdowns = equitySeries.map(x => x.drawdown * 100); 

        const textColor = isDark ? "#f2f2f7" : "#586e75";
        const borderColor = isDark ? "#2c2c2e" : "#d3c7a3";

        chartEquityInstance.setOption({
            backgroundColor: "transparent",
            tooltip: {
                trigger: "axis",
                axisPointer: { type: "cross" }
            },
            legend: {
                data: ["组合总净值", "回撤幅度 (%)"],
                textStyle: { color: textColor },
                top: 8
            },
            grid: {
                left: "8%",
                right: "8%",
                top: 50,
                bottom: 50
            },
            xAxis: {
                type: "category",
                data: dates,
                axisLabel: { color: textColor }
            },
            yAxis: [
                {
                    type: "value",
                    name: "总资产净值",
                    scale: true,
                    axisLabel: { color: textColor },
                    splitLine: { lineStyle: { color: borderColor } }
                },
                {
                    type: "value",
                    name: "回撤百分比 (%)",
                    max: 0,
                    axisLabel: { color: textColor },
                    splitLine: { show: false }
                }
            ],
            series: [
                {
                    name: "组合总净值",
                    type: "line",
                    data: equities,
                    smooth: true,
                    lineStyle: { width: 2, color: "#ff9f0a" },
                    showSymbol: false
                },
                {
                    name: "回撤幅度 (%)",
                    type: "line",
                    yAxisIndex: 1,
                    data: drawdowns,
                    smooth: true,
                    areaStyle: {
                        color: "rgba(255, 69, 58, 0.15)"
                    },
                    lineStyle: { width: 1, color: "#ff453a" },
                    showSymbol: false
                }
            ]
        });
    }

    const btnRunBacktest = document.getElementById("btn-run-backtest");
    if (btnRunBacktest) {
        btnRunBacktest.addEventListener("click", async () => {
            if (selectedBacktestContracts.size === 0) {
                alert("请先在列表中添加需要复盘的品种");
                return;
            }
            
            const startDate = document.getElementById("backtest-start").value;
            const endDate = document.getElementById("backtest-end").value;
            const paramFast = document.getElementById("param-fast").value;
            const paramSlow = document.getElementById("param-slow").value;
            const capital = document.getElementById("param-capital").value;
            const margin = document.getElementById("param-margin").value;
            const commission = document.getElementById("param-commission").value;
            
            btnRunBacktest.disabled = true;
            btnRunBacktest.innerHTML = '<span class="btn-text">⏳ 正在执行...</span>';
            
            try {
                const res = await fetch("/api/backtest", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        symbols: Array.from(selectedBacktestContracts),
                        start: startDate,
                        end: endDate,
                        params: {
                            fast_window: parseInt(paramFast),
                            slow_window: parseInt(paramSlow)
                        },
                        capital: parseFloat(capital),
                        margin_rate: parseFloat(margin) / 100,
                        commission_rate: parseFloat(commission) / 10000
                    })
                });
                
                const data = await res.json();
                if (data.status === "success") {
                    const summary = data.data;
                    document.getElementById("metric-total-return").textContent = (summary.total_return * 100).toFixed(2) + "%";
                    document.getElementById("metric-sharpe").textContent = summary.sharpe_ratio.toFixed(2);
                    
                    const mDrawdown = document.getElementById("metric-drawdown");
                    mDrawdown.textContent = (summary.max_drawdown * 100).toFixed(2) + "%";
                    
                    document.getElementById("metric-margin-win").textContent = (summary.win_rate * 100).toFixed(2) + "%";

                    renderEquityChart(summary.equity_series);
                } else {
                    alert("回测失败: " + (data.detail || data.message));
                }
            } catch (e) {
                console.error("Backtest Error:", e);
                alert("网络或系统异常");
            } finally {
                btnRunBacktest.disabled = false;
                btnRunBacktest.innerHTML = '<span class="btn-text">🚀 运行回测 / 组合回测</span>';
            }
        });
    }

    const origLoadSymbols = loadSymbols;
    async function loadSymbolsAndChart() {
        await origLoadSymbols();
        populateChartSectors();
        await loadVarietyExchanges();
        
        // Initialize indicator dropdowns
        renderIndicatorDropdowns();
        updateDropdownLabels();
    }
    // Replace loadSymbols call with extended version
    loadSymbolsAndChart();
});


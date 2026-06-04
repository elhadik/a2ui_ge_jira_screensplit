# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import logging

logger = logging.getLogger(__name__)

class UIBuilderV08:
    # Inlined clean HTML template to guarantee Vertex AI container deployment correctness
    DASHBOARD_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <meta content="connect-src 'none'" http-equiv="Content-Security-Policy">
    <title>Store Invoice Auditing Dashboard</title>
    
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-primary: #38bdf8;
            --accent-secondary: #818cf8;
            --border-color: #334155;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }
        body {
            font-family: system-ui, -apple-system, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            margin: 0;
            padding: 12px;
            box-sizing: border-box;
            font-size: 13px;
        }
        .dashboard-header {
            margin-bottom: 12px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .dashboard-header h1 {
            font-size: 1.1rem;
            font-weight: 700;
            margin: 0;
            background: linear-gradient(to right, var(--accent-primary), var(--accent-secondary));
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .dashboard-header p {
            color: var(--text-secondary);
            margin: 2px 0 0 0;
            font-size: 0.75rem;
        }
        .kpi-container {
            display: flex;
            gap: 8px;
            margin-bottom: 12px;
        }
        .kpi-card {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 8px 10px;
            flex: 1;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .kpi-card.success { border-left: 3px solid var(--success); }
        .kpi-card.warning { border-left: 3px solid var(--warning); }
        .kpi-card.danger { border-left: 3px solid var(--danger); }
        .kpi-title { font-size: 0.62rem; text-transform: uppercase; color: var(--text-secondary); letter-spacing: 0.05em; }
        .kpi-value { font-size: 1.05rem; font-weight: 700; margin: 2px 0; }
        .kpi-sub { font-size: 0.68rem; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        
        .grid-layout {
            display: grid;
            grid-template-columns: 1.2fr 1fr;
            gap: 12px;
        }
        @media (max-width: 640px) {
            .grid-layout {
                grid-template-columns: 1fr;
            }
        }
        .panel {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .panel-header {
            margin-bottom: 8px;
            font-weight: 700;
            color: var(--text-secondary);
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .table-container {
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }
        th {
            font-weight: 600;
            color: var(--text-secondary);
            border-bottom: 2px solid var(--border-color);
            font-size: 0.72rem;
            text-transform: uppercase;
        }
        th, td { padding: 6px 4px; }
        tr { border-bottom: 1px solid var(--border-color); }
        tr:last-child { border-bottom: none; }
        
        .slider-container {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: 8px;
        }
        .slider-group {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 6px 8px;
        }
        .slider-header {
            display: flex;
            justify-content: space-between;
            font-size: 0.72rem;
            margin-bottom: 2px;
            font-weight: 600;
        }
        .slider-label { color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 130px; }
        .slider-value { color: var(--accent-primary); font-weight: 700; }
        .slider-input { width: 100%; height: 4px; border-radius: 2px; background: var(--border-color); cursor: pointer; }

        .chart-container {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: 4px;
            margin-bottom: 12px;
            overflow-y: auto;
            max-height: 130px;
        }
        .chart-row {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .chart-label {
            width: 75px;
            color: var(--text-secondary);
            font-size: 0.68rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .chart-bar-wrapper {
            flex: 1;
            background: var(--border-color);
            height: 10px;
            border-radius: 3px;
            overflow: hidden;
            position: relative;
        }
        .chart-bar {
            height: 100%;
            background: linear-gradient(to right, var(--accent-primary), var(--accent-secondary));
            border-radius: 3px;
            transition: width 0.2s ease-in-out;
            width: 0%;
        }
        .chart-value {
            width: 55px;
            text-align: right;
            font-weight: 700;
            color: var(--accent-primary);
            font-size: 0.7rem;
        }

        .status-bar {
            background: rgba(16, 185, 129, 0.08);
            border: 1px solid rgba(16, 185, 129, 0.2);
            border-radius: 8px;
            padding: 10px;
            margin-top: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.2s ease-in-out;
        }
        .status-bar.override {
            background: rgba(239, 68, 68, 0.08);
            border: 1px solid rgba(239, 68, 68, 0.2);
        }
        .status-title { font-weight: 700; color: var(--success); font-size: 0.8rem; }
        .status-title.override { color: var(--danger); }
        .status-desc { font-size: 0.72rem; color: var(--text-secondary); }

        .badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.65rem;
            font-weight: 700;
            text-transform: uppercase;
        }
        .badge.success { background: rgba(16, 185, 129, 0.12); color: var(--success); }
        .badge.warning { background: rgba(245, 158, 11, 0.12); color: var(--warning); }
        .badge.danger { background: rgba(239, 68, 68, 0.12); color: var(--danger); }
    </style>
</head>
<body>
    <div class='dashboard-header'>
        <div>
            <h1 id='db-title'>Invoice Audit Dashboard</h1>
            <p id='db-subtitle'>Multi-Agent OCR & Compliance Diagnostics</p>
        </div>
        <div id='header-badge'>
            <!-- Merchant name badge -->
        </div>
    </div>

    <div class='kpi-container' id='kpi-container'>
        <!-- Dynamic KPIs -->
    </div>

    <div class='grid-layout'>
        <!-- Left Column: Table & Pie Chart -->
        <div style='display: flex; flex-direction: column; gap: 12px;'>
            <!-- Extracted Data Table -->
            <div class='panel'>
                <div class='panel-header'>
                    <span>Extracted Line Items</span>
                    <div style='display: flex; gap: 8px; align-items: center;'>
                        <button id='copy-csv-btn' onclick='copyItemsToCSV()' style='background: var(--border-color); border: 1px solid var(--border-color); color: var(--text-primary); border-radius: 4px; padding: 2px 6px; font-size: 0.65rem; cursor: pointer; transition: all 0.2s;'>📋 Copy CSV</button>
                        <span id='table-total' style='color: var(--accent-primary);'>Total: $0.00</span>
                    </div>
                </div>
                <div class='table-container'>
                    <table id='items-table'>
                        <thead>
                            <tr>
                                <th>Item</th>
                                <th style='text-align: center; width: 40px;'>Qty</th>
                                <th style='text-align: right; width: 60px;'>Price</th>
                                <th style='text-align: right; width: 70px;'>Amount</th>
                            </tr>
                        </thead>
                        <tbody id='table-body'>
                            <!-- Table rows -->
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Standalone Expense Share (Pie Chart) Panel -->
            <div class='panel'>
                <div class='panel-header'>Expense Share (Distribution)</div>
                <div style='display: flex; align-items: center; justify-content: center; gap: 16px; margin: 8px 0 4px 0;'>
                    <svg id='pie-chart' width='105' height='105' viewBox='0 0 140 140' style='transform: rotate(-90deg); border-radius: 50%; background: transparent; min-width: 105px;'></svg>
                    <div id='pie-legend' style='display: flex; flex-direction: column; gap: 4px; font-size: 0.68rem; max-height: 105px; overflow-y: auto; flex: 1;'></div>
                </div>
            </div>
        </div>

        <!-- Right Column: Interactive Adjuster & Live Chart -->
        <div style='display: flex; flex-direction: column; gap: 12px;'>
            <div class='panel' style='height: 100%; box-sizing: border-box;'>
                <div class='panel-header' style='display: flex; justify-content: space-between; align-items: center;'>
                    <span>Expense Adjuster & Live Chart</span>
                    <button id='reset-btn' onclick='resetPrices()' style='background: var(--border-color); border: 1px solid var(--border-color); color: var(--text-secondary); border-radius: 4px; padding: 2px 6px; font-size: 0.65rem; cursor: pointer; display: none; transition: all 0.2s;'>↺ Reset</button>
                </div>
                
                <div class='chart-container' id='live-chart-container'>
                    <!-- Dynamic CSS bar chart -->
                </div>

                <div class='slider-container' id='sliders-list'>
                    <!-- Interactive price sliders -->
                </div>
            </div>
        </div>

        <!-- Bottom Panel: Visual Analytics (Pivot only) -->
        <div class='panel' style='grid-column: span 2;'>
            <div class='panel-header'>Visual Analytics Breakdown</div>
            <div style='margin-top: 8px;'>
                <!-- Pivot Breakdown Table and Chart -->
                <div style='font-weight: 600; font-size: 0.75rem; margin-bottom: 6px; color: var(--text-secondary);'>Pivot Summary & Category Chart</div>
                <div style='display: flex; gap: 16px; align-items: flex-start;'>
                    <table style='flex: 1.5; border-collapse: collapse;'>
                        <thead>
                            <tr style='border-bottom: 1px solid var(--border-color); text-align: left;'>
                                <th style='font-size: 0.68rem; padding: 4px; color: var(--text-secondary);'>Category / Group</th>
                                <th style='font-size: 0.68rem; padding: 4px; text-align: center; color: var(--text-secondary);'>Qty</th>
                                <th style='font-size: 0.68rem; padding: 4px; text-align: right; color: var(--text-secondary);'>Amount</th>
                            </tr>
                        </thead>
                        <tbody id='pivot-body' style='font-size: 0.72rem;'>
                            <!-- Pivot rows -->
                        </tbody>
                    </table>
                    <!-- Pivot Mini Bar Chart -->
                    <div id='pivot-chart-container' style='flex: 1; display: flex; flex-direction: column; gap: 14px; padding-top: 24px;'>
                        <!-- Dynamic category bars -->
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Dynamic Status Acceptance Bar -->
    <div class='status-bar' id='status-bar'>
        <div>
            <div class='status-title' id='status-title'>Gemini Extraction Accepted</div>
            <div class='status-desc' id='status-desc'>Extracted total matches audited total. Pipeline validated.</div>
        </div>
        <div id='status-score-badge' class='badge success'>
            Confidence: 100%
        </div>
    </div>

    <script>
        var data = window.INJECTED_DATA || {};
        var chartInstance = null;
        var lineItems = [];
        var originalLineItems = [];
        var originalTotal = 0;

        var policy = null;
        if (window.trustedTypes && window.trustedTypes.createPolicy) {
            try {
                policy = window.trustedTypes.createPolicy('a2ui-policy', {
                    createHTML: function(s) { return s; }
                });
            } catch (e) {
                try {
                    policy = window.trustedTypes.createPolicy('default', {
                        createHTML: function(s) { return s; }
                    });
                } catch (e2) {
                    console.warn('TrustedTypes policy creation failed:', e2);
                }
            }
        }

        function clearElement(element) {
            while (element.firstChild) {
                element.removeChild(element.firstChild);
            }
        }

        function setHTML(element, htmlString) {
            if (policy && typeof policy.createHTML === 'function') {
                try {
                    element.innerHTML = policy.createHTML(htmlString);
                    return;
                } catch (err) {
                    console.warn('TrustedHTML assignment failed, falling back to DOMParser:', err);
                }
            }
            clearElement(element);
            try {
                var parser = new DOMParser();
                var doc = parser.parseFromString(htmlString, 'text/html');
                while (doc.body.firstChild) {
                    element.appendChild(doc.body.firstChild);
                }
            } catch (fallbackErr) {
                console.error('DOMParser fallback failed:', fallbackErr);
                element.innerHTML = htmlString;
            }
        }

        window.addEventListener('message', function(event) {
            if (event.data && event.data.type === 'INJECT_DATA') {
                data = event.data.payload || {};
                init();
            }
        });

        function init() {
            if (data.merchant_name) {
                document.getElementById('db-title').innerText = data.merchant_name + ' Invoice Audit';
                setHTML(document.getElementById('header-badge'), '<span class=\'badge success\' style=\'font-size:0.75rem\'>' + data.merchant_name + '</span>');
            }
            else {
                document.getElementById('db-title').innerText = 'Invoice Audit';
            }
            
            lineItems = data.line_items || [];
            if (originalLineItems.length === 0) {
                originalLineItems = JSON.parse(JSON.stringify(lineItems));
            }
            
            originalTotal = parseFloat(data.total || 0);
            if (!originalTotal) {
                originalTotal = lineItems.reduce(function(sum, item) { return sum + parseFloat(item.amount || 0); }, 0);
            }

            var kpiCont = document.getElementById('kpi-container');
            clearElement(kpiCont);

            var score = data.confidence_score || '5/5';
            var scoreNum = parseFloat(score.split('/')[0]) || 5;
            var confidenceStatus = 'success';
            if (scoreNum < 4) confidenceStatus = 'warning';
            if (scoreNum < 3) confidenceStatus = 'danger';

            var kpiConfidence = document.createElement('div');
            kpiConfidence.className = 'kpi-card ' + confidenceStatus;
            setHTML(kpiConfidence, '<div class=\'kpi-title\'>Confidence Score</div><div class=\'kpi-value\' style=\'color: var(--accent-primary);\'>' + score + '</div><div class=\'kpi-sub\'>Visual audit score</div>');
            kpiCont.appendChild(kpiConfidence);

            var kpiTotal = document.createElement('div');
            kpiTotal.className = 'kpi-card success';
            setHTML(kpiTotal, '<div class=\'kpi-title\'>Audited Total</div><div class=\'kpi-value\' id=\'kpi-total-val\'>$' + originalTotal.toFixed(2) + '</div><div class=\'kpi-sub\'>Extracted sum</div>');
            kpiCont.appendChild(kpiTotal);

            var routing = data.routing_status || 'Success';
            var bucket = data.routing_bucket || 'shade-sandbox-processed';
            var routingStatusClass = routing.toLowerCase().indexOf('error') !== -1 ? 'danger' : 'success';
            if (routing.toLowerCase().indexOf('skipped') !== -1 || routing.toLowerCase().indexOf('missing') !== -1) routingStatusClass = 'warning';
            
            var kpiRouting = document.createElement('div');
            kpiRouting.className = 'kpi-card ' + routingStatusClass;
            setHTML(kpiRouting, '<div class=\'kpi-title\'>GCS Archiving</div><div class=\'kpi-value\' style=\'font-size: 0.95rem;\'>' + routing + '</div><div class=\'kpi-sub\' title=\'' + bucket + '\'>Bucket: ' + bucket + '</div>');
            kpiCont.appendChild(kpiRouting);

            var jira = data.jira_status || 'Skipped (Perfect)';
            var jiraStatusClass = 'success';
            if (jira.toLowerCase().indexOf('created') !== -1 || jira.toLowerCase().indexOf('success') !== -1) jiraStatusClass = 'warning';
            if (jira.toLowerCase().indexOf('error') !== -1) jiraStatusClass = 'danger';

            var kpiJira = document.createElement('div');
            kpiJira.className = 'kpi-card ' + jiraStatusClass;
            setHTML(kpiJira, '<div class=\'kpi-title\'>JIRA Review</div><div class=\'kpi-value\' style=\'font-size: 0.95rem;\'>' + jira + '</div><div class=\'kpi-sub\'>Manual review ticket</div>');
            kpiCont.appendChild(kpiJira);

            renderTableAndSliders();
            renderChart();
            renderPieChart();
            renderPivotTable();
        }

        function renderTableAndSliders() {
            var tbody = document.getElementById('table-body');
            clearElement(tbody);
            
            var slidersList = document.getElementById('sliders-list');
            clearElement(slidersList);

            lineItems.forEach(function(item, index) {
                var tr = document.createElement('tr');
                tr.id = 'tr_' + index;
                setHTML(tr, '<td style=\'font-weight: 600;\'>' + item.item + '</td><td style=\'text-align: center;\' id=\'td_qty_' + index + '\'>' + item.quantity + '</td><td style=\'text-align: right;\' id=\'td_price_' + index + '\'>$' + parseFloat(item.unit_price).toFixed(2) + '</td><td style=\'text-align: right; font-weight: 700; color: var(--accent-primary);\' id=\'td_amount_' + index + '\'>$' + parseFloat(item.amount).toFixed(2) + '</td>');
                tbody.appendChild(tr);

                var maxPrice = Math.max(parseFloat(item.unit_price) * 3, 10.0);
                var sliderGroup = document.createElement('div');
                sliderGroup.className = 'slider-group';
                setHTML(sliderGroup, '<div class=\'slider-header\'><span class=\'slider-label\' title=\'' + item.item + '\'>' + item.item + '</span><span class=\'slider-value\' id=\'slider_val_' + index + '\'>$' + parseFloat(item.unit_price).toFixed(2) + '</span></div><input class=\'slider-input\' type=\'range\' id=\'slider_input_' + index + '\' min=\'0\' max=\'' + maxPrice.toFixed(1) + '\' value=\'' + item.unit_price + '\' step=\'0.01\' oninput=\'updateItemPrice(' + index + ')\'>');
                slidersList.appendChild(sliderGroup);
            });

            updateTotals(false);
        }

        function updateItemPrice(index) {
            var input = document.getElementById('slider_input_' + index);
            var priceVal = parseFloat(input.value);
            
            document.getElementById('slider_val_' + index).textContent = '$' + priceVal.toFixed(2);

            lineItems[index].unit_price = priceVal;
            lineItems[index].amount = priceVal * lineItems[index].quantity;

            document.getElementById('td_price_' + index).textContent = '$' + priceVal.toFixed(2);
            document.getElementById('td_amount_' + index).textContent = '$' + lineItems[index].amount.toFixed(2);

            updateTotals(true);
        }

        function updateTotals(isManualOverride) {
            var currentTotal = 0;
            lineItems.forEach(function(item) {
                currentTotal += parseFloat(item.amount || 0);
            });

            document.getElementById('table-total').textContent = 'Total: $' + currentTotal.toFixed(2);
            document.getElementById('kpi-total-val').textContent = '$' + currentTotal.toFixed(2);

            var statusBar = document.getElementById('status-bar');
            var statusTitle = document.getElementById('status-title');
            var statusDesc = document.getElementById('status-desc');
            var scoreBadge = document.getElementById('status-score-badge');

            var diff = Math.abs(currentTotal - originalTotal);
            var isDiscrepancy = diff > 0.01;

            var resetButton = document.getElementById('reset-btn');
            if (isDiscrepancy || isManualOverride) {
                statusBar.classList.add('override');
                statusTitle.classList.add('override');
                statusTitle.innerText = '⚠️ Auditor Override Active';
                statusDesc.innerText = 'Auditor modified parsed receipt extraction values. Gemini AI confidence rejected.';
                scoreBadge.className = 'badge danger';
                scoreBadge.innerText = 'Confidence: 0%';
                resetButton.style.display = 'inline-block';
            } else {
                statusBar.classList.remove('override');
                statusTitle.classList.remove('override');
                statusTitle.innerText = 'Gemini Extraction Accepted';
                statusDesc.innerText = 'Extracted total matches audited total. Pipeline validated.';
                scoreBadge.className = 'badge success';
                scoreBadge.innerText = 'Confidence: 100%';
                resetButton.style.display = 'none';
            }

            renderChart();
            renderPieChart();
            renderPivotTable();
        }

        function resetPrices() {
            lineItems = JSON.parse(JSON.stringify(originalLineItems));
            renderTableAndSliders();
            updateTotals(false);
        }

        function renderChart() {
            var container = document.getElementById('live-chart-container');
            clearElement(container);
            
            var maxAmount = Math.max.apply(Math, lineItems.map(function(item) { return item.amount; })) || 1.0;

            lineItems.forEach(function(item) {
                var pct = (item.amount / maxAmount) * 100;
                var row = document.createElement('div');
                row.className = 'chart-row';
                
                var rowHtml = '<span class=\'chart-label\' title=\'' + item.item + '\'>' + (item.item.length > 12 ? item.item.substring(0, 10) + '...' : item.item) + '</span><div class=\'chart-bar-wrapper\'><div class=\'chart-bar\' style=\'width: ' + pct.toFixed(1) + '%\'></div></div><span class=\'chart-value\'>$' + parseFloat(item.amount).toFixed(2) + '</span>';
                setHTML(row, rowHtml);
                
                container.appendChild(row);
            });
        }

        function renderPieChart() {
            var svg = document.getElementById('pie-chart');
            clearElement(svg);
            var legend = document.getElementById('pie-legend');
            clearElement(legend);
            
            var totalAmount = lineItems.reduce(function(sum, item) { return sum + item.amount; }, 0);
            if (totalAmount <= 0) return;
            
            var colors = ['#38bdf8', '#818cf8', '#34d399', '#f43f5e', '#fbbf24', '#a78bfa'];
            var cumulativePercent = 0;
            
            function getCoordinatesForPercent(percent) {
                var x = Math.cos(2 * Math.PI * percent);
                var y = Math.sin(2 * Math.PI * percent);
                return [x, y];
            }
            
            lineItems.forEach(function(item, index) {
                var percent = item.amount / totalAmount;
                var color = colors[index % colors.length];
                
                var start = getCoordinatesForPercent(cumulativePercent);
                cumulativePercent += percent;
                var end = getCoordinatesForPercent(cumulativePercent);
                
                var largeArcFlag = percent > 0.5 ? 1 : 0;
                
                var pathData = [
                    'M 70 70',
                    'L ' + (70 + 60 * start[0]) + ' ' + (70 + 60 * start[1]),
                    'A 60 60 0 ' + largeArcFlag + ' 1 ' + (70 + 60 * end[0]) + ' ' + (70 + 60 * end[1]),
                    'Z'
                ].join(' ');
                
                var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                path.setAttribute('d', pathData);
                path.setAttribute('fill', color);
                svg.appendChild(path);
                
                var legendItem = document.createElement('div');
                legendItem.style.display = 'flex';
                legendItem.style.alignItems = 'center';
                legendItem.style.gap = '6px';
                
                var legendHtml = '<span style=\'display:inline-block; width:8px; height:8px; background-color:' + color + '; border-radius:50%;\'></span><span style=\'color: var(--text-secondary); font-weight:600;\'>' + (item.item.length > 12 ? item.item.substring(0, 10) + '...' : item.item) + ': ' + (percent * 100).toFixed(0) + '%</span>';
                setHTML(legendItem, legendHtml);
                legend.appendChild(legendItem);
            });
        }

        function renderPivotTable() {
            var pivotBody = document.getElementById('pivot-body');
            clearElement(pivotBody);
            var chartCont = document.getElementById('pivot-chart-container');
            clearElement(chartCont);
            
            var groups = {};
            lineItems.forEach(function(item) {
                var cat = item.item.split(' ')[0] || 'Other';
                if (!groups[cat]) {
                    groups[cat] = { qty: 0, amount: 0 };
                }
                groups[cat].qty += item.quantity;
                groups[cat].amount += item.amount;
            });
            
            var colors = ['#38bdf8', '#818cf8', '#34d399', '#f43f5e', '#fbbf24', '#a78bfa'];
            var keys = Object.keys(groups);
            var maxAmount = Math.max.apply(Math, keys.map(function(k) { return groups[k].amount; })) || 1.0;
            
            keys.forEach(function(cat, index) {
                var color = colors[index % colors.length];
                
                var tr = document.createElement('tr');
                tr.style.borderBottom = '1px solid var(--border-color)';
                
                var trHtml = '<td style=\'padding: 6px 4px; font-weight: 600;\'><span style=\'display:inline-block; width:6px; height:6px; background-color:' + color + '; border-radius:50%; margin-right:4px;\'></span>' + cat + '</td><td style=\'padding: 6px 4px; text-align: center;\'>' + groups[cat].qty + '</td><td style=\'padding: 6px 4px; text-align: right; font-weight: 700; color: var(--accent-primary);\'>$' + groups[cat].amount.toFixed(2) + '</td>';
                setHTML(tr, trHtml);
                pivotBody.appendChild(tr);
                
                var pct = (groups[cat].amount / maxAmount) * 100;
                var barRow = document.createElement('div');
                barRow.style.display = 'flex';
                barRow.style.flexDirection = 'column';
                barRow.style.gap = '2px';
                
                var barRowHtml = '<div style=\'height:6px; background:var(--border-color); border-radius:3px; overflow:hidden; width:80px;\'><div style=\'height:100%; background:' + color + '; width:' + pct.toFixed(1) + '%;\'></div></div>';
                setHTML(barRow, barRowHtml);
                chartCont.appendChild(barRow);
            });
        }

        function copyItemsToCSV() {
            var csvRows = ['Item,Quantity,Unit Price,Amount'];
            lineItems.forEach(function(item) {
                csvRows.push('\'' + item.item + '\',' + item.quantity + ',' + item.unit_price.toFixed(2) + ',' + item.amount.toFixed(2));
            });
            var csvContent = csvRows.join('\n');
            
            var tempTextArea = document.createElement('textarea');
            tempTextArea.value = csvContent;
            document.body.appendChild(tempTextArea);
            tempTextArea.select();
            try {
                document.execCommand('copy');
                var btn = document.getElementById('copy-csv-btn');
                btn.textContent = '✓ Copied!';
                btn.style.background = 'var(--success)';
                btn.style.borderColor = 'var(--success)';
                setTimeout(function() {
                    btn.textContent = '📋 Copy CSV';
                    btn.style.background = 'var(--border-color)';
                    btn.style.borderColor = 'var(--border-color)';
                }, 2000);
            } catch (err) {
                console.error('Failed to copy CSV: ', err);
            }
            document.body.removeChild(tempTextArea);
        }

        window.addEventListener('load', function() {
            if (window.parent) {
                window.parent.postMessage({ type: 'IFRAME_READY' }, '*');
            }
            if (data && Object.keys(data).length > 0) {
                init();
            }
        });
    </script>
</body>
</html>
"""
    @staticmethod
    def build_audit_dashboard(surface_id: str, audit_data: dict) -> dict:
        """
        Compiles the A2UI v0.8 WebFrameSrcdoc payload for the premium interactive Store Invoice Auditing dashboard.
        Injects extraction and audit values dynamically as window.INJECTED_DATA.
        """
        # Use the inlined clean HTML string directly
        html_template = UIBuilderV08.DASHBOARD_HTML_TEMPLATE

        # Format and inject data package directly
        injected_script = f"<script>window.INJECTED_DATA = {json.dumps(audit_data)};</script>"
        html_injected = html_template.replace("</head>", f"{injected_script}\n</head>")

        surface_update = {
            "surfaceUpdate": {
                "surfaceId": surface_id,
                "components": [
                    {
                        "id": "root",
                        "component": {
                            "WebFrameSrcdoc": {
                                "htmlContent": { "literalString": html_injected }
                            }
                        }
                    }
                ]
            }
        }

        data_model_update = {
            "dataModelUpdate": {
                "surfaceId": surface_id,
                "contents": []
            }
        }

        begin_rendering = {
            "beginRendering": {
                "surfaceId": surface_id,
                "root": "root"
            }
        }

        return {
            "surface_update": surface_update,
            "data_model_update": data_model_update,
            "begin_rendering": begin_rendering
        }

# Global cache to prevent circular import between tools and executor
_LAST_ANALYSIS_RESULTS = {}

def generate_audit_a2ui_dashboard_tool(analysis_results_json: str) -> str:
    """Generates the premium interactive A2UI dashboard JSON block from the audit analysis results.
    
    Args:
        analysis_results_json: The JSON string returned by analyze_uploaded_invoice_tool.
    """
    global _LAST_ANALYSIS_RESULTS
    data = None
    if analysis_results_json:
        try:
            cleaned_json = analysis_results_json.strip()
            if cleaned_json.startswith('"') and cleaned_json.endswith('"'):
                try:
                    cleaned_json = json.loads(cleaned_json)
                except Exception:
                    pass
            data = json.loads(cleaned_json)
        except Exception as e:
            logger.warning(f"Failed to parse analysis results JSON: {e}")
            
    if not data or not isinstance(data, dict) or "Error" in str(data):
        data = _LAST_ANALYSIS_RESULTS
        if not data:
            return "Error: No analysis results available in cache or argument."
    
    def parse_price(val) -> float:
        if val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip().replace("$", "").replace(",", "")
        try:
            return float(s)
        except ValueError:
            return 0.0

    merchant_name = data.get("merchant_name") or data.get("merchant", {}).get("name") or "Unknown Merchant"
    gemini_analysis = data.get("gemini_analysis", {})
    confidence_score = gemini_analysis.get("confidence_score") or data.get("confidence_score") or "5/5"
    total = parse_price(data.get("total") or data.get("subtotal") or 0.0)
    
    gcs_routing = data.get("gcs_routing", {})
    routing_status = gcs_routing.get("status") or "Success"
    routing_bucket = gcs_routing.get("bucket") or "shade-sandbox-processed"
    jira_status = data.get("jira_ticketing") or "Skipped"
    
    line_items = []
    raw_items = data.get("line_items") or []
    for item in raw_items:
        u_price = parse_price(item.get("unit_price") or item.get("price") or 0.0)
        amt = parse_price(item.get("amount") or 0.0)
        if not amt and u_price:
            qty = int(item.get("quantity") or item.get("qty") or 1)
            amt = u_price * qty
        line_items.append({
            "item": item.get("item") or item.get("description") or "Unknown Item",
            "quantity": int(item.get("quantity") or item.get("qty") or 1),
            "unit_price": u_price,
            "amount": amt
        })
        
    dashboard_data = {
        "merchant_name": merchant_name,
        "confidence_score": f"{confidence_score}/5" if "/" not in str(confidence_score) else str(confidence_score),
        "total": total,
        "routing_status": routing_status,
        "routing_bucket": routing_bucket,
        "jira_status": jira_status,
        "line_items": line_items
    }
    
    ui = UIBuilderV08.build_audit_dashboard(
        surface_id="store-invoice-auditor-chart",
        audit_data=dashboard_data
    )
    
    sequence = [
        ui["surface_update"],
        ui["data_model_update"],
        ui["begin_rendering"]
    ]
    
    return f"<a2ui-json>\n{json.dumps(sequence, indent=2)}\n</a2ui-json>"

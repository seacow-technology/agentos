/**
 * JsonViewer - Interactive JSON viewer component
 *
 * Features:
 * - Collapsible tree view
 * - Copy to clipboard
 * - Download as file
 * - Syntax highlighting
 *
 * v0.3.2 - WebUI 100% Coverage Sprint
 */

class JsonViewer {
    constructor(container, data, options = {}) {
        this.container = typeof container === 'string'
            ? document.querySelector(container)
            : container;
        this.data = data;
        this.options = {
            collapsed: options.collapsed || false,
            maxDepth: options.maxDepth || Infinity,
            showToolbar: options.showToolbar !== false,
            fileName: options.fileName || 'data.json',
            ...options,
        };

        this.render();
    }

    /**
     * Render the JSON viewer
     */
    render() {
        this.container.innerHTML = '';
        this.container.className = 'json-viewer';

        // Toolbar
        if (this.options.showToolbar) {
            const toolbar = this.createToolbar();
            this.container.appendChild(toolbar);
        }

        // JSON content
        const content = document.createElement('div');
        content.className = 'json-content';
        content.appendChild(this.renderValue(this.data, 0));
        this.container.appendChild(content);
    }

    /**
     * Create toolbar
     */
    createToolbar() {
        const toolbar = document.createElement('div');
        toolbar.className = 'json-toolbar';

        // Expand/Collapse All button
        const expandBtn = document.createElement('button');
        expandBtn.className = 'json-btn';
        expandBtn.textContent = 'Expand All';
        expandBtn.onclick = () => this.expandAll();
        toolbar.appendChild(expandBtn);

        const collapseBtn = document.createElement('button');
        collapseBtn.className = 'json-btn';
        collapseBtn.textContent = 'Collapse All';
        collapseBtn.onclick = () => this.collapseAll();
        toolbar.appendChild(collapseBtn);

        // Copy button
        const copyBtn = document.createElement('button');
        copyBtn.className = 'json-btn';
        copyBtn.innerHTML = '<span class="material-icons md-18">content_copy</span> Copy';
        copyBtn.onclick = () => this.copyToClipboard();
        toolbar.appendChild(copyBtn);

        // Download button
        const downloadBtn = document.createElement('button');
        downloadBtn.className = 'json-btn';
        downloadBtn.innerHTML = '<span class="material-icons md-18">arrow_downward</span> Download';
        downloadBtn.onclick = () => this.download();
        toolbar.appendChild(downloadBtn);

        return toolbar;
    }

    /**
     * Render a value (recursive)
     */
    renderValue(value, depth) {
        const type = this.getType(value);

        switch (type) {
            case 'object':
                return this.renderObject(value, depth);
            case 'array':
                return this.renderArray(value, depth);
            case 'string':
                return this.renderPrimitive(value, 'json-string');
            case 'number':
                return this.renderPrimitive(value, 'json-number');
            case 'boolean':
                return this.renderPrimitive(value, 'json-boolean');
            case 'null':
                return this.renderPrimitive(null, 'json-null');
            default:
                return this.renderPrimitive(String(value), 'json-unknown');
        }
    }

    /**
     * Render object
     */
    renderObject(obj, depth) {
        const container = document.createElement('div');
        container.className = 'json-object';

        const keys = Object.keys(obj);
        const isEmpty = keys.length === 0;

        if (isEmpty) {
            const empty = document.createElement('span');
            empty.className = 'json-punctuation';
            empty.textContent = '{}';
            return empty;
        }

        // Opening brace with toggle
        const header = document.createElement('div');
        header.className = 'json-line';

        const toggle = document.createElement('span');
        toggle.className = 'json-toggle';
        toggle.classList.add('material-icons');
        toggle.textContent = 'expand_more';
        toggle.style.fontSize = '16px';
        toggle.onclick = (e) => {
            e.stopPropagation();
            this.toggleCollapse(container);
        };
        header.appendChild(toggle);

        const openBrace = document.createElement('span');
        openBrace.className = 'json-punctuation';
        openBrace.textContent = '{';
        header.appendChild(openBrace);

        const summary = document.createElement('span');
        summary.className = 'json-summary';
        summary.textContent = ` ${keys.length} ${keys.length === 1 ? 'key' : 'keys'} `;
        header.appendChild(summary);

        const closeBrace = document.createElement('span');
        closeBrace.className = 'json-punctuation json-collapsed';
        closeBrace.textContent = '}';
        header.appendChild(closeBrace);

        container.appendChild(header);

        // Properties
        const properties = document.createElement('div');
        properties.className = 'json-properties';

        keys.forEach((key, index) => {
            const line = document.createElement('div');
            line.className = 'json-line json-property';

            const keySpan = document.createElement('span');
            keySpan.className = 'json-key';
            keySpan.textContent = `"${key}"`;
            line.appendChild(keySpan);

            const colon = document.createElement('span');
            colon.className = 'json-punctuation';
            colon.textContent = ': ';
            line.appendChild(colon);

            const valueContainer = document.createElement('span');
            valueContainer.appendChild(this.renderValue(obj[key], depth + 1));
            line.appendChild(valueContainer);

            if (index < keys.length - 1) {
                const comma = document.createElement('span');
                comma.className = 'json-punctuation';
                comma.textContent = ',';
                line.appendChild(comma);
            }

            properties.appendChild(line);
        });

        container.appendChild(properties);

        // Closing brace
        const footer = document.createElement('div');
        footer.className = 'json-line';
        const closingBrace = document.createElement('span');
        closingBrace.className = 'json-punctuation';
        closingBrace.textContent = '}';
        footer.appendChild(closingBrace);
        container.appendChild(footer);

        // Auto-collapse based on depth
        if (this.options.collapsed || depth >= this.options.maxDepth) {
            this.collapse(container);
        }

        return container;
    }

    /**
     * Render array
     */
    renderArray(arr, depth) {
        const container = document.createElement('div');
        container.className = 'json-array';

        const isEmpty = arr.length === 0;

        if (isEmpty) {
            const empty = document.createElement('span');
            empty.className = 'json-punctuation';
            empty.textContent = '[]';
            return empty;
        }

        // Opening bracket with toggle
        const header = document.createElement('div');
        header.className = 'json-line';

        const toggle = document.createElement('span');
        toggle.className = 'json-toggle';
        toggle.classList.add('material-icons');
        toggle.textContent = 'expand_more';
        toggle.style.fontSize = '16px';
        toggle.onclick = (e) => {
            e.stopPropagation();
            this.toggleCollapse(container);
        };
        header.appendChild(toggle);

        const openBracket = document.createElement('span');
        openBracket.className = 'json-punctuation';
        openBracket.textContent = '[';
        header.appendChild(openBracket);

        const summary = document.createElement('span');
        summary.className = 'json-summary';
        summary.textContent = ` ${arr.length} ${arr.length === 1 ? 'item' : 'items'} `;
        header.appendChild(summary);

        const closeBracket = document.createElement('span');
        closeBracket.className = 'json-punctuation json-collapsed';
        closeBracket.textContent = ']';
        header.appendChild(closeBracket);

        container.appendChild(header);

        // Items
        const items = document.createElement('div');
        items.className = 'json-items';

        arr.forEach((item, index) => {
            const line = document.createElement('div');
            line.className = 'json-line json-item';

            const valueContainer = document.createElement('span');
            valueContainer.appendChild(this.renderValue(item, depth + 1));
            line.appendChild(valueContainer);

            if (index < arr.length - 1) {
                const comma = document.createElement('span');
                comma.className = 'json-punctuation';
                comma.textContent = ',';
                line.appendChild(comma);
            }

            items.appendChild(line);
        });

        container.appendChild(items);

        // Closing bracket
        const footer = document.createElement('div');
        footer.className = 'json-line';
        const closingBracket = document.createElement('span');
        closingBracket.className = 'json-punctuation';
        closingBracket.textContent = ']';
        footer.appendChild(closingBracket);
        container.appendChild(footer);

        // Auto-collapse based on depth
        if (this.options.collapsed || depth >= this.options.maxDepth) {
            this.collapse(container);
        }

        return container;
    }

    /**
     * Render primitive value
     */
    renderPrimitive(value, className) {
        const span = document.createElement('span');
        span.className = className;

        if (className === 'json-string') {
            span.textContent = `"${value}"`;
        } else if (className === 'json-null') {
            span.textContent = 'null';
        } else {
            span.textContent = String(value);
        }

        return span;
    }

    /**
     * Get value type
     */
    getType(value) {
        if (value === null) return 'null';
        if (Array.isArray(value)) return 'array';
        return typeof value;
    }

    /**
     * Toggle collapse state
     */
    toggleCollapse(container) {
        if (container.classList.contains('collapsed')) {
            this.expand(container);
        } else {
            this.collapse(container);
        }
    }

    /**
     * Collapse a container
     */
    collapse(container) {
        container.classList.add('collapsed');
        const toggle = container.querySelector('.json-toggle');
        if (toggle) toggle.textContent = '▶';

        const properties = container.querySelector('.json-properties, .json-items');
        const footer = container.querySelector('.json-line:last-child');
        if (properties) properties.style.display = 'none';
        if (footer) footer.style.display = 'none';

        const summary = container.querySelector('.json-summary');
        const closeBrace = container.querySelector('.json-collapsed');
        if (summary) summary.style.display = 'inline';
        if (closeBrace) closeBrace.style.display = 'inline';
    }

    /**
     * Expand a container
     */
    expand(container) {
        container.classList.remove('collapsed');
        const toggle = container.querySelector('.json-toggle');
        if (toggle) {
            toggle.classList.add('material-icons');
            toggle.textContent = 'expand_more';
            toggle.style.fontSize = '16px';
        }

        const properties = container.querySelector('.json-properties, .json-items');
        const footer = container.querySelector('.json-line:last-child');
        if (properties) properties.style.display = 'block';
        if (footer) footer.style.display = 'flex';

        const summary = container.querySelector('.json-summary');
        const closeBrace = container.querySelector('.json-collapsed');
        if (summary) summary.style.display = 'none';
        if (closeBrace) closeBrace.style.display = 'none';
    }

    /**
     * Expand all
     */
    expandAll() {
        const containers = this.container.querySelectorAll('.json-object, .json-array');
        containers.forEach(container => this.expand(container));
    }

    /**
     * Collapse all
     */
    collapseAll() {
        const containers = this.container.querySelectorAll('.json-object, .json-array');
        containers.forEach(container => this.collapse(container));
    }

    /**
     * Copy to clipboard
     */
    async copyToClipboard() {
        const json = JSON.stringify(this.data, null, 2);
        try {
            await navigator.clipboard.writeText(json);
            window.showToast?.('Copied to clipboard', 'success');
        } catch (err) {
            console.error('Failed to copy:', err);
            window.showToast?.('Failed to copy', 'error');
        }
    }

    /**
     * Download as file
     */
    download() {
        const json = JSON.stringify(this.data, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = this.options.fileName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    /**
     * Update data
     */
    update(data) {
        this.data = data;
        this.render();
    }
}

// Export to window
window.JsonViewer = JsonViewer;

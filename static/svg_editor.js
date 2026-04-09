// ============================================
// SVGエディタ — Fabric.js PowerPoint風フル編集
// ============================================

const svgEditor = {
    canvas: null,
    overlay: null,
    canvasWrap: null,
    propsPanel: null,
    currentTool: 'select',
    originalSvgUrl: null,
    canvasWidth: 680,
    canvasHeight: 520,

    // Image mode: 'svg' or 'raster'
    imageMode: 'svg',

    // History (Undo/Redo)
    history: [],
    historyIndex: -1,
    historyMax: 50,
    historyLocked: false,

    // Clipboard
    clipboard: null,

    // Drawing state
    isDrawing: false,
    drawStartX: 0,
    drawStartY: 0,
    drawingObject: null,

    // Zoom/Pan
    zoomLevel: 1,
    isPanning: false,
    panStartX: 0,
    panStartY: 0,
    lastPosX: 0,
    lastPosY: 0,
    spacePressed: false,

    // Grid
    gridEnabled: false,
    gridSize: 10,

    // Preset colors for new objects
    presetFillColor: '#e0e0e0',
    presetStrokeColor: '#333333',
    presetTextColor: '#333333',
    presetStrokeWidth: 2,

    // Arrow size presets
    arrowSizePresets: {
        thin:   { strokeWidth: 1.5, headLen: 8 },
        medium: { strokeWidth: 3,   headLen: 12 },
        thick:  { strokeWidth: 5,   headLen: 16 },
    },
    currentArrowSize: 'thin',

    // ============================================
    // 初期化
    // ============================================
    init() {
        this.overlay = document.getElementById('svgEditorOverlay');
        this.canvasWrap = this.overlay.querySelector('.svg-editor-canvas-wrap');
        this.propsPanel = this.overlay.querySelector('.svg-editor-props');
        this._initToolbar();
        this._initKeyboard();
    },

    // ============================================
    // エディタを開く
    // ============================================
    open(imageUrl) {
        this.originalSvgUrl = imageUrl;
        this.imageMode = /\.(jpg|jpeg|png|gif)(\?|$)/i.test(imageUrl) ? 'raster' : 'svg';
        this.overlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';

        // 既存canvasを破棄
        if (this.canvas) {
            this.canvas.dispose();
        }

        // Canvas生成
        this.canvas = new fabric.Canvas('svgEditorCanvas', {
            backgroundColor: '#ffffff',
            selection: true,
            preserveObjectStacking: true,
        });

        this._resetHistory();
        if (this.imageMode === 'raster') {
            this._loadImage(imageUrl);
        } else {
            this._loadSvg(imageUrl);
        }
        this._bindCanvasEvents();
        this._updatePropsPanel();
        this.setTool('select');
        this.zoomLevel = 1;
        this._updateZoomDisplay();
    },

    // ============================================
    // エディタを閉じる
    // ============================================
    close() {
        this.overlay.style.display = 'none';
        document.body.style.overflow = '';
        if (this.canvas) {
            this.canvas.dispose();
            this.canvas = null;
        }
    },

    // ============================================
    // ラスター画像読み込み
    // ============================================
    _loadImage(url) {
        const self = this;
        fabric.Image.fromURL(url, function(img) {
            if (!img || !img.width) {
                self._showToast('画像の読み込みに失敗しました');
                return;
            }
            self.canvasWidth = img.width;
            self.canvasHeight = img.height;
            self.canvas.setDimensions({ width: img.width, height: img.height });

            // 背景画像として設定（選択不可・移動不可）
            self.canvas.setBackgroundImage(img, function() {
                self.canvas.requestRenderAll();
                self._saveHistory();
                self._fitToScreen();
            }, {
                originX: 'left',
                originY: 'top',
            });
        }, { crossOrigin: 'anonymous' });
    },

    // ============================================
    // SVG読み込み
    // ============================================
    _loadSvg(url) {
        const self = this;
        // renderOnAddRemoveを無効化して一括読み込み
        this.canvas.renderOnAddRemove = false;

        fabric.loadSVGFromURL(url, function(objects, options) {
            // viewBoxからサイズ取得
            if (options.viewBoxWidth && options.viewBoxHeight) {
                self.canvasWidth = options.viewBoxWidth;
                self.canvasHeight = options.viewBoxHeight;
            } else if (options.width && options.height) {
                self.canvasWidth = parseFloat(options.width);
                self.canvasHeight = parseFloat(options.height);
            }

            self.canvas.setDimensions({
                width: self.canvasWidth,
                height: self.canvasHeight
            });

            // 各オブジェクトを処理してcanvasに追加
            // Text → IText変換（reviverでは返り値が無視されるためここで行う）
            // 注意: Fabric.jsのText.fromElementはtext-anchor="middle"を検出し、
            // left = x - textWidth/2 に自動補正済み。originXは'left'のままで正しい。
            objects.forEach(function(obj) {
                if (!obj) return;

                if (obj.type === 'text') {
                    var itext = new fabric.IText(obj.text, {
                        left: obj.left,
                        top: obj.top,
                        fontSize: obj.fontSize,
                        fontFamily: obj.fontFamily || 'sans-serif',
                        fontWeight: obj.fontWeight || 'normal',
                        fontStyle: obj.fontStyle || 'normal',
                        fill: obj.fill || '#000000',
                        originX: 'left',
                        originY: obj.originY || 'top',
                        textAlign: 'left',
                        strokeWidth: obj.strokeWidth || 0,
                    });
                    self.canvas.add(itext);
                } else {
                    self.canvas.add(obj);
                }
            });

            // 矢印オブジェクトのtoSVGオーバーライドを適用
            self.canvas.getObjects().forEach(obj => {
                if (obj._isArrow) self._applyArrowToSVG(obj);
            });

            self.canvas.renderOnAddRemove = true;
            self.canvas.requestRenderAll();
            self._saveHistory();
            self._fitToScreen();
        }, function(element, obj) {
            // reviver: objをin-place変更（返り値は無視される）
            if (!obj) return;

            // 線のmarker-end検出 → ArrowLineフラグ
            if ((obj.type === 'line' || obj.type === 'polyline') && element.getAttribute('marker-end')) {
                obj._isArrow = true;
                obj._markerStroke = element.getAttribute('stroke') || obj.stroke || '#888780';
            }
        });
    },

    // ============================================
    // ツール切替
    // ============================================
    setTool(tool) {
        this.currentTool = tool;
        // ツールバーボタンのアクティブ状態
        this.overlay.querySelectorAll('.tool-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tool === tool);
        });
        // カーソル
        const wrap = this.canvasWrap;
        wrap.className = 'svg-editor-canvas-wrap';
        if (tool !== 'select') {
            wrap.classList.add('tool-' + tool);
        }
        // 矢印太さボタン群の表示切替
        const arrowGroup = this.overlay.querySelector('.arrow-thickness-group');
        if (arrowGroup) arrowGroup.style.display = (tool === 'arrow') ? 'inline-flex' : 'none';
        // フリーハンド描画モード
        if (this.canvas) {
            const isDrawMode = (tool === 'draw' || tool === 'highlight');
            this.canvas.isDrawingMode = isDrawMode;
            if (isDrawMode) {
                const brush = this.canvas.freeDrawingBrush;
                if (tool === 'highlight') {
                    brush.color = 'rgba(255,255,0,0.3)';
                    brush.width = 20;
                } else {
                    brush.color = this.presetStrokeColor;
                    brush.width = this.presetStrokeWidth;
                }
            }
        }
        // 選択ツール以外ではオブジェクト選択を無効化
        if (this.canvas) {
            const isSelect = (tool === 'select');
            this.canvas.selection = isSelect;
            this.canvas.forEachObject(o => {
                o.selectable = isSelect;
                o.evented = isSelect;
            });
            if (!isSelect) {
                this.canvas.discardActiveObject();
                this.canvas.requestRenderAll();
            }
        }
    },

    // ============================================
    // Canvasイベント
    // ============================================
    _bindCanvasEvents() {
        const self = this;
        const c = this.canvas;

        // 選択変更 → プロパティパネル更新
        c.on('selection:created', () => self._updatePropsPanel());
        c.on('selection:updated', () => self._updatePropsPanel());
        c.on('selection:cleared', () => self._updatePropsPanel());

        // オブジェクト変更 → 履歴保存
        c.on('object:modified', () => self._saveHistory());

        // 図形描画: mouse:down
        c.on('mouse:down', function(opt) {
            if (self.spacePressed) {
                // Pan
                self.isPanning = true;
                self.panStartX = opt.e.clientX;
                self.panStartY = opt.e.clientY;
                self.lastPosX = c.viewportTransform[4];
                self.lastPosY = c.viewportTransform[5];
                return;
            }

            const tool = self.currentTool;
            if (tool === 'select') return;

            const pointer = c.getPointer(opt.e);
            self.isDrawing = true;
            self.drawStartX = pointer.x;
            self.drawStartY = pointer.y;

            if (tool === 'rect') {
                self.drawingObject = new fabric.Rect({
                    left: pointer.x, top: pointer.y,
                    width: 0, height: 0,
                    fill: self.presetFillColor, stroke: self.presetStrokeColor, strokeWidth: self.presetStrokeWidth,
                    rx: 0, ry: 0,
                });
                c.add(self.drawingObject);
            } else if (tool === 'ellipse') {
                self.drawingObject = new fabric.Ellipse({
                    left: pointer.x, top: pointer.y,
                    rx: 0, ry: 0,
                    fill: self.presetFillColor, stroke: self.presetStrokeColor, strokeWidth: self.presetStrokeWidth,
                });
                c.add(self.drawingObject);
            } else if (tool === 'line' || tool === 'arrow') {
                const arrowPreset = self.arrowSizePresets[self.currentArrowSize];
                const sw = tool === 'arrow' ? arrowPreset.strokeWidth : self.presetStrokeWidth;
                self.drawingObject = new fabric.Line(
                    [pointer.x, pointer.y, pointer.x, pointer.y],
                    { stroke: self.presetStrokeColor, strokeWidth: sw }
                );
                if (tool === 'arrow') {
                    self.drawingObject._isArrow = true;
                    self.drawingObject._markerStroke = self.presetStrokeColor;
                    self.drawingObject._arrowHeadLen = arrowPreset.headLen;
                    self._applyArrowToSVG(self.drawingObject);
                }
                c.add(self.drawingObject);
            } else if (tool === 'text') {
                const itext = new fabric.IText('テキスト', {
                    left: pointer.x, top: pointer.y,
                    fontSize: 14,
                    fontFamily: 'sans-serif',
                    fill: self.presetTextColor,
                });
                c.add(itext);
                c.setActiveObject(itext);
                itext.enterEditing();
                self.isDrawing = false;
                self._saveHistory();
                self.setTool('select');
            }
        });

        // 図形描画: mouse:move
        c.on('mouse:move', function(opt) {
            if (self.isPanning) {
                const dx = opt.e.clientX - self.panStartX;
                const dy = opt.e.clientY - self.panStartY;
                const vpt = c.viewportTransform.slice();
                vpt[4] = self.lastPosX + dx;
                vpt[5] = self.lastPosY + dy;
                c.setViewportTransform(vpt);
                return;
            }

            if (!self.isDrawing || !self.drawingObject) return;
            const pointer = c.getPointer(opt.e);
            const tool = self.currentTool;

            if (tool === 'rect') {
                const left = Math.min(self.drawStartX, pointer.x);
                const top = Math.min(self.drawStartY, pointer.y);
                self.drawingObject.set({
                    left: left, top: top,
                    width: Math.abs(pointer.x - self.drawStartX),
                    height: Math.abs(pointer.y - self.drawStartY),
                });
            } else if (tool === 'ellipse') {
                const rx = Math.abs(pointer.x - self.drawStartX) / 2;
                const ry = Math.abs(pointer.y - self.drawStartY) / 2;
                self.drawingObject.set({
                    left: Math.min(self.drawStartX, pointer.x),
                    top: Math.min(self.drawStartY, pointer.y),
                    rx: rx, ry: ry,
                });
            } else if (tool === 'line' || tool === 'arrow') {
                self.drawingObject.set({ x2: pointer.x, y2: pointer.y });
            }

            c.requestRenderAll();
        });

        // 図形描画: mouse:up
        c.on('mouse:up', function() {
            if (self.isPanning) {
                self.isPanning = false;
                return;
            }
            if (self.isDrawing && self.drawingObject) {
                self.isDrawing = false;
                self.drawingObject.setCoords();
                self.drawingObject = null;
                self._saveHistory();
                self.setTool('select');
            }
        });

        // マウスホイールズーム
        c.on('mouse:wheel', function(opt) {
            opt.e.preventDefault();
            const delta = opt.e.deltaY;
            let zoom = c.getZoom();
            zoom *= 0.999 ** delta;
            zoom = Math.max(0.1, Math.min(5, zoom));
            c.zoomToPoint({ x: opt.e.offsetX, y: opt.e.offsetY }, zoom);
            self.zoomLevel = zoom;
            self._updateZoomDisplay();
            self._updateGridOverlay();
        });

        // フリーハンド描画完了
        c.on('path:created', function() {
            self._saveHistory();
        });

        // 矢印描画（after:render）
        c.on('after:render', function() {
            self._drawArrows();
        });

        // グリッドスナップ
        c.on('object:moving', function(opt) {
            if (self.gridEnabled) {
                const obj = opt.target;
                obj.set({
                    left: Math.round(obj.left / self.gridSize) * self.gridSize,
                    top: Math.round(obj.top / self.gridSize) * self.gridSize,
                });
            }
        });
    },

    // ============================================
    // 矢印描画（marker代替 — ビューポート変換対応）
    // ============================================
    _drawArrows() {
        if (!this.canvas) return;
        const ctx = this.canvas.getContext();
        const vpt = this.canvas.viewportTransform;
        const zoom = vpt[0];

        this.canvas.forEachObject(obj => {
            if (!obj._isArrow || obj.type !== 'line') return;
            const coords = obj.calcLinePoints();
            const p = obj.getCenterPoint();

            // オブジェクト座標をビューポート座標に変換
            const p1 = fabric.util.transformPoint(
                new fabric.Point(p.x + coords.x1, p.y + coords.y1), vpt
            );
            const p2 = fabric.util.transformPoint(
                new fabric.Point(p.x + coords.x2, p.y + coords.y2), vpt
            );

            const angle = Math.atan2(p2.y - p1.y, p2.x - p1.x);
            const headLen = (obj._arrowHeadLen || 10) * zoom;
            const sw = (obj.strokeWidth || 1.5) * zoom;

            ctx.save();
            ctx.beginPath();
            ctx.moveTo(p2.x, p2.y);
            ctx.lineTo(
                p2.x - headLen * Math.cos(angle - Math.PI / 6),
                p2.y - headLen * Math.sin(angle - Math.PI / 6)
            );
            ctx.moveTo(p2.x, p2.y);
            ctx.lineTo(
                p2.x - headLen * Math.cos(angle + Math.PI / 6),
                p2.y - headLen * Math.sin(angle + Math.PI / 6)
            );
            ctx.strokeStyle = obj._markerStroke || obj.stroke || '#333';
            ctx.lineWidth = Math.max(1.5, sw * 0.5);
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            ctx.stroke();
            ctx.restore();
        });
    },

    // 矢印オブジェクトにtoSVGオーバーライドを適用
    _applyArrowToSVG(obj) {
        if (!obj || !obj._isArrow) return;
        const origToSVG = obj.toSVG.bind(obj);
        obj.toSVG = function(reviver) {
            let svg = origToSVG(reviver);
            svg = svg.replace(/<line /, '<line marker-end="url(#arr2)" ');
            return svg;
        };
    },

    // ============================================
    // グリッド表示（CSS方式 — 重複描画バグ解消）
    // ============================================
    _updateGridOverlay() {
        const wrap = this.canvasWrap;
        if (!wrap) return;
        if (!this.gridEnabled) {
            wrap.style.backgroundImage = 'none';
            return;
        }
        const gs = this.gridSize * this.zoomLevel;
        wrap.style.backgroundImage =
            `repeating-linear-gradient(0deg, transparent, transparent ${gs - 0.5}px, rgba(0,0,0,0.1) ${gs - 0.5}px, rgba(0,0,0,0.1) ${gs}px),
             repeating-linear-gradient(90deg, transparent, transparent ${gs - 0.5}px, rgba(0,0,0,0.1) ${gs - 0.5}px, rgba(0,0,0,0.1) ${gs}px)`;
        wrap.style.backgroundSize = `${gs}px ${gs}px`;
    },

    // ============================================
    // Undo / Redo
    // ============================================
    _resetHistory() {
        this.history = [];
        this.historyIndex = -1;
    },

    _saveHistory() {
        if (this.historyLocked || !this.canvas) return;
        // 現在位置より先の履歴を切り捨て
        this.history = this.history.slice(0, this.historyIndex + 1);
        const json = JSON.stringify(this.canvas.toJSON(['_isArrow', '_markerStroke', '_arrowHeadLen']));
        this.history.push(json);
        if (this.history.length > this.historyMax) {
            this.history.shift();
        }
        this.historyIndex = this.history.length - 1;
    },

    undo() {
        if (this.historyIndex <= 0 || !this.canvas) return;
        this.historyIndex--;
        this._loadHistory();
    },

    redo() {
        if (this.historyIndex >= this.history.length - 1 || !this.canvas) return;
        this.historyIndex++;
        this._loadHistory();
    },

    _loadHistory() {
        const self = this;
        this.historyLocked = true;
        this.canvas.loadFromJSON(this.history[this.historyIndex], function() {
            // IText復元: TextをITextに変換
            const objects = self.canvas.getObjects();
            const toReplace = [];
            objects.forEach((obj, i) => {
                if (obj.type === 'text') {
                    toReplace.push({ index: i, obj: obj });
                }
            });
            toReplace.reverse().forEach(item => {
                const old = item.obj;
                const itext = new fabric.IText(old.text, old.toObject());
                itext._isArrow = old._isArrow;
                itext._markerStroke = old._markerStroke;
                self.canvas.remove(old);
                self.canvas.insertAt(itext, item.index);
            });
            // 矢印オブジェクトのtoSVGオーバーライドを再適用
            self.canvas.getObjects().forEach(obj => {
                if (obj._isArrow) self._applyArrowToSVG(obj);
            });
            self.canvas.requestRenderAll();
            self.historyLocked = false;
            self._updatePropsPanel();
        });
    },

    // ============================================
    // Z順序
    // ============================================
    bringToFront() {
        const obj = this.canvas?.getActiveObject();
        if (obj) { this.canvas.bringToFront(obj); this._saveHistory(); }
    },
    sendToBack() {
        const obj = this.canvas?.getActiveObject();
        if (obj) { this.canvas.sendToBack(obj); this._saveHistory(); }
    },
    bringForward() {
        const obj = this.canvas?.getActiveObject();
        if (obj) { this.canvas.bringForward(obj); this._saveHistory(); }
    },
    sendBackwards() {
        const obj = this.canvas?.getActiveObject();
        if (obj) { this.canvas.sendBackwards(obj); this._saveHistory(); }
    },

    // ============================================
    // 整列
    // ============================================
    align(type) {
        const active = this.canvas?.getActiveObject();
        if (!active) return;

        let objects;
        if (active.type === 'activeSelection') {
            objects = active.getObjects();
        } else {
            // 単一オブジェクト → キャンバス基準で整列
            objects = [active];
        }

        if (objects.length < 1) return;

        if (objects.length === 1) {
            // キャンバスに対して整列
            const obj = objects[0];
            const bound = active.type === 'activeSelection'
                ? { left: active.left, top: active.top, width: active.width, height: active.height }
                : null;
            switch (type) {
                case 'left': obj.set('left', 0); break;
                case 'centerH': obj.set('left', (this.canvasWidth - obj.getScaledWidth()) / 2); break;
                case 'right': obj.set('left', this.canvasWidth - obj.getScaledWidth()); break;
                case 'top': obj.set('top', 0); break;
                case 'centerV': obj.set('top', (this.canvasHeight - obj.getScaledHeight()) / 2); break;
                case 'bottom': obj.set('top', this.canvasHeight - obj.getScaledHeight()); break;
            }
            obj.setCoords();
        } else {
            // 複数オブジェクト → グループ内で整列
            const bounds = objects.map(o => {
                const rect = o.getBoundingRect(true);
                return rect;
            });
            const minLeft = Math.min(...bounds.map(b => b.left));
            const maxRight = Math.max(...bounds.map(b => b.left + b.width));
            const minTop = Math.min(...bounds.map(b => b.top));
            const maxBottom = Math.max(...bounds.map(b => b.top + b.height));
            const centerX = (minLeft + maxRight) / 2;
            const centerY = (minTop + maxBottom) / 2;

            objects.forEach((obj, i) => {
                const b = bounds[i];
                switch (type) {
                    case 'left': obj.set('left', obj.left + (minLeft - b.left)); break;
                    case 'centerH': obj.set('left', obj.left + (centerX - b.left - b.width / 2)); break;
                    case 'right': obj.set('left', obj.left + (maxRight - b.left - b.width)); break;
                    case 'top': obj.set('top', obj.top + (minTop - b.top)); break;
                    case 'centerV': obj.set('top', obj.top + (centerY - b.top - b.height / 2)); break;
                    case 'bottom': obj.set('top', obj.top + (maxBottom - b.top - b.height)); break;
                }
                obj.setCoords();
            });
        }

        this.canvas.requestRenderAll();
        this._saveHistory();
    },

    // ============================================
    // コピー / ペースト
    // ============================================
    copy() {
        const active = this.canvas?.getActiveObject();
        if (!active) return;
        active.clone(cloned => {
            this.clipboard = cloned;
        }, ['_isArrow', '_markerStroke', '_arrowHeadLen']);
    },

    paste() {
        if (!this.clipboard || !this.canvas) return;
        this.clipboard.clone(cloned => {
            this.canvas.discardActiveObject();
            cloned.set({ left: cloned.left + 15, top: cloned.top + 15, evented: true });
            if (cloned.type === 'activeSelection') {
                cloned.canvas = this.canvas;
                cloned.forEachObject(obj => {
                    this.canvas.add(obj);
                });
                cloned.setCoords();
            } else {
                this.canvas.add(cloned);
            }
            this.clipboard.top += 15;
            this.clipboard.left += 15;
            // 矢印のtoSVGオーバーライド再適用
            if (cloned._isArrow) {
                this._applyArrowToSVG(cloned);
            } else if (cloned.type === 'activeSelection') {
                cloned.forEachObject(obj => {
                    if (obj._isArrow) this._applyArrowToSVG(obj);
                });
            }
            this.canvas.setActiveObject(cloned);
            this.canvas.requestRenderAll();
            this._saveHistory();
        }, ['_isArrow', '_markerStroke', '_arrowHeadLen']);
    },

    // ============================================
    // グループ化 / 解除
    // ============================================
    group() {
        const active = this.canvas?.getActiveObject();
        if (!active || active.type !== 'activeSelection') return;
        active.toGroup();
        this.canvas.requestRenderAll();
        this._saveHistory();
    },

    ungroup() {
        const active = this.canvas?.getActiveObject();
        if (!active || active.type !== 'group') return;
        active.toActiveSelection();
        this.canvas.requestRenderAll();
        this._saveHistory();
    },

    // ============================================
    // 削除
    // ============================================
    deleteSelected() {
        const active = this.canvas?.getActiveObject();
        if (!active) return;
        if (active.type === 'activeSelection') {
            active.forEachObject(obj => this.canvas.remove(obj));
            this.canvas.discardActiveObject();
        } else {
            this.canvas.remove(active);
        }
        this.canvas.requestRenderAll();
        this._saveHistory();
    },

    // ============================================
    // 全選択
    // ============================================
    selectAll() {
        if (!this.canvas) return;
        this.canvas.discardActiveObject();
        const sel = new fabric.ActiveSelection(this.canvas.getObjects(), {
            canvas: this.canvas,
        });
        this.canvas.setActiveObject(sel);
        this.canvas.requestRenderAll();
    },

    // ============================================
    // Zoom
    // ============================================
    zoomIn() {
        this.zoomLevel = Math.min(5, this.zoomLevel * 1.2);
        this.canvas.setZoom(this.zoomLevel);
        this._resizeCanvasForZoom();
        this._updateZoomDisplay();
        this._updateGridOverlay();
    },

    zoomOut() {
        this.zoomLevel = Math.max(0.1, this.zoomLevel / 1.2);
        this.canvas.setZoom(this.zoomLevel);
        this._resizeCanvasForZoom();
        this._updateZoomDisplay();
        this._updateGridOverlay();
    },

    _fitToScreen() {
        if (!this.canvas || !this.canvasWrap) return;
        const wrapRect = this.canvasWrap.getBoundingClientRect();
        const margin = 40;
        const scaleX = (wrapRect.width - margin) / this.canvasWidth;
        const scaleY = (wrapRect.height - margin) / this.canvasHeight;
        this.zoomLevel = Math.min(scaleX, scaleY);
        this.canvas.setZoom(this.zoomLevel);
        this._resizeCanvasForZoom();
        this._updateZoomDisplay();
        // viewportをリセット
        this.canvas.viewportTransform[4] = 0;
        this.canvas.viewportTransform[5] = 0;
        this.canvas.requestRenderAll();
        this._updateGridOverlay();
    },

    _resizeCanvasForZoom() {
        if (!this.canvas) return;
        this.canvas.setDimensions({
            width: this.canvasWidth * this.zoomLevel,
            height: this.canvasHeight * this.zoomLevel,
        });
    },

    _updateZoomDisplay() {
        const el = this.overlay.querySelector('.zoom-level');
        if (el) el.textContent = Math.round(this.zoomLevel * 100) + '%';
    },

    // ============================================
    // キャンバスリサイズダイアログ
    // ============================================
    showResizeDialog() {
        const dlg = this.overlay.querySelector('.svg-editor-resize-dialog');
        dlg.querySelector('#resizeWidth').value = this.canvasWidth;
        dlg.querySelector('#resizeHeight').value = this.canvasHeight;
        dlg.style.display = 'block';
    },

    applyResize() {
        const dlg = this.overlay.querySelector('.svg-editor-resize-dialog');
        const w = parseInt(dlg.querySelector('#resizeWidth').value) || this.canvasWidth;
        const h = parseInt(dlg.querySelector('#resizeHeight').value) || this.canvasHeight;
        this.canvasWidth = w;
        this.canvasHeight = h;
        this.canvas.setDimensions({ width: w, height: h });
        this.canvas.setZoom(1);
        this.zoomLevel = 1;
        this._updateZoomDisplay();
        dlg.style.display = 'none';
        this._saveHistory();
        this._fitToScreen();
    },

    cancelResize() {
        this.overlay.querySelector('.svg-editor-resize-dialog').style.display = 'none';
    },

    // ============================================
    // グリッドトグル
    // ============================================
    toggleGrid() {
        this.gridEnabled = !this.gridEnabled;
        const btn = this.overlay.querySelector('[data-action="grid"]');
        if (btn) btn.classList.toggle('active', this.gridEnabled);
        this._updateGridOverlay();
    },

    // ============================================
    // SVGエクスポート
    // ============================================
    exportSvg() {
        if (!this.canvas) return '';

        // ズームを一時的にリセット
        const prevZoom = this.canvas.getZoom();
        this.canvas.setZoom(1);
        this.canvas.setDimensions({ width: this.canvasWidth, height: this.canvasHeight });

        let svg = this.canvas.toSVG({
            viewBox: { x: 0, y: 0, width: this.canvasWidth, height: this.canvasHeight },
            width: this.canvasWidth,
            height: this.canvasHeight,
        });

        // ズーム復元
        this.canvas.setZoom(prevZoom);
        this._resizeCanvasForZoom();

        // Fabric.jsメタデータ除去
        svg = svg.replace(/<!--.*?-->/gs, '');

        // 矢印マーカー用defs注入
        const arrows = this.canvas.getObjects().filter(o => o._isArrow);
        if (arrows.length > 0) {
            // 使用されている色ごとにマーカーを生成
            const colors = [...new Set(arrows.map(o => o._markerStroke || o.stroke || '#333'))];
            let defsContent = '';
            colors.forEach((color, i) => {
                const markerId = i === 0 ? 'arr2' : `arr2_${i}`;
                defsContent += `  <marker id="${markerId}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
    <path d="M2 1L8 5L2 9" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
  </marker>\n`;
            });
            const markerDef = `<defs>\n${defsContent}</defs>`;
            svg = svg.replace(/<svg([^>]*)>/, `<svg$1>\n${markerDef}`);
        }

        // 不要な空行を整理
        svg = svg.replace(/\n\s*\n/g, '\n');

        return svg;
    },

    // ============================================
    // サーバーに保存（形式別分岐）
    // ============================================
    async save() {
        try {
            if (this.imageMode === 'raster') {
                await this._saveImage();
            } else {
                await this._saveSvg();
            }
        } catch (e) {
            this._showToast('保存エラー: ' + e.message);
            console.error('Save error:', e);
        }
    },

    // URL置換＋ページ保存の共通処理
    async _replaceUrlAndSavePage(originalFilename, newUrl) {
        const textarea = document.getElementById('content');
        if (textarea && newUrl !== `/attach/${originalFilename}`) {
            const oldUrl = `/attach/${originalFilename}`;
            const oldThumbUrl = `/attach/s_${originalFilename}`;
            const newFilename = newUrl.split('/').pop();
            const newThumbUrl = `/attach/s_${newFilename}`;

            textarea.value = textarea.value
                .replace(new RegExp(oldThumbUrl.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), newThumbUrl)
                .replace(new RegExp(oldUrl.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), newUrl);

            textarea.dispatchEvent(new Event('input'));
            this.originalSvgUrl = newUrl;
        }

        if (typeof window.saveWithoutRedirect === 'function') {
            await window.saveWithoutRedirect();
        }

        this._showToast('保存しました');
    },

    // SVG保存
    async _saveSvg() {
        const svgContent = this.exportSvg();
        if (!svgContent) return;

        const csrfToken = document.body.dataset.csrfToken;
        const urlParts = this.originalSvgUrl.split('/');
        const originalFilename = urlParts[urlParts.length - 1];

        const response = await fetch('/attach_save_svg', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ svg_content: svgContent, filename: originalFilename }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || 'Save failed');
        }

        const data = await response.json();
        await this._replaceUrlAndSavePage(originalFilename, data.url);
    },

    // ラスター画像エクスポート
    exportImage() {
        const prevZoom = this.canvas.getZoom();
        this.canvas.setZoom(1);
        this.canvas.setDimensions({ width: this.canvasWidth, height: this.canvasHeight });

        const isJpeg = /\.(jpg|jpeg)(\?|$)/i.test(this.originalSvgUrl);
        const format = isJpeg ? 'jpeg' : 'png';
        const quality = isJpeg ? 0.92 : undefined;
        const dataUrl = this.canvas.toDataURL({ format: format, quality: quality, multiplier: 1 });

        this.canvas.setZoom(prevZoom);
        this._resizeCanvasForZoom();

        return { dataUrl, format };
    },

    // ラスター画像保存
    async _saveImage() {
        const { dataUrl, format } = this.exportImage();
        const csrfToken = document.body.dataset.csrfToken;
        const urlParts = this.originalSvgUrl.split('/');
        const originalFilename = urlParts[urlParts.length - 1];

        const response = await fetch('/attach_save_image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ image_data: dataUrl, filename: originalFilename, format: format }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.error || 'Save failed');
        }

        const data = await response.json();
        await this._replaceUrlAndSavePage(originalFilename, data.url);
    },

    // ============================================
    // トースト通知
    // ============================================
    _showToast(msg) {
        let toast = document.querySelector('.svg-editor-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.className = 'svg-editor-toast';
            document.body.appendChild(toast);
        }
        toast.textContent = msg;
        toast.classList.add('show');
        clearTimeout(toast._timer);
        toast._timer = setTimeout(() => toast.classList.remove('show'), 2000);
    },

    // ============================================
    // プロパティパネル
    // ============================================
    _updatePropsPanel() {
        const panel = this.propsPanel;
        if (!panel) return;

        const active = this.canvas?.getActiveObject();
        if (!active || active.type === 'activeSelection') {
            const count = active ? active.getObjects().length : 0;
            panel.innerHTML = count > 1
                ? `<p class="prop-empty">${count}個のオブジェクトを選択中</p>`
                : '<p class="prop-empty">要素を選択してください</p>';
            return;
        }

        const obj = active;
        const isText = obj.type === 'i-text' || obj.type === 'textbox' || obj.type === 'text';
        const isShape = obj.type === 'rect' || obj.type === 'ellipse' || obj.type === 'circle';
        const isLine = obj.type === 'line';

        let html = '<h6>位置・サイズ</h6>';
        html += this._propRow('X', 'number', 'propX', Math.round(obj.left));
        html += this._propRow('Y', 'number', 'propY', Math.round(obj.top));
        if (!isLine) {
            html += this._propRow('W', 'number', 'propW', Math.round(obj.getScaledWidth()));
            html += this._propRow('H', 'number', 'propH', Math.round(obj.getScaledHeight()));
        }

        html += '<h6>スタイル</h6>';
        if (obj.fill !== undefined && !isLine) {
            html += this._propRow('塗り', 'color', 'propFill', obj.fill || '#ffffff');
        }
        if (obj.stroke !== undefined) {
            html += this._propRow('線色', 'color', 'propStroke', obj.stroke || '#000000');
        }
        html += this._propRow('線幅', 'number', 'propStrokeW', obj.strokeWidth ?? 1, 'min="0" max="20" step="0.5"');
        html += this._propRow('透明度', 'range', 'propOpacity', obj.opacity ?? 1, 'min="0" max="1" step="0.05"');

        if (isShape && obj.rx !== undefined) {
            html += this._propRow('角丸', 'number', 'propRx', obj.rx || 0, 'min="0" max="100"');
        }

        if (isText) {
            html += '<h6>テキスト</h6>';
            html += this._propRow('サイズ', 'number', 'propFontSize', obj.fontSize || 14, 'min="6" max="200"');
            html += `<div class="prop-row"><label>太さ</label><select id="propFontWeight">
                <option value="normal" ${obj.fontWeight === 'normal' || obj.fontWeight === 400 ? 'selected' : ''}>Normal</option>
                <option value="500" ${obj.fontWeight === '500' || obj.fontWeight === 500 ? 'selected' : ''}>Medium</option>
                <option value="bold" ${obj.fontWeight === 'bold' || obj.fontWeight === 700 ? 'selected' : ''}>Bold</option>
            </select></div>`;
            html += this._propRow('文字色', 'color', 'propTextFill', obj.fill || '#000000');
        }

        panel.innerHTML = html;
        this._bindProps(obj);
    },

    _propRow(label, type, id, value, attrs) {
        attrs = attrs || '';
        if (type === 'color') {
            return `<div class="prop-row"><label>${label}</label><input type="color" id="${id}" value="${value}" ${attrs}></div>`;
        } else if (type === 'range') {
            return `<div class="prop-row"><label>${label}</label><input type="range" id="${id}" value="${value}" ${attrs}></div>`;
        }
        return `<div class="prop-row"><label>${label}</label><input type="number" id="${id}" value="${value}" ${attrs}></div>`;
    },

    _bindProps(obj) {
        const self = this;
        const bind = (id, setter) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('input', function() {
                setter(this.value);
                self.canvas.requestRenderAll();
            });
            el.addEventListener('change', function() {
                self._saveHistory();
            });
        };

        bind('propX', v => obj.set('left', parseFloat(v)));
        bind('propY', v => obj.set('top', parseFloat(v)));
        bind('propW', v => {
            const scale = parseFloat(v) / (obj.width || 1);
            obj.set('scaleX', scale);
        });
        bind('propH', v => {
            const scale = parseFloat(v) / (obj.height || 1);
            obj.set('scaleY', scale);
        });
        bind('propFill', v => obj.set('fill', v));
        bind('propStroke', v => obj.set('stroke', v));
        bind('propStrokeW', v => obj.set('strokeWidth', parseFloat(v)));
        bind('propOpacity', v => obj.set('opacity', parseFloat(v)));
        bind('propRx', v => { obj.set('rx', parseFloat(v)); obj.set('ry', parseFloat(v)); });
        bind('propFontSize', v => obj.set('fontSize', parseInt(v)));
        bind('propFontWeight', v => obj.set('fontWeight', v));
        bind('propTextFill', v => obj.set('fill', v));
    },

    // ============================================
    // ツールバー初期化
    // ============================================
    _initToolbar() {
        const self = this;
        // ツールボタン
        this.overlay.querySelectorAll('.tool-btn').forEach(btn => {
            btn.addEventListener('click', () => self.setTool(btn.dataset.tool));
        });
        // アクションボタン
        this.overlay.querySelectorAll('[data-action]').forEach(btn => {
            btn.addEventListener('click', () => {
                const action = btn.dataset.action;
                switch (action) {
                    case 'undo': self.undo(); break;
                    case 'redo': self.redo(); break;
                    case 'delete': self.deleteSelected(); break;
                    case 'copy': self.copy(); break;
                    case 'paste': self.paste(); break;
                    case 'bringFront': self.bringToFront(); break;
                    case 'sendBack': self.sendToBack(); break;
                    case 'bringForward': self.bringForward(); break;
                    case 'sendBackward': self.sendBackwards(); break;
                    case 'group': self.group(); break;
                    case 'ungroup': self.ungroup(); break;
                    case 'grid': self.toggleGrid(); break;
                    case 'resize': self.showResizeDialog(); break;
                    case 'zoomIn': self.zoomIn(); break;
                    case 'zoomOut': self.zoomOut(); break;
                    case 'save': self.save(); break;
                    case 'close': self.close(); break;
                }
            });
        });
        // 整列メニュー
        const alignBtn = this.overlay.querySelector('[data-action-menu="align"]');
        const alignMenu = this.overlay.querySelector('.svg-editor-align-menu');
        if (alignBtn && alignMenu) {
            alignBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                const rect = alignBtn.getBoundingClientRect();
                alignMenu.style.top = rect.bottom + 2 + 'px';
                alignMenu.style.left = rect.left + 'px';
                alignMenu.style.display = alignMenu.style.display === 'block' ? 'none' : 'block';
            });
            alignMenu.querySelectorAll('button').forEach(btn => {
                btn.addEventListener('click', () => {
                    self.align(btn.dataset.align);
                    alignMenu.style.display = 'none';
                });
            });
            document.addEventListener('click', () => { alignMenu.style.display = 'none'; });
        }
        // リサイズダイアログ
        const resizeOk = this.overlay.querySelector('#resizeOk');
        if (resizeOk) resizeOk.addEventListener('click', () => self.applyResize());
        const resizeCancel = this.overlay.querySelector('#resizeCancel');
        if (resizeCancel) resizeCancel.addEventListener('click', () => self.cancelResize());

        // プリセットカラーピッカー
        const presetFill = this.overlay.querySelector('#presetFill');
        if (presetFill) presetFill.addEventListener('input', (e) => { self.presetFillColor = e.target.value; });
        const presetStroke = this.overlay.querySelector('#presetStroke');
        if (presetStroke) presetStroke.addEventListener('input', (e) => {
            self.presetStrokeColor = e.target.value;
            if (self.canvas && self.canvas.isDrawingMode && self.currentTool === 'draw') {
                self.canvas.freeDrawingBrush.color = e.target.value;
            }
        });
        const presetText = this.overlay.querySelector('#presetTextColor');
        if (presetText) presetText.addEventListener('input', (e) => { self.presetTextColor = e.target.value; });

        // プリセット線幅
        const presetSW = this.overlay.querySelector('#presetStrokeWidth');
        if (presetSW) presetSW.addEventListener('change', (e) => {
            self.presetStrokeWidth = parseFloat(e.target.value);
            if (self.canvas && self.canvas.isDrawingMode && self.currentTool === 'draw') {
                self.canvas.freeDrawingBrush.width = self.presetStrokeWidth;
            }
        });

        // 矢印太さボタン
        this.overlay.querySelectorAll('.arrow-size').forEach(btn => {
            btn.addEventListener('click', () => {
                self.currentArrowSize = btn.dataset.arrowSize;
                self.overlay.querySelectorAll('.arrow-size').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });
    },

    // ============================================
    // キーボードショートカット
    // ============================================
    _initKeyboard() {
        const self = this;
        document.addEventListener('keydown', function(e) {
            // エディタが開いていない場合は無視
            if (self.overlay.style.display !== 'flex') return;

            // IText編集中はショートカットを制限
            const active = self.canvas?.getActiveObject();
            const isEditing = active && active.isEditing;

            // Space（パン）
            if (e.code === 'Space' && !isEditing) {
                e.preventDefault();
                self.spacePressed = true;
                self.canvasWrap.classList.add('tool-pan');
            }

            // Escape
            if (e.key === 'Escape') {
                if (isEditing) {
                    active.exitEditing();
                    self.canvas.requestRenderAll();
                } else if (self.canvas?.getActiveObject()) {
                    self.canvas.discardActiveObject();
                    self.canvas.requestRenderAll();
                } else {
                    self.close();
                }
                return;
            }

            // Ctrl/Cmd shortcuts
            if (e.ctrlKey || e.metaKey) {
                switch (e.key.toLowerCase()) {
                    case 'z':
                        if (!isEditing) { e.preventDefault(); if (e.shiftKey) self.redo(); else self.undo(); }
                        break;
                    case 'y':
                        if (!isEditing) { e.preventDefault(); self.redo(); }
                        break;
                    case 'c':
                        if (!isEditing) { e.preventDefault(); self.copy(); }
                        break;
                    case 'v':
                        if (!isEditing) { e.preventDefault(); self.paste(); }
                        break;
                    case 'a':
                        if (!isEditing) { e.preventDefault(); self.selectAll(); }
                        break;
                    case 's':
                        e.preventDefault(); self.save();
                        break;
                }
                return;
            }

            // Delete/Backspace
            if ((e.key === 'Delete' || e.key === 'Backspace') && !isEditing) {
                e.preventDefault();
                self.deleteSelected();
            }

            // 矢印キーでナッジ
            if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key) && !isEditing) {
                e.preventDefault();
                const obj = self.canvas?.getActiveObject();
                if (!obj) return;
                const step = e.shiftKey ? 10 : 1;
                switch (e.key) {
                    case 'ArrowUp': obj.set('top', obj.top - step); break;
                    case 'ArrowDown': obj.set('top', obj.top + step); break;
                    case 'ArrowLeft': obj.set('left', obj.left - step); break;
                    case 'ArrowRight': obj.set('left', obj.left + step); break;
                }
                obj.setCoords();
                self.canvas.requestRenderAll();
                self._saveHistory();
                self._updatePropsPanel();
            }
        });

        document.addEventListener('keyup', function(e) {
            if (self.overlay.style.display !== 'flex') return;
            if (e.code === 'Space') {
                self.spacePressed = false;
                self.canvasWrap.classList.remove('tool-pan');
            }
        });
    },
};

// ============================================
// DOMContentLoaded で初期化
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('svgEditorOverlay')) {
        svgEditor.init();
    }
});

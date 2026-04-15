// ============================================
// スライドショーモーダル機能（ズーム対応）
// ============================================
let slideshowImages = [];
let currentSlideIndex = 0;

// ペン状態（ペン関連はファイル末尾のIIFEで実装。ここではフラグのみ共有）
let slideshowPenActive = false;

// ズーム状態
let zoomScale = 1;
let panX = 0;
let panY = 0;

// マウスパン状態
let isMousePanning = false;
let mousePanStartX = 0;
let mousePanStartY = 0;
let mousePanStartPanX = 0;
let mousePanStartPanY = 0;
let mouseDownTime = 0;

// タッチ状態
let touchStartX = 0;
let touchEndX = 0;
let isTouchPanning = false;
let touchPanStartX = 0;
let touchPanStartY = 0;
let touchPanStartPanX = 0;
let touchPanStartPanY = 0;
let pinchStartDist = 0;
let pinchStartScale = 1;
let lastTapTime = 0;
let lastTapX = 0;
let lastTapY = 0;
let isPinching = false;

const ZOOM_MIN = 0.5;
const ZOOM_MAX = 5;
const ZOOM_STEP = 0.25;

// ============================================
// 初期化
// ============================================
function initializeSlideshowImages(containerSelector) {
    containerSelector = containerSelector || '#content';
    const contentImages = document.querySelectorAll(containerSelector + ' img');
    slideshowImages = [];

    contentImages.forEach((img, index) => {
        const parent = img.parentElement;
        let fullSizeUrl = img.src;

        if (parent.tagName === 'A' && parent.href.match(/\.(jpg|jpeg|png|gif|svg)$/i)) {
            fullSizeUrl = parent.href;
            parent.addEventListener('click', function(e) {
                e.preventDefault();
                openSlideshowModal(index);
            });
        } else {
            img.style.cursor = 'pointer';
            img.addEventListener('click', function() {
                openSlideshowModal(index);
            });
        }

        slideshowImages.push({
            thumb: img.src,
            full: fullSizeUrl,
            alt: img.alt || ''
        });
    });
}

// ============================================
// モーダル開閉
// ============================================
function openSlideshowModal(index) {
    currentSlideIndex = index;
    const modal = document.getElementById('slideshow-modal');
    if (!modal) {
        console.error('slideshow-modal element not found');
        return;
    }
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
    resetZoom();
    showCurrentSlide();
    if (typeof window.slideshowPenSetOff === 'function') window.slideshowPenSetOff();
    if (typeof window.slideshowPenClear === 'function') window.slideshowPenClear();
    if (typeof window.slideshowPenResize === 'function') {
        requestAnimationFrame(window.slideshowPenResize);
    }
}

function closeSlideshowModal() {
    const modal = document.getElementById('slideshow-modal');
    if (!modal) return;

    modal.classList.remove('active');
    document.body.style.overflow = '';
    resetZoom();
    if (typeof window.slideshowPenSetOff === 'function') window.slideshowPenSetOff();
    if (typeof window.slideshowPenClear === 'function') window.slideshowPenClear();
}

// ============================================
// スライドナビゲーション
// ============================================
function navigateSlideshow(direction) {
    currentSlideIndex += direction;
    if (currentSlideIndex < 0) {
        currentSlideIndex = slideshowImages.length - 1;
    } else if (currentSlideIndex >= slideshowImages.length) {
        currentSlideIndex = 0;
    }
    resetZoom();
    showCurrentSlide();
    if (typeof window.slideshowPenClear === 'function') window.slideshowPenClear();
}

function preloadAdjacentImages(index) {
    if (slideshowImages.length === 0) return;
    const prevIndex = (index - 1 + slideshowImages.length) % slideshowImages.length;
    const nextIndex = (index + 1) % slideshowImages.length;

    if (slideshowImages[prevIndex]) {
        const prevImg = new Image();
        prevImg.src = slideshowImages[prevIndex].full;
    }
    if (slideshowImages[nextIndex]) {
        const nextImg = new Image();
        nextImg.src = slideshowImages[nextIndex].full;
    }
}

function showCurrentSlide() {
    if (slideshowImages.length === 0) return;

    const img = document.getElementById('slideshow-image');
    const counter = document.getElementById('slideshow-counter');
    if (!img || !counter) return;

    const currentImage = slideshowImages[currentSlideIndex];

    img.style.opacity = '0';

    setTimeout(() => {
        const tempImg = new Image();
        tempImg.onload = function() {
            img.src = currentImage.full;
            img.alt = currentImage.alt;
            img.style.opacity = '1';
        };
        tempImg.onerror = function() {
            img.src = currentImage.full;
            img.alt = currentImage.alt;
            img.style.opacity = '1';
        };
        tempImg.src = currentImage.full;
    }, 150);

    counter.textContent = `${currentSlideIndex + 1} / ${slideshowImages.length}`;
    preloadAdjacentImages(currentSlideIndex);

    // SVG編集ボタンの表示制御
    const editSvgBtn = document.getElementById('slideshowEditSvgBtn');
    if (editSvgBtn) {
        const isEditable = currentImage.full && currentImage.full.match(/\/attach\/[a-f0-9]+\.(svg|jpg|jpeg|png|gif)(\?|$)/i);
        editSvgBtn.style.display = isEditable ? 'inline-block' : 'none';
    }
}

// ============================================
// ズーム機能
// ============================================
function resetZoom() {
    zoomScale = 1;
    panX = 0;
    panY = 0;
    applyTransform();
}

function applyTransform() {
    const img = document.getElementById('slideshow-image');
    if (!img) return;

    if (typeof window.slideshowPenClear === 'function') window.slideshowPenClear();

    if (zoomScale <= 1.01 && Math.abs(panX) < 1 && Math.abs(panY) < 1) {
        zoomScale = 1;
        panX = 0;
        panY = 0;
        img.style.transform = '';
        img.classList.remove('zoomed');
    } else {
        img.style.transform = 'translate(' + panX + 'px, ' + panY + 'px) scale(' + zoomScale + ')';
        img.classList.add('zoomed');
    }
    updateZoomLevel();
}

function updateZoomLevel() {
    const el = document.getElementById('slideshow-zoom-level');
    if (el) {
        el.textContent = Math.round(zoomScale * 100) + '%';
    }
}

/**
 * 指定座標を中心にズーム
 * transform-origin: 0 0 での計算:
 *   newPanX = panX + (cx - rect.left) * (1 - newScale/zoomScale)
 */
function zoomAtPoint(newScale, cx, cy) {
    newScale = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, newScale));

    const img = document.getElementById('slideshow-image');
    if (!img) return;

    const rect = img.getBoundingClientRect();
    const ratio = newScale / zoomScale;

    panX = panX + (cx - rect.left) * (1 - ratio);
    panY = panY + (cy - rect.top) * (1 - ratio);
    zoomScale = newScale;

    if (zoomScale <= 1.01) {
        resetZoom();
        return;
    }

    applyTransform();
}

/** ボタン操作用：画像中心を基準にズーム */
function zoomByStep(step) {
    const img = document.getElementById('slideshow-image');
    if (!img) return;
    const rect = img.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    zoomAtPoint(zoomScale + step, cx, cy);
}

function slideshowZoomIn() {
    zoomByStep(ZOOM_STEP);
}

function slideshowZoomOut() {
    zoomByStep(-ZOOM_STEP);
}

function slideshowResetZoom() {
    resetZoom();
}

// ============================================
// マウスホイールズーム
// ============================================
function handleWheelZoom(e) {
    const modal = document.getElementById('slideshow-modal');
    if (!modal || !modal.classList.contains('active')) return;
    if (slideshowPenActive) return;

    e.preventDefault();
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    const newScale = zoomScale * factor;
    zoomAtPoint(newScale, e.clientX, e.clientY);
}

// ============================================
// ダブルクリックでズームトグル
// ============================================
function handleImageDoubleClick(e) {
    if (slideshowPenActive) return;
    e.preventDefault();
    e.stopPropagation();

    if (zoomScale > 1.05) {
        resetZoom();
    } else {
        zoomAtPoint(2, e.clientX, e.clientY);
    }
}

// ============================================
// マウスドラッグでパン
// ============================================
function handleMouseDown(e) {
    if (slideshowPenActive) return;
    // 画像上でのみパン開始
    if (e.target.id !== 'slideshow-image') return;
    if (e.button !== 0) return; // 左クリックのみ

    mouseDownTime = Date.now();

    if (zoomScale > 1.01) {
        isMousePanning = true;
        mousePanStartX = e.clientX;
        mousePanStartY = e.clientY;
        mousePanStartPanX = panX;
        mousePanStartPanY = panY;

        const img = document.getElementById('slideshow-image');
        if (img) img.classList.add('panning');
        e.preventDefault();
    }
}

function handleMouseMove(e) {
    if (!isMousePanning) return;

    panX = mousePanStartPanX + (e.clientX - mousePanStartX);
    panY = mousePanStartPanY + (e.clientY - mousePanStartY);
    applyTransform();
}

function handleMouseUp(e) {
    if (isMousePanning) {
        isMousePanning = false;
        const img = document.getElementById('slideshow-image');
        if (img) img.classList.remove('panning');
    }
}

// ============================================
// タッチイベント（スワイプ + ピンチズーム + パン）
// ============================================
function handleTouchStart(e) {
    if (slideshowPenActive) return;
    if (e.touches.length === 2) {
        // ピンチ開始
        isPinching = true;
        isTouchPanning = false;
        const t1 = e.touches[0];
        const t2 = e.touches[1];
        pinchStartDist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY);
        pinchStartScale = zoomScale;
        e.preventDefault();
        return;
    }

    if (e.touches.length === 1) {
        const t = e.touches[0];
        const now = Date.now();

        // ダブルタップ検出
        if (now - lastTapTime < 300 &&
            Math.abs(t.clientX - lastTapX) < 30 &&
            Math.abs(t.clientY - lastTapY) < 30) {
            e.preventDefault();
            lastTapTime = 0;
            if (zoomScale > 1.05) {
                resetZoom();
            } else {
                zoomAtPoint(2, t.clientX, t.clientY);
            }
            return;
        }
        lastTapTime = now;
        lastTapX = t.clientX;
        lastTapY = t.clientY;

        // ズーム中は1本指パン
        if (zoomScale > 1.05) {
            isTouchPanning = true;
            touchPanStartX = t.clientX;
            touchPanStartY = t.clientY;
            touchPanStartPanX = panX;
            touchPanStartPanY = panY;
        } else {
            // 等倍時はスワイプ用に記録
            isTouchPanning = false;
            touchStartX = t.screenX;
        }
    }
}

function handleTouchMove(e) {
    if (slideshowPenActive) return;
    if (e.touches.length === 2 && isPinching) {
        e.preventDefault();
        const t1 = e.touches[0];
        const t2 = e.touches[1];
        const dist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY);
        const newScale = pinchStartScale * (dist / pinchStartDist);

        const cx = (t1.clientX + t2.clientX) / 2;
        const cy = (t1.clientY + t2.clientY) / 2;
        zoomAtPoint(newScale, cx, cy);
        return;
    }

    if (e.touches.length === 1 && isTouchPanning) {
        e.preventDefault();
        const t = e.touches[0];
        panX = touchPanStartPanX + (t.clientX - touchPanStartX);
        panY = touchPanStartPanY + (t.clientY - touchPanStartY);
        applyTransform();
    }
}

function handleTouchEnd(e) {
    if (isPinching) {
        isPinching = false;
        return;
    }

    if (isTouchPanning) {
        isTouchPanning = false;
        return;
    }

    // 等倍時のスワイプナビゲーション
    if (zoomScale <= 1.05 && e.changedTouches.length === 1) {
        touchEndX = e.changedTouches[0].screenX;
        handleSwipe();
    }
}

function handleSwipe() {
    const swipeThreshold = 50;
    const diff = touchStartX - touchEndX;

    if (Math.abs(diff) > swipeThreshold) {
        if (diff > 0) {
            navigateSlideshow(1);
        } else {
            navigateSlideshow(-1);
        }
    }
}

// ============================================
// SVGエディタ連携
// ============================================
function slideshowOpenSvgEditor() {
    if (slideshowImages.length === 0) return;
    const currentImage = slideshowImages[currentSlideIndex];
    if (!currentImage || !currentImage.full) return;

    // スライドショーを閉じてからSVGエディタを開く
    closeSlideshowModal();

    if (typeof svgEditor !== 'undefined') {
        svgEditor.open(currentImage.full);
    }
}

// ============================================
// DOMContentLoaded
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    // Markdownレンダリング完了後に初期化
    setTimeout(function() {
        const contentContainer = document.querySelector('#content');
        if (contentContainer && contentContainer.querySelectorAll('img').length > 0) {
            initializeSlideshowImages('#content');
        }
    }, 500);

    // キーボード操作
    document.addEventListener('keydown', function(e) {
        const modal = document.getElementById('slideshow-modal');
        if (!modal || !modal.classList.contains('active')) return;

        switch (e.key) {
            case 'ArrowLeft':
                navigateSlideshow(-1);
                break;
            case 'ArrowRight':
                navigateSlideshow(1);
                break;
            case 'Escape':
                closeSlideshowModal();
                break;
            case '+':
            case '=':
                e.preventDefault();
                slideshowZoomIn();
                break;
            case '-':
                e.preventDefault();
                slideshowZoomOut();
                break;
            case '0':
                e.preventDefault();
                resetZoom();
                break;
            case 'p':
            case 'P':
                e.preventDefault();
                if (typeof window.slideshowPenToggle === 'function') {
                    window.slideshowPenToggle();
                }
                break;
        }
    });

    // マウスホイールズーム
    document.addEventListener('wheel', handleWheelZoom, { passive: false });

    // マウスドラッグでパン
    document.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    // 背景クリックで閉じる
    const modal = document.getElementById('slideshow-modal');
    const container = document.getElementById('slideshow-container');

    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                closeSlideshowModal();
            }
        });
    }

    if (container) {
        container.addEventListener('click', function(e) {
            if (e.target === this) {
                closeSlideshowModal();
            }
        });

        // ダブルクリックズーム（画像上のみ）
        container.addEventListener('dblclick', function(e) {
            if (e.target.id === 'slideshow-image') {
                handleImageDoubleClick(e);
            }
        });

        // タッチイベント
        container.addEventListener('touchstart', handleTouchStart, { passive: false });
        container.addEventListener('touchmove', handleTouchMove, { passive: false });
        container.addEventListener('touchend', handleTouchEnd, { passive: false });
    }

    initSlideshowPen();
});

// ============================================
// ペン書き込み機能（スライドショーモーダル用）
// ============================================
function initSlideshowPen() {
    const drawCanvas = document.getElementById('slideshowDrawCanvas');
    const container = document.getElementById('slideshow-container');
    if (!drawCanvas || !container) return;
    const drawCtx = drawCanvas.getContext('2d');

    let penColor = '#e00';
    let penWidth = 3;
    let isDrawingPen = false;
    let lastPenX = 0;
    let lastPenY = 0;

    function resize() {
        drawCanvas.width = container.clientWidth;
        drawCanvas.height = container.clientHeight;
    }

    function clear() {
        drawCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
    }

    function setOff() {
        slideshowPenActive = false;
        const btn = document.getElementById('slideshowPenToggle');
        const colors = document.getElementById('slideshowPenColors');
        if (btn) btn.classList.remove('active');
        if (colors) colors.style.display = 'none';
        drawCanvas.classList.remove('active');
    }

    function toggle() {
        slideshowPenActive = !slideshowPenActive;
        const btn = document.getElementById('slideshowPenToggle');
        const colors = document.getElementById('slideshowPenColors');
        if (btn) btn.classList.toggle('active', slideshowPenActive);
        if (colors) colors.style.display = slideshowPenActive ? 'inline-flex' : 'none';
        drawCanvas.classList.toggle('active', slideshowPenActive);
        if (slideshowPenActive) resize();
    }

    function coords(clientX, clientY) {
        const rect = drawCanvas.getBoundingClientRect();
        return { x: clientX - rect.left, y: clientY - rect.top };
    }

    function drawLine(x, y) {
        drawCtx.beginPath();
        drawCtx.moveTo(lastPenX, lastPenY);
        drawCtx.lineTo(x, y);
        drawCtx.strokeStyle = penColor;
        drawCtx.lineWidth = penWidth;
        drawCtx.lineCap = 'round';
        drawCtx.lineJoin = 'round';
        drawCtx.stroke();
        lastPenX = x;
        lastPenY = y;
    }

    drawCanvas.addEventListener('mousedown', function(e) {
        if (!slideshowPenActive) return;
        e.stopPropagation();
        isDrawingPen = true;
        const p = coords(e.clientX, e.clientY);
        lastPenX = p.x;
        lastPenY = p.y;
    });
    drawCanvas.addEventListener('mousemove', function(e) {
        if (!isDrawingPen || !slideshowPenActive) return;
        const p = coords(e.clientX, e.clientY);
        drawLine(p.x, p.y);
    });
    drawCanvas.addEventListener('mouseup', function() { isDrawingPen = false; });
    drawCanvas.addEventListener('mouseleave', function() { isDrawingPen = false; });

    drawCanvas.addEventListener('touchstart', function(e) {
        if (!slideshowPenActive) return;
        e.preventDefault();
        e.stopPropagation();
        isDrawingPen = true;
        const t = e.touches[0];
        const p = coords(t.clientX, t.clientY);
        lastPenX = p.x;
        lastPenY = p.y;
    }, { passive: false });
    drawCanvas.addEventListener('touchmove', function(e) {
        if (!isDrawingPen || !slideshowPenActive) return;
        e.preventDefault();
        const t = e.touches[0];
        const p = coords(t.clientX, t.clientY);
        drawLine(p.x, p.y);
    }, { passive: false });
    drawCanvas.addEventListener('touchend', function() { isDrawingPen = false; });

    const toggleBtn = document.getElementById('slideshowPenToggle');
    if (toggleBtn) toggleBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        toggle();
    });

    const clearBtn = document.getElementById('slideshowPenClear');
    if (clearBtn) clearBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        clear();
    });

    const thickBtn = document.getElementById('slideshowPenThick');
    if (thickBtn) {
        thickBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            penWidth = penWidth === 3 ? 8 : penWidth === 8 ? 16 : 3;
            const icon = this.querySelector('i');
            if (icon) icon.style.fontSize = penWidth === 3 ? '6px' : penWidth === 8 ? '10px' : '16px';
        });
    }

    document.querySelectorAll('#slideshowPenColors .slide-pen-color').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            penColor = this.dataset.color;
            document.querySelectorAll('#slideshowPenColors .slide-pen-color').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
        });
    });

    window.addEventListener('resize', function() {
        if (document.getElementById('slideshow-modal').classList.contains('active')) {
            resize();
            clear();
        }
    });

    // 公開API
    window.slideshowPenToggle = toggle;
    window.slideshowPenSetOff = setOff;
    window.slideshowPenClear = clear;
    window.slideshowPenResize = resize;
}

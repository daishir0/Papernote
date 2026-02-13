// ============================================
// スライドショーモーダル機能（ズーム対応）
// ============================================
let slideshowImages = [];
let currentSlideIndex = 0;

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
}

function closeSlideshowModal() {
    const modal = document.getElementById('slideshow-modal');
    if (!modal) return;

    modal.classList.remove('active');
    document.body.style.overflow = '';
    resetZoom();
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

    e.preventDefault();
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    const newScale = zoomScale * factor;
    zoomAtPoint(newScale, e.clientX, e.clientY);
}

// ============================================
// ダブルクリックでズームトグル
// ============================================
function handleImageDoubleClick(e) {
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
});

// ============================================
// スライドショーモーダル機能
// ============================================
let slideshowImages = [];
let currentSlideIndex = 0;
let touchStartX = 0;
let touchEndX = 0;

// 初期化関数（外部から呼び出し可能）
function initializeSlideshowImages(containerSelector) {
    containerSelector = containerSelector || '#content';

    // コンテンツ内の全画像を取得（サムネイル画像のみ）
    const contentImages = document.querySelectorAll(containerSelector + ' img');
    slideshowImages = [];

    contentImages.forEach((img, index) => {
        // 親要素がaタグか確認
        const parent = img.parentElement;
        let fullSizeUrl = img.src;

        // 親がaタグで、hrefが画像URLの場合はそれを使用
        if (parent.tagName === 'A' && parent.href.match(/\.(jpg|jpeg|png|gif)$/i)) {
            fullSizeUrl = parent.href;
            // aタグのデフォルト動作を防ぐ
            parent.addEventListener('click', function(e) {
                e.preventDefault();
                openSlideshowModal(index);
            });
        } else {
            // 直接画像をクリック
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

function openSlideshowModal(index) {
    currentSlideIndex = index;
    const modal = document.getElementById('slideshow-modal');
    if (!modal) {
        console.error('slideshow-modal element not found');
        return;
    }
    modal.classList.add('active');
    document.body.style.overflow = 'hidden'; // 背景スクロール無効化
    showCurrentSlide();

    // スワイプイベントリスナー追加（スマホ用）
    const container = document.getElementById('slideshow-container');
    if (container) {
        container.addEventListener('touchstart', handleTouchStart, false);
        container.addEventListener('touchend', handleTouchEnd, false);
    }
}

function closeSlideshowModal() {
    const modal = document.getElementById('slideshow-modal');
    if (!modal) return;

    modal.classList.remove('active');
    document.body.style.overflow = ''; // 背景スクロール復元

    // イベントリスナー削除
    const container = document.getElementById('slideshow-container');
    if (container) {
        container.removeEventListener('touchstart', handleTouchStart);
        container.removeEventListener('touchend', handleTouchEnd);
    }
}

function navigateSlideshow(direction) {
    currentSlideIndex += direction;

    // ループ処理
    if (currentSlideIndex < 0) {
        currentSlideIndex = slideshowImages.length - 1;
    } else if (currentSlideIndex >= slideshowImages.length) {
        currentSlideIndex = 0;
    }

    showCurrentSlide();
}

// 前後の画像を先読み（プリロード）する関数
function preloadAdjacentImages(index) {
    if (slideshowImages.length === 0) return;

    // 前の画像のインデックス（ループ対応）
    const prevIndex = (index - 1 + slideshowImages.length) % slideshowImages.length;
    // 次の画像のインデックス（ループ対応）
    const nextIndex = (index + 1) % slideshowImages.length;

    // 前の画像をプリロード
    if (slideshowImages[prevIndex]) {
        const prevImg = new Image();
        prevImg.src = slideshowImages[prevIndex].full;
    }

    // 次の画像をプリロード
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

    // フェードアウト
    img.style.opacity = '0';

    setTimeout(() => {
        // 新しい画像のロード完了を待つ
        const tempImg = new Image();
        tempImg.onload = function() {
            // ロード完了後に表示
            img.src = currentImage.full;
            img.alt = currentImage.alt;
            img.style.opacity = '1';
        };
        tempImg.onerror = function() {
            // エラー時も表示を試みる
            img.src = currentImage.full;
            img.alt = currentImage.alt;
            img.style.opacity = '1';
        };
        tempImg.src = currentImage.full;  // ダウンロード開始
    }, 150);

    counter.textContent = `${currentSlideIndex + 1} / ${slideshowImages.length}`;

    // 前後の画像を先読み
    preloadAdjacentImages(currentSlideIndex);
}

// タッチイベント処理（スワイプ検知）
function handleTouchStart(e) {
    touchStartX = e.changedTouches[0].screenX;
}

function handleTouchEnd(e) {
    touchEndX = e.changedTouches[0].screenX;
    handleSwipe();
}

function handleSwipe() {
    const swipeThreshold = 50; // 最小スワイプ距離
    const diff = touchStartX - touchEndX;

    if (Math.abs(diff) > swipeThreshold) {
        if (diff > 0) {
            // 左スワイプ → 次の画像
            navigateSlideshow(1);
        } else {
            // 右スワイプ → 前の画像
            navigateSlideshow(-1);
        }
    }
}

// DOMContentLoaded後に初期化（post.html用）
document.addEventListener('DOMContentLoaded', function() {
    // Markdownレンダリング完了後に実行するため、遅延させる
    setTimeout(function() {
        const contentContainer = document.querySelector('#content');
        // #contentが存在し、かつその中に画像がある場合のみ初期化
        if (contentContainer && contentContainer.querySelectorAll('img').length > 0) {
            initializeSlideshowImages('#content');
        }
    }, 500);

    // キーボード操作
    document.addEventListener('keydown', function(e) {
        const modal = document.getElementById('slideshow-modal');
        if (!modal || !modal.classList.contains('active')) return;

        if (e.key === 'ArrowLeft') {
            navigateSlideshow(-1);
        } else if (e.key === 'ArrowRight') {
            navigateSlideshow(1);
        } else if (e.key === 'Escape') {
            closeSlideshowModal();
        }
    });

    // 背景クリックで閉じる（改善版）
    const modal = document.getElementById('slideshow-modal');
    const container = document.getElementById('slideshow-container');

    if (modal) {
        // モーダル背景をクリックした時
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                closeSlideshowModal();
            }
        });
    }

    if (container) {
        // コンテナの空白部分をクリックした時
        container.addEventListener('click', function(e) {
            // 画像、ボタン、カウンター以外をクリックした場合に閉じる
            if (e.target === this) {
                closeSlideshowModal();
            }
        });
    }
});

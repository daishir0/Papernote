#!/usr/bin/env python3
"""
HEIC変換機能のテストスクリプト
実行方法: python test_heic_support.py
"""

import sys
from PIL import Image

def test_heic_library():
    """pillow-heifライブラリの動作確認"""
    print("=" * 60)
    print("📸 HEIC変換機能テスト")
    print("=" * 60)

    try:
        from pillow_heif import register_heif_opener
        print("✅ pillow-heif ライブラリ: インストール済み")

        # HEIFサポートを有効化
        register_heif_opener()
        print("✅ HEIF Opener: 登録成功")

        # PILがサポートしているフォーマットを確認
        supported_formats = Image.registered_extensions()
        heic_formats = {ext: fmt for ext, fmt in supported_formats.items() if 'heif' in fmt.lower() or 'heic' in fmt.lower()}

        if heic_formats:
            print(f"✅ サポート形式: {heic_formats}")
        else:
            print("⚠️  HEIC形式が登録されていない可能性があります")

        print("\n" + "=" * 60)
        print("🎉 すべてのチェックが完了しました！")
        print("=" * 60)
        print("\n📝 次のステップ:")
        print("  1. HEICファイルをedit_postページにDrag&Drop")
        print("  2. 自動的にJPEG形式に変換されます")
        print("  3. ブラウザで正常に表示されることを確認")
        print("\n💡 テストファイルがない場合:")
        print("  - iPhoneで撮影した写真（.heic）を使用")
        print("  - または https://heic.online/ で変換ツールを利用")
        print()

        return True

    except ImportError as e:
        print(f"❌ エラー: {e}")
        print("\n📦 修正方法:")
        print("  conda activate 311")
        print("  pip install pillow-heif")
        return False
    except Exception as e:
        print(f"❌ 予期しないエラー: {e}")
        return False

if __name__ == "__main__":
    success = test_heic_library()
    sys.exit(0 if success else 1)

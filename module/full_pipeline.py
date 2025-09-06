# module/full_pipeline.py
########## [Script Entry Point] パス設定ブロック - 開始 ##########
import sys
import os

if __name__ == "__main__" and __package__ is None:
    # スクリプトが直接実行された場合、プロジェクトのルートディレクトリをsys.pathに追加
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "../")) # 1階層下の場合
    sys.path.insert(0, project_root)
########## [Script Entry Point] パス設定ブロック - 終了 ##########

import shutil
from pathlib import Path
from typing import Dict, Optional

# 絶対パスでインポート
from module.sub.a_create_timestamps import create_timestamps
from module.sub.b_convert_to_rosvot import convert_to_rosvot_format, validate_rosvot_metadata
from module.sub.c_rosvot_to_midi import rosvot_to_midi

class FullPipeline:
    """完全な自動パイプライン統合クラス"""
    
    def __init__(self, output_base_dir: str = "output"):
        self.output_base_dir = Path(output_base_dir)
    
    def run_complete_pipeline(self, wav_path: str, lyrics_text: str) -> Dict[str, any]:
        """
        完全なパイプラインを実行
        
        Args:
            wav_path: 音声ファイルのパス
            lyrics_text: 歌詞テキスト
            
        Returns:
            results: 実行結果の辞書
        """
        results = {
            'success': False,
            'timestamps': None,
            'rosvot_metadata': None,
            'midi_path': None,
            'errors': []
        }
        
        try:
            item_name = Path(wav_path).stem.replace(' ', '_').replace('(', '').replace(')', '')
            output_dir = self.output_base_dir / item_name
            
            print("=" * 60)
            print("🎵 完全自動パイプライン開始")
            print("=" * 60)
            print(f"📁 入力WAV: {wav_path}")
            print(f"📝 歌詞: {lyrics_text}")
            print(f"📂 出力ディレクトリ: {output_dir}")
            print()
            
            # ステップ1: タイムスタンプ作成
            print("🔄 ステップ1: 音声ファイルと歌詞からタイムスタンプ作成")
            print("-" * 50)
            
            timestamps, textgrid_path = create_timestamps(wav_path, lyrics_text)
            
            if not timestamps:
                results['errors'].append("タイムスタンプ作成に失敗しました")
                return results
            
            results['timestamps'] = timestamps
            
            # TextGridファイルを保存
            if textgrid_path and Path(textgrid_path).exists():
                textgrid_output_path = output_dir / "a_textgrid.TextGrid"
                output_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(textgrid_path, textgrid_output_path)
                print(f"   📁 TextGridファイル保存: {textgrid_output_path}")
            
            print(f"✅ タイムスタンプ作成完了")
            print(f"   単語数: {len(timestamps.get('words', []))}")
            print(f"   音素数: {len(timestamps.get('phonemes', []))}")
            print(f"   有効な単語持続時間数: {len(timestamps.get('word_durations', []))}")
            print()
            
            # ステップ2: ROSVOT形式変換
            print("🔄 ステップ2: タイムスタンプをROSVOT形式に変換")
            print("-" * 50)
            
            rosvot_metadata = convert_to_rosvot_format(timestamps, wav_path)
            
            if not rosvot_metadata:
                results['errors'].append("ROSVOT形式変換に失敗しました")
                return results
            
            # メタデータを検証
            if not validate_rosvot_metadata(rosvot_metadata):
                results['errors'].append("ROSVOTメタデータの検証に失敗しました")
                return results
            
            results['rosvot_metadata'] = rosvot_metadata
            print(f"✅ ROSVOT形式変換完了")
            print(f"   アイテム名: {rosvot_metadata['item_name']}")
            print(f"   単語持続時間数: {len(rosvot_metadata['word_durs'])}")
            print()
            
            # ステップ3: ROSVOT実行→MIDI変換
            print("🔄 ステップ3: ROSVOTを実行してMIDIファイルを生成")
            print("-" * 50)
            
            midi_path = rosvot_to_midi(rosvot_metadata, output_dir)
            
            if not midi_path:
                results['errors'].append("ROSVOT→MIDI変換に失敗しました")
                return results
            
            results['midi_path'] = midi_path
            print(f"✅ MIDI変換完了")
            print(f"   生成されたMIDIファイル: {midi_path}")
            
            # ファイルサイズを確認
            if Path(midi_path).exists():
                file_size = Path(midi_path).stat().st_size
                print(f"   MIDIファイルサイズ: {file_size} bytes")
            print()
            
            results['success'] = True
            
            print("=" * 60)
            print("🎉 パイプライン完了!")
            print("=" * 60)
            print("📊 生成されたファイル:")
            print(f"   🎼 MIDI: {results['midi_path']}")
            print()
            print("📈 統計情報:")
            print(f"   単語数: {len(timestamps.get('words', []))}")
            print(f"   音素数: {len(timestamps.get('phonemes', []))}")
            print(f"   有効な単語持続時間数: {len(timestamps.get('word_durations', []))}")
            print("=" * 60)
            
            return results
            
        except Exception as e:
            error_msg = f"パイプライン実行中にエラー: {e}"
            results['errors'].append(error_msg)
            print(f"❌ {error_msg}")
            return results
    
    def cleanup_intermediate_files(self, item_name: str):
        """中間生成物をクリーンアップ（NPYファイルなど不要なファイルを削除）"""
        try:
            output_dir = self.output_base_dir / item_name
            
            # 不要な拡張子のファイルを削除
            unwanted_extensions = ['.npy', '.pkl', '.tmp']
            
            for ext in unwanted_extensions:
                for file_path in output_dir.rglob(f"*{ext}"):
                    try:
                        file_path.unlink()
                        print(f"🗑️  削除: {file_path}")
                    except Exception as e:
                        print(f"削除失敗: {file_path} - {e}")
            
            print(f"✅ 中間ファイルのクリーンアップ完了: {output_dir}")
            print(f"📁 保持されたファイル:")
            for file_path in output_dir.iterdir():
                if file_path.is_file():
                    print(f"   📄 {file_path.name}")
            
        except Exception as e:
            print(f"クリーンアップエラー: {e}")

def run_pipeline(wav_path: str, lyrics_text: str) -> Optional[str]:
    """
    パイプラインを実行してMIDIファイルのパスを返す
    
    Args:
        wav_path: 音声ファイルのパス
        lyrics_text: 歌詞テキスト
        
    Returns:
        midi_path: 生成されたMIDIファイルのパス（失敗時はNone）
    """
    pipeline = FullPipeline()
    results = pipeline.run_complete_pipeline(wav_path, lyrics_text)
    
    if results['success']:
        # 中間ファイルをクリーンアップ
        item_name = Path(wav_path).stem.replace(' ', '_').replace('(', '').replace(')', '')
        pipeline.cleanup_intermediate_files(item_name)
        
        return results['midi_path']
    else:
        print("\n❌ パイプライン失敗:")
        for error in results['errors']:
            print(f"  - {error}")
        return None

def main():
    """メイン処理"""
    # サンプル値を設定
    wav_path = "dataset/チューリップ/raw/001_1 VOCALOID  tyu-rti.wav"
    lyrics_text = "さいた さいた チューリップの はなが ならんだ ならんだ あか しろ きいろ どの はなみても きれいだな"
    
    print("🎵 音声ファイルと歌詞から自動でMIDIファイルを生成")
    print(f"📁 入力WAV: {wav_path}")
    print(f"📝 歌詞: {lyrics_text}")
    print()
    
    # パイプラインを実行
    midi_path = run_pipeline(wav_path, lyrics_text)
    
    if midi_path:
        print(f"\n🎉 成功! MIDIファイルが生成されました: {midi_path}")
        
        # 最終確認
        if Path(midi_path).exists():
            file_size = Path(midi_path).stat().st_size
            print(f"📊 ファイルサイズ: {file_size} bytes")
            print(f"📂 ファイルパス: {Path(midi_path).absolute()}")
        else:
            print("⚠️  MIDIファイルが見つかりません")
    else:
        print("\n❌ MIDIファイルの生成に失敗しました")

if __name__ == "__main__":
    main()

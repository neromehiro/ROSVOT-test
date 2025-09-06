# module/sub/b_convert_to_rosvot.py
########## [Script Entry Point] パス設定ブロック - 開始 ##########
import sys
import os

if __name__ == "__main__" and __package__ is None:
    # スクリプトが直接実行された場合、プロジェクトのルートディレクトリをsys.pathに追加
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "../../")) # 2階層下の場合
    sys.path.insert(0, project_root)
########## [Script Entry Point] パス設定ブロック - 終了 ##########

import json
from pathlib import Path
from typing import Dict, List, Optional

def convert_to_rosvot_format(timestamps: Dict, wav_path: str) -> Dict:
    """
    タイムスタンプをROSVOT形式に変換
    
    Args:
        timestamps: タイムスタンプ情報の辞書
        wav_path: 音声ファイルのパス
        
    Returns:
        rosvot_metadata: ROSVOT形式のメタデータ
    """
    try:
        # アイテム名を生成（ファイル名から特殊文字を除去）
        item_name = Path(wav_path).stem.replace(' ', '_').replace('(', '').replace(')', '')
        
        # WAVファイルパスを絶対パスに変換
        abs_wav_path = os.path.abspath(wav_path)
        
        # 単語持続時間を取得
        word_durations = timestamps.get("word_durations", [])
        
        if not word_durations:
            print("警告: 有効な単語持続時間が見つかりません")
            return {}
        
        # ROSVOT形式のメタデータを作成
        rosvot_metadata = {
            "item_name": item_name,
            "wav_fn": abs_wav_path,
            "word_durs": word_durations
        }
        
        print(f"ROSVOT形式変換完了:")
        print(f"  アイテム名: {item_name}")
        print(f"  WAVファイル: {abs_wav_path}")
        print(f"  単語持続時間数: {len(word_durations)}")
        print(f"  単語持続時間（最初の5個）: {word_durations[:5]}")
        
        return rosvot_metadata
        
    except Exception as e:
        print(f"ROSVOT形式変換エラー: {e}")
        return {}

def create_debug_flat_midi(timestamps: Dict, output_path: str, debug_note: int = 60) -> bool:
    """
    デバッグ用にC4で平坦な単語のMIDIファイルを作成
    
    Args:
        timestamps: タイムスタンプ情報の辞書
        output_path: 出力MIDIファイルのパス
        debug_note: デバッグ用のMIDIノート番号（デフォルト: 60 = C4）
        
    Returns:
        success: 作成成功フラグ
    """
    try:
        # pretty_midiをインポート
        try:
            import pretty_midi
        except ImportError:
            print("pretty_midiがインストールされていません。pip install pretty_midiを実行してください。")
            return False
        
        # MIDIオブジェクトを作成
        midi = pretty_midi.PrettyMIDI()
        instrument = pretty_midi.Instrument(program=0)  # ピアノ
        
        # 単語データを取得
        words = timestamps.get("words", [])
        
        if not words:
            print("警告: 単語データが見つかりません")
            return False
        
        print(f"🎵 デバッグ用平坦MIDI作成開始 (ノート: {debug_note} = C4)")
        print(f"📊 単語数: {len(words)}")
        
        # 各単語をC4のノートとして追加
        note_count = 0
        for start_time, end_time, word in words:
            # 無音記号（SP, AP）や空文字列はスキップ
            if word in ("SP", "AP", ""):
                continue
            
            # 最小ノート長（50ms）を確保
            duration = end_time - start_time
            if duration < 0.05:
                continue
            
            # C4のノートを作成
            note = pretty_midi.Note(
                velocity=80,
                pitch=debug_note,
                start=start_time,
                end=end_time
            )
            instrument.notes.append(note)
            note_count += 1
            
            print(f"  ノート {note_count}: {start_time:.3f}s-{end_time:.3f}s ({word})")
        
        # MIDIファイルに楽器を追加
        midi.instruments.append(instrument)
        
        # 出力ディレクトリを作成
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # MIDIファイルを保存
        midi.write(output_path)
        
        print(f"✅ デバッグ用平坦MIDIファイルを作成: {output_path}")
        print(f"📊 作成されたノート数: {note_count}")
        print(f"🎵 MIDI終端時刻: {midi.get_end_time():.3f}秒")
        
        return True
        
    except Exception as e:
        print(f"デバッグ用MIDI作成エラー: {e}")
        return False

def create_rosvot_metadata_file(rosvot_metadata: Dict, output_path: str) -> bool:
    """
    ROSVOT形式のメタデータをJSONファイルとして保存
    
    Args:
        rosvot_metadata: ROSVOT形式のメタデータ
        output_path: 出力ファイルパス
        
    Returns:
        success: 保存成功フラグ
    """
    try:
        # メタデータを配列形式で保存（ROSVOTの要求形式）
        metadata_array = [rosvot_metadata]
        
        # 出力ディレクトリを作成
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # JSONファイルとして保存
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata_array, f, indent=2, ensure_ascii=False)
        
        print(f"ROSVOTメタデータファイルを保存: {output_path}")
        return True
        
    except Exception as e:
        print(f"ROSVOTメタデータファイル保存エラー: {e}")
        return False

def validate_rosvot_metadata(rosvot_metadata: Dict) -> bool:
    """
    ROSVOT形式のメタデータを検証
    
    Args:
        rosvot_metadata: ROSVOT形式のメタデータ
        
    Returns:
        valid: 検証結果
    """
    required_keys = ["item_name", "wav_fn", "word_durs"]
    
    for key in required_keys:
        if key not in rosvot_metadata:
            print(f"エラー: 必須キー '{key}' が見つかりません")
            return False
    
    # WAVファイルの存在確認
    wav_path = rosvot_metadata["wav_fn"]
    if not Path(wav_path).exists():
        print(f"エラー: WAVファイルが見つかりません: {wav_path}")
        return False
    
    # 単語持続時間の検証
    word_durs = rosvot_metadata["word_durs"]
    if not isinstance(word_durs, list) or len(word_durs) == 0:
        print("エラー: word_dursが空または無効です")
        return False
    
    # 持続時間の値を検証
    for i, dur in enumerate(word_durs):
        if not isinstance(dur, (int, float)) or dur <= 0:
            print(f"エラー: 無効な持続時間 word_durs[{i}] = {dur}")
            return False
    
    print("✅ ROSVOTメタデータの検証成功")
    return True

def find_latest_timestamps_file() -> Optional[str]:
    """最新のa_timestamps.jsonファイルを探す"""
    output_dir = Path("output")
    if not output_dir.exists():
        return None
    
    # 全てのa_timestamps.jsonファイルを探す
    timestamp_files = list(output_dir.glob("*/a_timestamps.json"))
    
    if not timestamp_files:
        return None
    
    # 最新のファイルを返す（更新時刻順）
    latest_file = max(timestamp_files, key=lambda f: f.stat().st_mtime)
    return str(latest_file)

def main():
    """メイン処理"""
    print("=== タイムスタンプをROSVOT形式に変換 ===")
    
    # 前のモジュールの成果物を自動で探す
    timestamps_file = find_latest_timestamps_file()
    
    if not timestamps_file:
        print("❌ a_timestamps.jsonファイルが見つかりません")
        print("🔗 先に以下を実行してください: python module/sub/a_create_timestamps.py")
        return None
    
    print(f"📁 入力ファイル: {timestamps_file}")
    
    # タイムスタンプファイルを読み込み
    try:
        with open(timestamps_file, 'r', encoding='utf-8') as f:
            timestamps = json.load(f)
    except Exception as e:
        print(f"❌ タイムスタンプファイル読み込みエラー: {e}")
        return None
    
    # WAVパスを推定（タイムスタンプファイルのディレクトリ名から）
    item_name = Path(timestamps_file).parent.name
    
    # 実際のWAVファイルを探す
    wav_dir = Path("dataset/チューリップ/raw/")
    wav_files = list(wav_dir.glob("*.wav"))
    
    # アイテム名に最も近いファイルを探す
    best_match = None
    for wav_file in wav_files:
        # ファイル名から拡張子を除去し、特殊文字を正規化
        file_stem = wav_file.stem.replace(' ', '_').replace('(', '').replace(')', '')
        if file_stem == item_name:
            best_match = wav_file
            break
    
    if best_match:
        wav_path = str(best_match)
    else:
        # フォールバック: 元の推定方法
        original_name = item_name.replace('__', '  ').replace('_', ' ')
        wav_path = f"dataset/チューリップ/raw/{original_name}.wav"
    
    print(f"📊 単語持続時間数: {len(timestamps.get('word_durations', []))}")
    print(f"🎵 推定WAVパス: {wav_path}")
    
    # ROSVOT形式に変換
    rosvot_metadata = convert_to_rosvot_format(timestamps, wav_path)
    
    if rosvot_metadata:
        # メタデータを検証
        if validate_rosvot_metadata(rosvot_metadata):
            print("\n✅ ROSVOT形式変換成功!")
            
            # 中間生成物を保存（if __name__ == "__main__"時のみ）
            output_dir = Path(timestamps_file).parent
            
            # 統一されたファイル名で保存
            metadata_path = output_dir / "b_rosvot_metadata.json"
            success = create_rosvot_metadata_file(rosvot_metadata, str(metadata_path))
            
            if success:
                print(f"📁 成果物を保存: {metadata_path}")
                
                # 保存されたファイルの内容を確認
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                print(f"📊 保存されたメタデータ: {saved_data[0]['item_name']}")
                
                # デバッグ用平坦MIDIファイルを作成
                debug_midi_path = output_dir / "b_debug_flat.mid"
                print(f"\n🎵 デバッグ用平坦MIDIファイルを作成中...")
                debug_success = create_debug_flat_midi(timestamps, str(debug_midi_path))
                
                if debug_success:
                    print(f"✅ デバッグ用MIDIファイルを保存: {debug_midi_path}")
                    print(f"🎹 全ての音素がC4（MIDIノート60）で配置されています")
                    print(f"🔍 このファイルでタイミングの確認ができます")
                else:
                    print(f"⚠️ デバッグ用MIDIファイルの作成に失敗しました")
                
                print(f"🔗 次のステップ: python module/sub/c_rosvot_to_midi.py")
                
                return rosvot_metadata
            else:
                print("❌ ROSVOTメタデータファイル保存失敗")
                return None
        else:
            print("❌ ROSVOTメタデータ検証失敗")
            return None
    else:
        print("\n❌ ROSVOT形式変換失敗")
        return None

if __name__ == "__main__":
    main()

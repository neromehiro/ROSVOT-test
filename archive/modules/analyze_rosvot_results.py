# modules/analyze_rosvot_results.py
import numpy as np
import json
from pathlib import Path
import matplotlib.pyplot as plt

def analyze_rosvot_results():
    """ROSVOT結果を分析"""
    
    print("=== ROSVOT結果分析 ===")
    
    # 結果ファイルを読み込み
    results_path = "dataset/チューリップ/rosvot_output_direct/notes.npy"
    
    if not Path(results_path).exists():
        print(f"結果ファイルが見つかりません: {results_path}")
        return
    
    # numpy形式の結果を読み込み
    results = np.load(results_path, allow_pickle=True).item()
    
    print(f"処理されたアイテム数: {len(results)}")
    
    for item_name, data in results.items():
        print(f"\n--- {item_name} ---")
        print(f"検出された音符数: {len(data['pitches'])}")
        print(f"音符の持続時間数: {len(data['note_durs'])}")
        
        # 音符情報を表示
        pitches = data['pitches']
        note_durs = data['note_durs']
        
        print(f"音符（最初の10個）: {pitches[:10]}")
        print(f"持続時間（最初の10個）: {[round(d, 3) for d in note_durs[:10]]}")
        
        # 統計情報
        if pitches:
            print(f"音符の範囲: {min(pitches)} - {max(pitches)} (MIDI番号)")
            print(f"平均持続時間: {np.mean(note_durs):.3f}秒")
            print(f"総演奏時間: {sum(note_durs):.3f}秒")
        
        # note2wordsがある場合の分析
        if data.get('note2words') is not None:
            note2words = data['note2words']
            print(f"音符と単語の対応: {len(note2words)}個")
            
            # スラー（同じ単語に複数の音符）の統計
            word_note_counts = {}
            for word_idx in note2words:
                word_note_counts[word_idx] = word_note_counts.get(word_idx, 0) + 1
            
            slur_counts = [count for count in word_note_counts.values() if count > 1]
            if slur_counts:
                print(f"スラーのある単語数: {len(slur_counts)}")
                print(f"最大スラー長: {max(slur_counts)}音符")

def compare_with_phonemes():
    """音素情報との比較"""
    print("\n=== 音素情報との比較 ===")
    
    # メタデータから音素情報を読み込み
    metadata_path = "dataset/チューリップ/rosvot_input/direct_tulip_metadata.json"
    
    if Path(metadata_path).exists():
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        word_durs = metadata[0]['word_durs']
        print(f"入力された単語数: {len(word_durs)}")
        print(f"単語の総持続時間: {sum(word_durs):.3f}秒")
        
        # 結果と比較
        results_path = "dataset/チューリップ/rosvot_output_direct/notes.npy"
        if Path(results_path).exists():
            results = np.load(results_path, allow_pickle=True).item()
            
            for item_name, data in results.items():
                note_durs = data['note_durs']
                print(f"出力された音符の総持続時間: {sum(note_durs):.3f}秒")
                
                # 比較
                ratio = sum(note_durs) / sum(word_durs) if sum(word_durs) > 0 else 0
                print(f"持続時間の比率（音符/単語）: {ratio:.3f}")

def main():
    """メイン処理"""
    analyze_rosvot_results()
    compare_with_phonemes()
    
    print("\n=== 生成されたファイル ===")
    output_dir = Path("dataset/チューリップ/rosvot_output_direct")
    
    if output_dir.exists():
        print("MIDIファイル:")
        for midi_file in output_dir.glob("midi/*.mid"):
            print(f"  {midi_file}")
        
        print("可視化プロット:")
        for plot_file in output_dir.glob("plot/*.png"):
            print(f"  {plot_file}")
        
        print("データファイル:")
        for npy_file in output_dir.glob("npy/*.npy"):
            print(f"  {npy_file}")

if __name__ == "__main__":
    main()

# module/sub/e_debug_rosvot_npy.py
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
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import pretty_midi

def analyze_rosvot_npy_files(output_dir: str) -> Dict:
    """ROSVOTが生成したNPYファイルを詳細解析"""
    output_path = Path(output_dir)
    
    # NPYファイルを探す（デバッグディレクトリも含む）
    note_files = list(output_path.glob("**/*note*.npy"))
    bd_files = list(output_path.glob("**/*bd*.npy"))
    
    if not note_files or not bd_files:
        print(f"NPYファイルが見つかりません: {output_path}")
        print("検索結果:")
        print(f"  - ノートファイル: {note_files}")
        print(f"  - 境界ファイル: {bd_files}")
        return {}
    
    note_file = note_files[0]
    bd_file = bd_files[0]
    
    print(f"[DEBUG] ノートファイル: {note_file}")
    print(f"[DEBUG] 境界ファイル: {bd_file}")
    
    # データを読み込み
    try:
        note_data = np.load(note_file, allow_pickle=True).item()
        bd_data = np.load(bd_file, allow_pickle=True)
        
        print(f"[DEBUG] ノートデータキー: {note_data.keys()}")
        print(f"[DEBUG] 境界データ形状: {bd_data.shape}")
        
        # ノート情報を表示（辞書の最初のアイテムを取得）
        item_key = list(note_data.keys())[0]
        item_data = note_data[item_key]
        print(f"[DEBUG] アイテムデータキー: {item_data.keys()}")
        
        pitches = item_data['pitches']
        note_durs = item_data['note_durs']
        
        print(f"\n📊 ノート情報:")
        print(f"  - ノート数: {len(pitches)}")
        print(f"  - ピッチ範囲: {min(pitches)}-{max(pitches)}")
        
        # 各ノートの詳細
        cumulative_time = 0
        for i, (pitch, dur) in enumerate(zip(pitches, note_durs)):
            start_time = cumulative_time
            end_time = cumulative_time + dur
            note_name = pretty_midi.note_number_to_name(int(pitch)) if pitch > 0 else "REST"
            print(f"  {i+1:2d}: {start_time:6.3f}s-{end_time:6.3f}s ({dur:6.3f}s) pitch={pitch:3.0f} ({note_name})")
            cumulative_time = end_time
        
        # 境界データの統計
        print(f"\n📊 境界データ統計:")
        print(f"  - フレーム数: {len(bd_data)}")
        print(f"  - 最大値: {bd_data.max():.4f}")
        print(f"  - 最小値: {bd_data.min():.4f}")
        print(f"  - 平均値: {bd_data.mean():.4f}")
        
        # 高い境界スコアの部分を検出
        high_bd_threshold = 0.3
        high_bd_indices = np.where(bd_data > high_bd_threshold)[0]
        print(f"  - 閾値{high_bd_threshold}以上のフレーム数: {len(high_bd_indices)}")
        
        # 時間軸での解析
        TPF = 128 / 24000.0  # ROSVOTの時間解像度
        
        # 14秒以降の境界データを詳しく見る
        t_start = 14.0
        t_end = 18.0
        i_start = int(t_start / TPF)
        i_end = int(t_end / TPF)
        
        if i_end <= len(bd_data):
            tail_bd = bd_data[i_start:i_end]
            tail_high_indices = np.where(tail_bd > high_bd_threshold)[0]
            
            print(f"\n🔍 {t_start}-{t_end}秒の境界データ:")
            print(f"  - フレーム数: {len(tail_bd)}")
            print(f"  - 高スコア({high_bd_threshold}以上)フレーム数: {len(tail_high_indices)}")
            print(f"  - 最大値: {tail_bd.max():.4f}")
            print(f"  - 平均値: {tail_bd.mean():.4f}")
            
            # 高スコア区間を時間で表示
            if len(tail_high_indices) > 0:
                print(f"  - 高スコア区間:")
                for idx in tail_high_indices[:10]:  # 最初の10個
                    time_sec = t_start + idx * TPF
                    score = tail_bd[idx]
                    print(f"    {time_sec:.3f}s: {score:.4f}")
        
        return {
            'note_data': note_data,
            'bd_data': bd_data,
            'TPF': TPF,
            'analysis': {
                'total_notes': len(pitches),
                'pitch_range': (min(pitches), max(pitches)),
                'total_duration': cumulative_time,
                'bd_stats': {
                    'frames': len(bd_data),
                    'max': float(bd_data.max()),
                    'min': float(bd_data.min()),
                    'mean': float(bd_data.mean()),
                    'high_frames': len(high_bd_indices)
                }
            }
        }
        
    except Exception as e:
        print(f"NPYファイル読み込みエラー: {e}")
        return {}

def create_debug_visualization(output_dir: str, analysis_data: Dict):
    """デバッグ用の可視化を作成"""
    if not analysis_data:
        return
    
    note_data = analysis_data['note_data']
    bd_data = analysis_data['bd_data']
    TPF = analysis_data['TPF']
    
    # 図を作成
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 12))
    
    # 1. ノート表示
    item_key = list(note_data.keys())[0]
    item_data = note_data[item_key]
    pitches = item_data['pitches']
    note_durs = item_data['note_durs']
    
    cumulative_time = 0
    note_times = []
    note_pitches = []
    
    for pitch, dur in zip(pitches, note_durs):
        if pitch > 0:  # 有効なピッチのみ
            note_times.extend([cumulative_time, cumulative_time + dur, cumulative_time + dur])
            note_pitches.extend([pitch, pitch, 0])
        cumulative_time += dur
    
    ax1.plot(note_times, note_pitches, 'b-', linewidth=2, label='ROSVOT Notes')
    ax1.set_ylabel('MIDI Note Number')
    ax1.set_title('ROSVOT検出ノート')
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    
    # 2. 境界データ
    time_axis = np.arange(len(bd_data)) * TPF
    ax2.plot(time_axis, bd_data, 'g-', alpha=0.7, label='Boundary Score')
    ax2.axhline(y=0.5, color='r', linestyle='--', alpha=0.5, label='Default Threshold (0.5)')
    ax2.axhline(y=0.3, color='orange', linestyle='--', alpha=0.5, label='Debug Threshold (0.3)')
    ax2.set_ylabel('Boundary Score')
    ax2.set_title('境界スコア（ノート境界の確信度）')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    # 3. 14-18秒の詳細表示
    t_start, t_end = 14.0, 18.0
    i_start = int(t_start / TPF)
    i_end = int(t_end / TPF)
    
    if i_end <= len(bd_data):
        detail_time = time_axis[i_start:i_end]
        detail_bd = bd_data[i_start:i_end]
        
        ax3.plot(detail_time, detail_bd, 'g-', linewidth=2, label='Boundary Score')
        ax3.axhline(y=0.5, color='r', linestyle='--', alpha=0.5, label='Default Threshold')
        ax3.axhline(y=0.3, color='orange', linestyle='--', alpha=0.5, label='Debug Threshold')
        
        # 高スコア部分をハイライト
        high_indices = np.where(detail_bd > 0.3)[0]
        if len(high_indices) > 0:
            ax3.scatter(detail_time[high_indices], detail_bd[high_indices], 
                       c='red', s=20, alpha=0.7, label='High Score Points')
        
        ax3.set_xlabel('Time (seconds)')
        ax3.set_ylabel('Boundary Score')
        ax3.set_title(f'{t_start}-{t_end}秒の境界スコア詳細')
        ax3.grid(True, alpha=0.3)
        ax3.legend()
    
    plt.tight_layout()
    
    # 保存
    output_path = Path(output_dir)
    plot_path = output_path / "e_debug_rosvot_analysis.png"
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"📊 デバッグ可視化を保存: {plot_path}")

def compare_with_phonemes(output_dir: str, analysis_data: Dict):
    """音素データとの比較分析"""
    if not analysis_data:
        return
    
    # タイムスタンプファイルを読み込み
    timestamps_path = Path(output_dir) / "a_timestamps.json"
    if not timestamps_path.exists():
        print("タイムスタンプファイルが見つかりません")
        return
    
    with open(timestamps_path, 'r', encoding='utf-8') as f:
        ts_data = json.load(f)
    
    phonemes = [(s, e, p) for (s, e, p) in ts_data["phonemes"] if p not in ("SP", "AP", "")]
    
    print(f"\n🔍 音素との比較分析:")
    
    # 問題の区間を詳しく見る
    problem_regions = [
        (9.8, 11.0, "チューリップ"),  # チュー・り・ぷ
        (14.5, 16.3, "さいたよー"),   # よー
        (16.0, 16.3, "最後のあ")      # あ
    ]
    
    note_data = analysis_data['note_data']
    bd_data = analysis_data['bd_data']
    TPF = analysis_data['TPF']
    
    for start_t, end_t, region_name in problem_regions:
        print(f"\n📍 {region_name} ({start_t}-{end_t}秒):")
        
        # この区間の音素
        region_phonemes = [(s, e, p) for (s, e, p) in phonemes 
                          if not (e <= start_t or s >= end_t)]
        
        print(f"  音素数: {len(region_phonemes)}")
        for s, e, p in region_phonemes:
            print(f"    {s:.3f}-{e:.3f}s: '{p}' ({e-s:.3f}s)")
        
        # この区間の境界スコア統計
        i_start = int(start_t / TPF)
        i_end = int(end_t / TPF)
        
        if i_end <= len(bd_data):
            region_bd = bd_data[i_start:i_end]
            high_count = np.sum(region_bd > 0.3)
            
            print(f"  境界スコア統計:")
            print(f"    フレーム数: {len(region_bd)}")
            print(f"    最大値: {region_bd.max():.4f}")
            print(f"    平均値: {region_bd.mean():.4f}")
            print(f"    高スコア(>0.3)フレーム数: {high_count}")
            print(f"    高スコア率: {high_count/len(region_bd)*100:.1f}%")

def find_latest_output_dir() -> Optional[str]:
    """最新の出力ディレクトリを探す"""
    output_dir = Path("output")
    if not output_dir.exists():
        return None
    
    # 全てのサブディレクトリを探す
    subdirs = [d for d in output_dir.iterdir() if d.is_dir()]
    
    if not subdirs:
        return None
    
    # 最新のディレクトリを返す（更新時刻順）
    latest_dir = max(subdirs, key=lambda d: d.stat().st_mtime)
    return str(latest_dir)

def main():
    """メイン処理"""
    print("=== ROSVOT NPYファイル詳細解析 ===")
    
    # 最新の出力ディレクトリを探す
    output_dir = find_latest_output_dir()
    
    if not output_dir:
        print("❌ 出力ディレクトリが見つかりません")
        return
    
    print(f"📁 解析対象ディレクトリ: {output_dir}")
    
    # NPYファイルを解析
    analysis_data = analyze_rosvot_npy_files(output_dir)
    
    if analysis_data:
        # 可視化を作成
        create_debug_visualization(output_dir, analysis_data)
        
        # 音素との比較
        compare_with_phonemes(output_dir, analysis_data)
        
        print("\n✅ 解析完了!")
        print("📊 詳細な可視化とログを確認してください")
    else:
        print("❌ 解析に失敗しました")

if __name__ == "__main__":
    main()

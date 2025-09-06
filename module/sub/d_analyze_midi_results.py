# module/sub/d_analyze_midi_results.py
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
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

class MIDIAnalyzer:
    """MIDIデータと音素データの分析クラス"""
    
    def __init__(self):
        self.timestamps_data = None
        self.midi_notes = []
        self.analysis_results = {}
        
    def load_timestamps(self, timestamps_path: str) -> bool:
        """タイムスタンプデータを読み込み"""
        try:
            with open(timestamps_path, 'r', encoding='utf-8') as f:
                self.timestamps_data = json.load(f)
            print(f"✅ タイムスタンプデータ読み込み完了: {len(self.timestamps_data['words'])}単語, {len(self.timestamps_data['phonemes'])}音素")
            return True
        except Exception as e:
            print(f"❌ タイムスタンプデータ読み込みエラー: {e}")
            return False
    
    def load_midi(self, midi_path: str) -> bool:
        """MIDIファイルを読み込み"""
        try:
            import pretty_midi
            midi = pretty_midi.PrettyMIDI(midi_path)
            
            self.midi_notes = []
            if midi.instruments:
                for note in midi.instruments[0].notes:
                    self.midi_notes.append({
                        'start': note.start,
                        'end': note.end,
                        'pitch': note.pitch,
                        'note_name': pretty_midi.note_number_to_name(note.pitch),
                        'velocity': note.velocity
                    })
            
            print(f"✅ MIDIデータ読み込み完了: {len(self.midi_notes)}ノート, 総時間{midi.get_end_time():.3f}秒")
            return True
        except Exception as e:
            print(f"❌ MIDIデータ読み込みエラー: {e}")
            return False
    
    def analyze_coverage(self) -> Dict:
        """音素とMIDIノートのカバレッジを分析"""
        if not self.timestamps_data or not self.midi_notes:
            return {}
        
        words = self.timestamps_data['words']
        phonemes = self.timestamps_data['phonemes']
        
        # 分析結果を格納
        results = {
            'total_words': len(words),
            'total_phonemes': len(phonemes),
            'total_midi_notes': len(self.midi_notes),
            'word_coverage': [],
            'phoneme_coverage': [],
            'missing_segments': [],
            'statistics': {}
        }
        
        # 単語レベルの分析
        for i, (start, end, word) in enumerate(words):
            if word == 'SP':  # 無音部分はスキップ
                continue
                
            # この単語の時間範囲にMIDIノートがあるかチェック
            overlapping_notes = self._find_overlapping_notes(start, end)
            
            coverage_info = {
                'index': i,
                'word': word,
                'start': start,
                'end': end,
                'duration': end - start,
                'has_midi': len(overlapping_notes) > 0,
                'coverage_ratio': self._calculate_coverage_ratio(start, end, overlapping_notes),
                'midi_notes': [{'note_name': note['note_name'], 'pitch': note['pitch']} for note in overlapping_notes] if overlapping_notes else []
            }
            results['word_coverage'].append(coverage_info)
        
        # 音素レベルの分析
        for i, (start, end, phoneme) in enumerate(phonemes):
            if phoneme == 'SP':  # 無音部分はスキップ
                continue
                
            overlapping_notes = self._find_overlapping_notes(start, end)
            
            coverage_info = {
                'index': i,
                'phoneme': phoneme,
                'start': start,
                'end': end,
                'duration': end - start,
                'has_midi': len(overlapping_notes) > 0,
                'coverage_ratio': self._calculate_coverage_ratio(start, end, overlapping_notes),
                'midi_notes': [{'note_name': note['note_name'], 'pitch': note['pitch']} for note in overlapping_notes] if overlapping_notes else []
            }
            results['phoneme_coverage'].append(coverage_info)
        
        # 欠落セグメントの特定
        results['missing_segments'] = self._find_missing_segments()
        
        # 統計情報の計算
        results['statistics'] = self._calculate_statistics(results)
        
        self.analysis_results = results
        return results
    
    def _find_overlapping_notes(self, start: float, end: float) -> List[Dict]:
        """指定された時間範囲と重複するMIDIノートを見つける"""
        overlapping = []
        for note in self.midi_notes:
            # 重複判定: ノートの開始が範囲の終了より前で、ノートの終了が範囲の開始より後
            if note['start'] < end and note['end'] > start:
                overlap_start = max(note['start'], start)
                overlap_end = min(note['end'], end)
                overlap_duration = overlap_end - overlap_start
                
                # 音名情報を含める
                overlapping.append({
                    'overlap_duration': overlap_duration,
                    'note_name': note['note_name'],
                    'pitch': note['pitch']
                })
        return overlapping
    
    def _calculate_coverage_ratio(self, start: float, end: float, overlapping_notes: List[Dict]) -> float:
        """カバレッジ比率を計算"""
        if not overlapping_notes:
            return 0.0
        
        total_duration = end - start
        covered_duration = sum(note['overlap_duration'] for note in overlapping_notes)
        
        return min(covered_duration / total_duration, 1.0)
    
    def _find_missing_segments(self) -> List[Dict]:
        """音階が取れなかった時間セグメントを特定"""
        missing = []
        
        # 音素データから無音以外の部分を抽出
        vocal_segments = []
        for start, end, phoneme in self.timestamps_data['phonemes']:
            if phoneme != 'SP':
                vocal_segments.append((start, end, phoneme))
        
        # 各音素セグメントでMIDIカバレッジをチェック
        for start, end, phoneme in vocal_segments:
            overlapping_notes = self._find_overlapping_notes(start, end)
            coverage_ratio = self._calculate_coverage_ratio(start, end, overlapping_notes)
            
            if coverage_ratio < 0.1:  # 10%未満のカバレッジは欠落とみなす
                missing.append({
                    'start': start,
                    'end': end,
                    'duration': end - start,
                    'phoneme': phoneme,
                    'coverage_ratio': coverage_ratio,
                    'reason': 'low_coverage' if coverage_ratio > 0 else 'no_midi'
                })
        
        return missing
    
    def _calculate_statistics(self, results: Dict) -> Dict:
        """統計情報を計算"""
        word_coverage = results['word_coverage']
        phoneme_coverage = results['phoneme_coverage']
        
        # 単語統計
        words_with_midi = sum(1 for w in word_coverage if w['has_midi'])
        word_success_rate = words_with_midi / len(word_coverage) if word_coverage else 0
        
        # 音素統計
        phonemes_with_midi = sum(1 for p in phoneme_coverage if p['has_midi'])
        phoneme_success_rate = phonemes_with_midi / len(phoneme_coverage) if phoneme_coverage else 0
        
        # カバレッジ比率統計
        word_coverage_ratios = [w['coverage_ratio'] for w in word_coverage]
        phoneme_coverage_ratios = [p['coverage_ratio'] for p in phoneme_coverage]
        
        return {
            'word_success_rate': word_success_rate,
            'phoneme_success_rate': phoneme_success_rate,
            'words_with_midi': words_with_midi,
            'phonemes_with_midi': phonemes_with_midi,
            'avg_word_coverage': np.mean(word_coverage_ratios) if word_coverage_ratios else 0,
            'avg_phoneme_coverage': np.mean(phoneme_coverage_ratios) if phoneme_coverage_ratios else 0,
            'missing_segments_count': len(results['missing_segments']),
            'total_missing_duration': sum(seg['duration'] for seg in results['missing_segments'])
        }
    
    
    def generate_report(self, output_path: str):
        """分析レポートを生成"""
        if not self.analysis_results:
            return
        
        stats = self.analysis_results['statistics']
        
        report = {
            'analysis_timestamp': datetime.now().isoformat(),
            'summary': {
                'total_words': self.analysis_results['total_words'],
                'total_phonemes': self.analysis_results['total_phonemes'],
                'total_midi_notes': self.analysis_results['total_midi_notes'],
                'word_success_rate': f"{stats['word_success_rate']:.1%}",
                'phoneme_success_rate': f"{stats['phoneme_success_rate']:.1%}",
                'missing_segments_count': stats['missing_segments_count'],
                'total_missing_duration': f"{stats['total_missing_duration']:.3f}秒"
            },
            'detailed_results': self.analysis_results
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 分析レポートを保存: {output_path}")
        
        # コンソールにサマリーを表示
        print("\n" + "="*60)
        print("📊 MIDI分析結果サマリー")
        print("="*60)
        print(f"📝 総単語数: {report['summary']['total_words']}")
        print(f"🔤 総音素数: {report['summary']['total_phonemes']}")
        print(f"🎵 総MIDIノート数: {report['summary']['total_midi_notes']}")
        print(f"✅ 単語成功率: {report['summary']['word_success_rate']}")
        print(f"✅ 音素成功率: {report['summary']['phoneme_success_rate']}")
        print(f"❌ 欠落セグメント数: {report['summary']['missing_segments_count']}")
        print(f"⏱️  欠落総時間: {report['summary']['total_missing_duration']}")
        
        if self.analysis_results['missing_segments']:
            print("\n🔍 欠落セグメント詳細:")
            for i, seg in enumerate(self.analysis_results['missing_segments'], 1):
                print(f"  {i}. 音素'{seg['phoneme']}' ({seg['start']:.3f}s-{seg['end']:.3f}s, {seg['duration']:.3f}s)")

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
    print("=== MIDIデータ分析ツール ===")
    
    # 最新の出力ディレクトリを自動検出
    output_dir = find_latest_output_dir()
    
    if not output_dir:
        print("❌ 出力ディレクトリが見つかりません")
        return
    
    print(f"📁 分析対象ディレクトリ: {output_dir}")
    
    # ファイルパスを設定
    timestamps_path = Path(output_dir) / "a_timestamps.json"
    midi_path = Path(output_dir) / "c_output.mid"
    
    # ファイルの存在確認
    if not timestamps_path.exists():
        print(f"❌ タイムスタンプファイルが見つかりません: {timestamps_path}")
        return
    
    if not midi_path.exists():
        print(f"❌ MIDIファイルが見つかりません: {midi_path}")
        return
    
    # 分析器を初期化
    analyzer = MIDIAnalyzer()
    
    # データを読み込み
    if not analyzer.load_timestamps(str(timestamps_path)):
        return
    
    if not analyzer.load_midi(str(midi_path)):
        return
    
    # 分析を実行
    print("\n🔍 カバレッジ分析を実行中...")
    results = analyzer.analyze_coverage()
    
    # 出力ファイルパスを設定
    output_base = Path(output_dir)
    report_json = output_base / "d_analysis_report.json"
    
    # レポートを生成
    print("\n📄 レポートを生成中...")
    analyzer.generate_report(str(report_json))
    
    print(f"\n🎉 分析完了! 成果物:")
    print(f"  📄 詳細レポート: {report_json}")

if __name__ == "__main__":
    main()
